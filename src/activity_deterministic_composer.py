"""Composição determinística de relatos a partir de fatos validados."""

import hashlib
import re
from dataclasses import dataclass

from activity_bibliography import (
    BibliographyCatalog,
    load_project_bibliography_catalog,
)
from activity_content_allocator import AllocatedParagraph, allocate_activity_content
from activity_contract import EnrichedActivity, FACT_GROUPS
from activity_draft import ActivityCompositionError, StructuredDraft
from activity_draft_validator import ActivityDraftValidator, DraftValidationReport, count_words
from activity_narrative_planner import NarrativePlan


OPERATIONAL_FRAMES = (
    "Acompanhei {article} {fact}.",
    "Na sequência, observei {article} {fact}.",
    "Também registrei {article} {fact}.",
    "Outro ponto acompanhado foi {article} {fact}.",
    "Entre as etapas observadas esteve {article} {fact}.",
    "Minha atenção se voltou para {article} {fact}.",
    "A rotina profissional incluiu {article} {fact}.",
    "No registro da atividade, destaquei {article} {fact}.",
)

ACCOMPANIMENT_FRAMES = (
    "Foi possível observar o {fact}.",
    "Mantive atenção ao {fact}.",
    "Registrei o {fact} como parte da rotina.",
    "Minha observação incluiu o {fact}.",
    "A vivência prática permitiu o {fact}.",
    "Entre os pontos registrados esteve o {fact}.",
    "A rotina observada contemplou o {fact}.",
    "Dediquei atenção ao {fact}.",
)

OBSERVATION_FRAMES = (
    "A {fact} fez parte da atividade.",
    "Também registrei a {fact}.",
    "Mantive atenção à {fact}.",
    "A rotina incluiu a {fact}.",
    "Entre os aspectos acompanhados esteve a {fact}.",
    "A experiência prática contemplou a {fact}.",
    "No registro da vivência, destaquei a {fact}.",
    "Minha atenção também se voltou à {fact}.",
)

FEMININE_FACT_PREFIXES = (
    "adoção",
    "análise",
    "anamnese",
    "aplicação",
    "avaliação",
    "classificação",
    "coleta",
    "compreensão",
    "conferência",
    "definição",
    "diferenciação",
    "documentação",
    "escolha",
    "higienização",
    "identificação",
    "importância",
    "inserção",
    "leitura",
    "marcação",
    "necessidade",
    "observação",
    "organização",
    "orientação",
    "preparação",
    "realização",
    "recomendação",
    "relação",
    "relevância",
    "seleção",
    "verificação",
)

LEAD_VARIANTS = {
    "avaliacao_planejamento": (
        "Na etapa inicial, acompanhei como a equipe reuniu as informações necessárias para organizar o atendimento.",
        "A avaliação abriu a atividade e permitiu observar os critérios usados pela equipe no planejamento.",
        "O primeiro momento da vivência foi dedicado à avaliação e à organização da conduta profissional.",
        "Antes da parte prática, registrei os elementos considerados pelo profissional na avaliação inicial.",
    ),
    "planejamento_preparo": (
        "A organização definida após a avaliação orientou o preparo acompanhado na sequência.",
        "Com os critérios iniciais reunidos, a equipe passou ao planejamento e à preparação do atendimento.",
        "O planejamento profissional serviu de base para a organização observada antes da execução.",
        "Na continuidade do atendimento, acompanhei a passagem da avaliação para o preparo técnico.",
    ),
    "preparo_biosseguranca": (
        "Antes da execução, minha atenção se voltou à preparação do ambiente e aos cuidados adotados pela equipe.",
        "O preparo do atendimento evidenciou os cuidados de organização e biossegurança presentes na rotina.",
        "Na fase preparatória, observei como ambiente, materiais e medidas de proteção foram organizados.",
        "A execução foi antecedida por uma etapa de preparo que acompanhei junto à equipe responsável.",
    ),
    "preparo_execucao": (
        "Com o planejamento estabelecido, acompanhei o preparo e a execução conduzidos sob responsabilidade profissional.",
        "A parte prática começou pela organização dos recursos e avançou para a execução supervisionada.",
        "Do preparo à execução, mantive o foco na sequência técnica adotada pelo profissional.",
        "A rotina prosseguiu com os cuidados preparatórios e com o acompanhamento da prática profissional.",
    ),
    "execucao": (
        "Na execução supervisionada, observei a sequência técnica sem assumir decisões ou ações reservadas ao profissional.",
        "A etapa prática foi acompanhada com atenção aos limites da minha participação como estudante.",
        "Ao longo da execução, registrei a sequência conduzida pelo profissional e os cuidados da equipe.",
        "Minha observação da prática permaneceu concentrada nas etapas técnicas e na supervisão profissional.",
    ),
    "execucao_orientacoes": (
        "Na parte prática, acompanhei a execução profissional e a transição para as orientações posteriores.",
        "A execução observada foi seguida pelas orientações apresentadas pela equipe ao final do atendimento.",
        "O momento prático reuniu a técnica supervisionada e os cuidados discutidos após sua conclusão.",
        "Entre a execução e o encerramento, registrei tanto a prática quanto as orientações fornecidas.",
    ),
    "orientacoes_aprendizado": (
        "Após a etapa prática, registrei as orientações apresentadas e os conhecimentos relacionados à atividade.",
        "As orientações posteriores ajudaram a conectar a prática observada aos conteúdos estudados.",
        "No momento seguinte, concentrei minha atenção nos cuidados explicados e no aprendizado técnico.",
        "A conclusão do atendimento abriu espaço para acompanhar orientações e organizar os aprendizados da vivência.",
    ),
    "aprendizado_fechamento": (
        "Ao reunir os pontos observados, concentrei o fechamento nos aprendizados técnicos específicos dessa vivência.",
        "A síntese da atividade foi construída a partir dos conhecimentos que se tornaram mais concretos na prática.",
        "Para encerrar o registro, relacionei as orientações acompanhadas aos principais aprendizados técnicos.",
        "O fechamento retomou os aspectos da atividade que mais contribuíram para minha compreensão profissional.",
    ),
    "fechamento": (
        "Como síntese da atividade, retomei os aspectos técnicos que ficaram mais claros ao longo do acompanhamento.",
        "Ao concluir o registro, reuni os aprendizados que se destacaram na experiência observada.",
        "O encerramento da vivência permitiu organizar os conhecimentos técnicos percebidos na rotina.",
        "Na reflexão final, relacionei a prática acompanhada aos conteúdos relevantes para minha formação.",
    ),
}

OPENING_VARIANTS = (
    "A atividade de {title} integrou a rotina que acompanhei durante o estágio, sempre sob responsabilidade de profissional habilitado.",
    "Entre as práticas observadas no estágio esteve a atividade de {title}, conduzida por profissional habilitado.",
    "Na rotina do estágio, tive contato com a atividade de {title}, acompanhando sua condução profissional.",
    "Uma das vivências registradas no estágio foi a atividade de {title}, realizada sob responsabilidade da equipe habilitada.",
    "No período de estágio, observei o desenvolvimento da atividade de {title} junto à equipe responsável.",
    "Dentro das práticas previstas no estágio, acompanhei a atividade de {title} sob supervisão profissional.",
    "Meu contato com a atividade de {title} ocorreu na rotina de estágio e permaneceu restrito à observação supervisionada.",
    "A rotina acompanhada incluiu a atividade de {title}, conduzida pelo profissional responsável.",
    "Como parte da experiência de estágio, acompanhei a atividade de {title} ao lado da equipe habilitada.",
    "O estágio permitiu observar a atividade de {title} em um contexto de atuação profissional supervisionada.",
    "Na experiência prática registrada, a atividade de {title} foi acompanhada sob condução da equipe responsável.",
    "Entre os atendimentos acompanhados, a atividade de {title} aproximou o conteúdo acadêmico da rotina profissional.",
)

OPENING_DETAIL_ACTIONS = (
    "com atenção voltada",
    "com foco",
    "mantendo minha atenção ligada",
    "dedicando atenção",
    "com a observação direcionada",
    "deixando meu registro associado",
    "mantendo o acompanhamento relacionado",
    "com interesse voltado",
    "direcionando meu olhar",
    "mantendo a descrição ligada",
    "com o registro direcionado",
    "relacionando minha observação",
)

OPENING_DETAIL_FOCUSES = (
    "aos critérios adotados pela equipe",
    "à sequência observada no atendimento",
    "aos cuidados presentes na rotina",
    "à relação entre teoria e prática",
    "aos limites definidos para o estágio",
    "aos pontos apresentados pelo profissional",
    "à organização adotada pela equipe",
    "aos aspectos técnicos da atividade",
    "à forma como o atendimento prosseguiu",
    "aos registros feitos durante a prática",
    "à supervisão mantida pela equipe",
    "aos conhecimentos relacionados à atividade",
)

TECHNICAL_OPENING_VARIANTS = (
    "O aspecto técnico central da atividade foi {principle}",
    "Do ponto de vista técnico, observei {principle}",
    "A base técnica acompanhada envolveu {principle}",
    "Durante a atividade, o fundamento apresentado foi {principle}",
    "A explicação técnica da equipe abordou {principle}",
    "Entre os fundamentos discutidos esteve {principle}",
    "Na observação da rotina, o conteúdo técnico incluiu {principle}",
    "O conteúdo técnico associado à prática envolveu {principle}",
    "A equipe relacionou a atividade a este fundamento: {principle}",
    "Como fundamento da prática, foi apresentada a seguinte relação: {principle}",
    "O acompanhamento permitiu registrar este aspecto técnico: {principle}",
    "Na parte conceitual da atividade, foi discutido o seguinte fundamento: {principle}",
)

PARTICIPATION_VARIANTS = (
    "Minha participação se concentrou na observação da rotina e no auxílio permitido pela equipe responsável.",
    "Atuei apenas como observador e auxiliar nas tarefas previamente autorizadas pela supervisão.",
    "O acompanhamento ocorreu dentro dos limites do estágio, sem assumir decisões reservadas ao profissional.",
    "Mantive uma postura de observação, registrando a sequência e auxiliando somente quando autorizado.",
    "Minha presença na atividade teve caráter acadêmico e permaneceu vinculada à supervisão da equipe.",
    "A vivência foi acompanhada como estudante, com participação limitada às ações permitidas pelo responsável.",
)

LEAD_SUFFIX_SUBJECTS = (
    "Esse recorte",
    "A observação desse momento",
    "O registro dessa etapa",
    "Esse ponto da atividade",
    "A experiência nesse trecho",
    "O acompanhamento dessa fase",
    "Essa parte da rotina",
    "O contato com esse momento",
    "A sequência observada",
    "A atenção dedicada a essa etapa",
    "O modo como a atividade prosseguiu",
    "A vivência desse ponto",
)

LEAD_SUFFIX_PREDICATES = (
    "orientou a forma como organizei o relato",
    "ajudou a situar os aspectos descritos a seguir",
    "manteve meu registro ligado à rotina acompanhada",
    "serviu de base para relacionar teoria e prática",
    "permitiu destacar os critérios apresentados pela equipe",
    "contribuiu para organizar os pontos observados",
    "deixou mais clara a sequência adotada no atendimento",
    "direcionou minha atenção aos cuidados da equipe",
    "ajudou a reunir os elementos mais presentes na prática",
    "permitiu registrar a atividade sem assumir decisões profissionais",
    "reforçou os limites da minha participação como estudante",
    "aproximou o conteúdo acadêmico da situação acompanhada",
)

BOOSTERS = {
    "opening": (
        "Desde o início, mantive uma postura de observação e auxílio apenas nas tarefas autorizadas.",
        "O foco permaneceu na rotina acompanhada e nos critérios apresentados pela equipe responsável.",
    ),
    "evaluation": (
        "Ao acompanhar essa etapa, percebi que a avaliação organiza a sequência do atendimento antes de qualquer intervenção.",
        "As informações foram consideradas em conjunto, respeitando as características observadas em cada situação.",
        "Minha atenção ficou voltada aos critérios utilizados pelo profissional para relacionar avaliação e planejamento.",
        "Esse momento mostrou como diferentes observações são reunidas antes da definição da conduta profissional.",
        "O registro da atividade ajudou a distinguir a participação do estudante das decisões reservadas ao responsável.",
        "A análise conduzida pela equipe serviu de referência para compreender as etapas que vieram depois.",
    ),
    "execution": (
        "A ordem adotada permitiu acompanhar a relação entre organização, biossegurança e desenvolvimento da prática.",
        "Cada decisão permaneceu sob responsabilidade profissional, enquanto observei os cuidados presentes na rotina.",
        "A atenção ao preparo deixou mais clara a função das medidas adotadas antes e depois da execução.",
        "Minha participação ficou restrita à observação e ao auxílio autorizado na organização dos materiais.",
        "A sequência ajudou a relacionar os cuidados do ambiente com o acompanhamento técnico do procedimento.",
        "O modo como a equipe organizou o atendimento facilitou o registro das etapas sem transformar a vivência em protocolo.",
        "A supervisão esteve presente durante toda a atividade, delimitando com clareza o papel do estudante.",
    ),
    "orientation": (
        "As explicações foram acompanhadas como parte do atendimento, sem que eu assumisse orientações clínicas.",
        "Esse momento conectou o que havia sido observado na prática aos cuidados discutidos pela equipe.",
        "O registro dos pontos apresentados favoreceu uma compreensão mais concreta dos riscos relacionados à atividade.",
        "Também ficou mais clara a importância de comunicar alterações à equipe e respeitar o acompanhamento indicado.",
        "A vivência permitiu relacionar o conteúdo estudado às situações observadas sob supervisão.",
        "Minha reflexão se concentrou nos limites de atuação e nos conhecimentos técnicos envolvidos no atendimento.",
        "Os cuidados posteriores foram compreendidos como continuidade da atenção iniciada na avaliação.",
    ),
    "closing": (
        "A experiência reforçou meu compromisso com a observação cuidadosa e com os limites da atuação supervisionada.",
        "O aprendizado obtido permaneceu ligado às situações concretas acompanhadas junto à equipe.",
        "Esse registro reuniu os pontos que contribuíram de forma mais direta para minha formação técnica.",
        "Ao final, consegui relacionar melhor o conteúdo acadêmico com a rotina profissional observada.",
    ),
}

SHORT_BOOSTERS = (
    "Mantive atenção à sequência e à supervisão profissional.",
    "As etapas foram registradas a partir da rotina observada.",
    "O acompanhamento permaneceu dentro dos limites do estágio.",
)


class DeterministicCompositionError(ActivityCompositionError):
    """O texto determinístico não cumpriu o contrato final."""

    def __init__(self, report: DraftValidationReport) -> None:
        codes = ", ".join(dict.fromkeys(issue.code for issue in report.issues))
        super().__init__(f"composição determinística inválida: {codes}")
        self.report = report


@dataclass(frozen=True)
class DeterministicWritingResult:
    draft: StructuredDraft
    final_report: DraftValidationReport
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeVariation:
    seed: str
    index: int

    def choose(self, values: tuple[str, ...], key: str) -> str:
        offset = _stable_offset(f"{self.seed}:{key}", len(values))
        return values[(self.index + offset) % len(values)]

    def choose_lead(self, values: tuple[str, ...], key: str) -> str:
        base = values[
            (self.index + _stable_offset(f"{self.seed}:{key}:lead", len(values)))
            % len(values)
        ]
        subject_index = (
            self.index + _stable_offset(f"{key}:suffix-subject", len(LEAD_SUFFIX_SUBJECTS))
        ) % len(LEAD_SUFFIX_SUBJECTS)
        predicate_index = (
            self.index // len(LEAD_SUFFIX_SUBJECTS)
            + _stable_offset(f"{key}:suffix-predicate", len(LEAD_SUFFIX_PREDICATES))
        ) % len(LEAD_SUFFIX_PREDICATES)
        suffix = (
            f"{LEAD_SUFFIX_SUBJECTS[subject_index]} "
            f"{LEAD_SUFFIX_PREDICATES[predicate_index]}."
        )
        return f"{base} {suffix}"


def _stable_offset(text: str, size: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def _strip_terminal_punctuation(text: str) -> str:
    return text.strip().rstrip(".!?;:")


def _article_for(fact: str) -> str:
    normalized = fact.casefold()
    if normalized.startswith("orientações"):
        return "as"
    if normalized.startswith(FEMININE_FACT_PREFIXES):
        return "a"
    return "o"


def _opening_sentences(
    activity: EnrichedActivity,
    variation: NarrativeVariation,
    inline_citation: str,
    activity_position: int,
) -> list[str]:
    opening_title = activity.titulo
    normalized_title = activity.titulo.casefold()
    if any(
        normalized_title in fact.casefold()
        for group in FACT_GROUPS
        for fact in activity.fatos_permitidos.get(group)
    ):
        opening_title = activity.categoria

    context_parts = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", activity.contexto_seguro)
        if part.strip()
    ]
    principle = context_parts[-1] if len(context_parts) > 1 else context_parts[0]
    principle = re.sub(
        r"^O princípio técnico observado é\s+",
        "",
        _strip_terminal_punctuation(principle),
        flags=re.IGNORECASE,
    )
    opening_index = (
        variation.index + activity_position - 1
    ) % len(OPENING_VARIANTS)
    opening_action_index = (
        variation.index // len(OPENING_VARIANTS)
    ) % len(OPENING_DETAIL_ACTIONS)
    opening_focus_index = (
        variation.index
        // (len(OPENING_VARIANTS) * len(OPENING_DETAIL_ACTIONS))
    ) % len(OPENING_DETAIL_FOCUSES)
    technical_index = (
        variation.index // len(OPENING_VARIANTS) + activity_position - 1
    ) % len(TECHNICAL_OPENING_VARIANTS)
    cited_principle = TECHNICAL_OPENING_VARIANTS[technical_index].format(
        principle=principle
    )
    cited_principle += f" {inline_citation}." if inline_citation else "."
    sentences = [
        (
            _strip_terminal_punctuation(
                OPENING_VARIANTS[opening_index].format(title=opening_title)
            )
            + f", {OPENING_DETAIL_ACTIONS[opening_action_index]} "
            + OPENING_DETAIL_FOCUSES[opening_focus_index]
            + "."
        )
    ]
    if inline_citation:
        sentences.append(cited_principle)
    sentences.append(
        variation.choose(
            PARTICIPATION_VARIANTS,
            f"{activity.titulo}:participation",
        )
    )
    return sentences


def _paragraph_kind(key: str) -> str:
    if key in {"abertura", "abertura_avaliacao"}:
        return "opening"
    if "avaliacao" in key or "planejamento" in key:
        return "evaluation"
    if "preparo" in key or "execucao" in key:
        return "execution"
    if key == "fechamento" or "fechamento" in key:
        return "closing"
    return "orientation"


def _fact_sentences(
    activity: EnrichedActivity,
    allocation: AllocatedParagraph,
    variation: NarrativeVariation,
) -> list[str]:
    learning_facts = set(activity.fatos_permitidos.orientacoes_aprendizado)
    offset = _stable_offset(
        f"{variation.seed}:{activity.titulo}:{allocation.spec.key}:facts",
        len(OPERATIONAL_FRAMES),
    )
    sentences = []
    for index, fact in enumerate(allocation.facts):
        clean_fact = _strip_terminal_punctuation(fact)
        normalized = clean_fact.casefold()
        variant = (variation.index + offset + index) % len(OPERATIONAL_FRAMES)

        if fact in learning_facts:
            if normalized.startswith("compreensão"):
                templates = (
                    "A atividade ampliou minha {fact}.",
                    "A prática observada favoreceu minha {fact}.",
                    "A vivência contribuiu diretamente para minha {fact}.",
                    "O conteúdo acompanhado fortaleceu minha {fact}.",
                )
            elif normalized.startswith("relação"):
                templates = (
                    "Também compreendi melhor a {fact}.",
                    "A prática tornou mais clara a {fact}.",
                    "O acompanhamento ajudou a perceber a {fact}.",
                    "Entre os aprendizados esteve a {fact}.",
                )
            elif normalized.startswith("relevância"):
                templates = (
                    "Percebi com mais clareza a {fact}.",
                    "A experiência destacou a {fact}.",
                    "A rotina observada evidenciou a {fact}.",
                    "O aprendizado também contemplou a {fact}.",
                )
            elif normalized.startswith("importância"):
                templates = (
                    "Outro aprendizado foi reconhecer a {fact}.",
                    "A vivência deixou mais evidente a {fact}.",
                    "Também pude refletir sobre a {fact}.",
                    "Entre os pontos compreendidos esteve a {fact}.",
                )
            elif normalized.startswith("necessidade"):
                templates = (
                    "A vivência evidenciou a {fact}.",
                    "O acompanhamento reforçou a {fact}.",
                    "A prática tornou mais concreta a {fact}.",
                    "Também reconheci a {fact}.",
                )
            elif normalized.startswith("diferenciação"):
                templates = (
                    "O aprendizado abrangeu temas de {fact}.",
                    "A atividade ajudou no estudo de {fact}.",
                    "A experiência favoreceu a análise de {fact}.",
                    "O conteúdo prático incluiu aspectos de {fact}.",
                )
            elif normalized.startswith("recomendação"):
                templates = (
                    "Também registrei a {fact}.",
                    "Entre as orientações esteve a {fact}.",
                    "Acompanhei a {fact}.",
                    "Minha atenção incluiu a {fact}.",
                )
            elif normalized.startswith("orientações"):
                templates = (
                    "Acompanhei as {fact}.",
                    "Registrei as {fact}.",
                    "A etapa final incluiu as {fact}.",
                    "Também observei as {fact}.",
                )
            elif normalized.startswith("orientação"):
                templates = (
                    "Acompanhei a {fact}.",
                    "Registrei a {fact}.",
                    "A etapa final incluiu a {fact}.",
                    "Também observei a {fact}.",
                )
            elif normalized.startswith("acompanhamento"):
                sentence = ACCOMPANIMENT_FRAMES[variant].format(fact=clean_fact)
                templates = ()
            elif normalized.startswith(("conhecimento", "domínio")):
                templates = (
                    "O conteúdo estudado se relacionou ao {fact}.",
                    "A prática aproximou minha formação do {fact}.",
                    "A atividade abordou aspectos ligados ao {fact}.",
                    "O registro técnico também considerou o {fact}.",
                )
            else:
                templates = (
                    "O aprendizado técnico também abrangeu {fact}.",
                    "A vivência acrescentou conhecimentos sobre {fact}.",
                    "Entre os conteúdos relacionados esteve {fact}.",
                    "A reflexão técnica incluiu {fact}.",
                )

            if templates:
                sentence = templates[variant % len(templates)].format(fact=clean_fact)
        elif normalized.startswith("acompanhamento"):
            frame = ACCOMPANIMENT_FRAMES[variant]
            sentence = frame.format(fact=clean_fact)
        elif normalized.startswith("observação"):
            frame = OBSERVATION_FRAMES[variant]
            sentence = frame.format(fact=clean_fact)
        else:
            frame = OPERATIONAL_FRAMES[variant]
            sentence = frame.format(article=_article_for(clean_fact), fact=clean_fact)

        sentences.append(sentence)
    return sentences


def _candidate_boosters(
    activity: EnrichedActivity,
    allocation: AllocatedParagraph,
    used_boosters: set[str],
    variation: NarrativeVariation,
) -> list[str]:
    kind = _paragraph_kind(allocation.spec.key)
    pool = BOOSTERS[kind]
    offset = _stable_offset(
        f"{variation.seed}:{activity.titulo}:{allocation.spec.key}:boosters",
        len(pool),
    )
    ordered = [
        pool[(variation.index + offset + index) % len(pool)]
        for index in range(len(pool))
    ]
    return [sentence for sentence in ordered if sentence not in used_boosters]


def _render_paragraph(
    activity: EnrichedActivity,
    allocation: AllocatedParagraph,
    used_boosters: set[str],
    variation: NarrativeVariation,
    inline_citation: str,
    activity_position: int,
) -> str:
    if allocation.context:
        sentences = _opening_sentences(
            activity,
            variation,
            inline_citation,
            activity_position,
        )
    else:
        sentences = [
            variation.choose_lead(
                LEAD_VARIANTS[allocation.spec.key],
                f"{activity.titulo}:{allocation.spec.key}:lead",
            )
        ]
    sentences.extend(_fact_sentences(activity, allocation, variation))

    target = allocation.spec.min_words + min(
        8,
        (allocation.spec.max_words - allocation.spec.min_words) // 3,
    )
    for booster in _candidate_boosters(
        activity,
        allocation,
        used_boosters,
        variation,
    ):
        if count_words(" ".join(sentences)) >= target:
            break
        if count_words(" ".join(sentences + [booster])) <= allocation.spec.max_words:
            sentences.append(booster)
            used_boosters.add(booster)

    for booster in SHORT_BOOSTERS:
        if count_words(" ".join(sentences)) >= allocation.spec.min_words:
            break
        if booster in used_boosters:
            continue
        if count_words(" ".join(sentences + [booster])) <= allocation.spec.max_words:
            sentences.append(booster)
            used_boosters.add(booster)

    return " ".join(sentences)


class DeterministicActivityComposer:
    """Produz o relato final sem chamadas a modelos de linguagem."""

    def __init__(
        self,
        validator: ActivityDraftValidator | None = None,
        *,
        report_seed: str = "default",
        variant_index: int = 0,
        bibliography_catalog: BibliographyCatalog | None = None,
    ) -> None:
        self.validator = validator or ActivityDraftValidator()
        self.variation = NarrativeVariation(report_seed, variant_index)
        self.bibliography_catalog = (
            bibliography_catalog
            if bibliography_catalog is not None
            else load_project_bibliography_catalog()
        )

    def write(
        self,
        activity: EnrichedActivity,
        plan: NarrativePlan,
    ) -> DeterministicWritingResult:
        citation_ids: tuple[str, ...] = ()
        inline_citation = ""
        if activity.referencias_ids:
            self.bibliography_catalog.validate_activity_ids(activity.referencias_ids)
            citation_id = self.variation.choose(
                activity.referencias_ids,
                f"{activity.titulo}:reference",
            )
            citation_ids = (citation_id,)
            inline_citation = self.bibliography_catalog.inline_citation(citation_id)
        allocations = allocate_activity_content(activity, plan)
        used_boosters: set[str] = set()
        paragraphs = tuple(
            (
                allocation.spec.key,
                _render_paragraph(
                    activity,
                    allocation,
                    used_boosters,
                    self.variation,
                    inline_citation,
                    plan.position,
                ),
            )
            for allocation in allocations
        )
        draft = StructuredDraft(paragraphs)
        report = self.validator.validate(activity, plan, draft)
        if not report.is_acceptable:
            raise DeterministicCompositionError(report)
        return DeterministicWritingResult(draft, report, citation_ids)
