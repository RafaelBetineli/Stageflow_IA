"""Planejamento determinístico da composição dos relatos de atividade."""

from dataclasses import dataclass

from activity_contract import EnrichedActivity, FACT_GROUPS


MIN_TOTAL_WORDS = 420
MAX_TOTAL_WORDS = 700
MIN_PARAGRAPHS = 4
MAX_PARAGRAPHS = 6
MIN_GUARANTEED_SPREAD = 30


@dataclass(frozen=True)
class ParagraphSpec:
    key: str
    purpose: str
    min_words: int
    max_words: int
    source_groups: tuple[str, ...] = ()
    uses_context: bool = False

    @property
    def target_words(self) -> int:
        return (self.min_words + self.max_words) // 2


@dataclass(frozen=True)
class NarrativeProfile:
    profile_id: str
    paragraphs: tuple[ParagraphSpec, ...]

    @property
    def min_total_words(self) -> int:
        return sum(paragraph.min_words for paragraph in self.paragraphs)

    @property
    def max_total_words(self) -> int:
        return sum(paragraph.max_words for paragraph in self.paragraphs)

    @property
    def target_total_words(self) -> int:
        return sum(paragraph.target_words for paragraph in self.paragraphs)

    @property
    def guaranteed_spread(self) -> int:
        return max(paragraph.min_words for paragraph in self.paragraphs) - min(
            paragraph.max_words for paragraph in self.paragraphs
        )


@dataclass(frozen=True)
class NarrativePlan:
    activity_title: str
    report_type: str
    position: int
    profile: NarrativeProfile

    @property
    def paragraphs(self) -> tuple[ParagraphSpec, ...]:
        return self.profile.paragraphs


PROFILES = (
    NarrativeProfile(
        profile_id="A5",
        paragraphs=(
            ParagraphSpec(
                "abertura",
                "Apresentar brevemente a atividade acompanhada, sem definição enciclopédica.",
                45,
                65,
                uses_context=True,
            ),
            ParagraphSpec(
                "avaliacao_planejamento",
                "Relacionar avaliação inicial e planejamento conduzidos pelo profissional.",
                100,
                125,
                ("avaliacao_planejamento",),
            ),
            ParagraphSpec(
                "preparo_execucao",
                "Desenvolver preparo, biossegurança e acompanhamento da execução.",
                135,
                165,
                ("preparo_biosseguranca_execucao",),
            ),
            ParagraphSpec(
                "orientacoes_aprendizado",
                "Integrar orientações observadas e aprendizado técnico específico.",
                110,
                140,
                ("orientacoes_aprendizado",),
            ),
            ParagraphSpec(
                "fechamento",
                "Encerrar de forma concisa com uma síntese natural da vivência.",
                55,
                75,
                ("orientacoes_aprendizado",),
            ),
        ),
    ),
    NarrativeProfile(
        profile_id="B4",
        paragraphs=(
            ParagraphSpec(
                "abertura_avaliacao",
                "Começar por uma observação concreta da avaliação e contextualizar a atividade.",
                110,
                135,
                ("avaliacao_planejamento",),
                uses_context=True,
            ),
            ParagraphSpec(
                "planejamento_preparo",
                "Conectar planejamento profissional, organização e biossegurança.",
                135,
                165,
                ("avaliacao_planejamento", "preparo_biosseguranca_execucao"),
            ),
            ParagraphSpec(
                "execucao_orientacoes",
                "Desenvolver a execução supervisionada e as orientações acompanhadas.",
                150,
                180,
                ("preparo_biosseguranca_execucao", "orientacoes_aprendizado"),
            ),
            ParagraphSpec(
                "aprendizado_fechamento",
                "Fechar com aprendizado específico, sem fórmula genérica de conclusão.",
                80,
                105,
                ("orientacoes_aprendizado",),
            ),
        ),
    ),
    NarrativeProfile(
        profile_id="C6",
        paragraphs=(
            ParagraphSpec(
                "abertura",
                "Abrir com uma cena curta da rotina observada.",
                40,
                55,
                uses_context=True,
            ),
            ParagraphSpec(
                "avaliacao_planejamento",
                "Descrever avaliação e planejamento sem transformar itens em lista.",
                85,
                110,
                ("avaliacao_planejamento",),
            ),
            ParagraphSpec(
                "preparo_biosseguranca",
                "Relatar organização, preparo e biossegurança de forma conectada.",
                100,
                125,
                ("preparo_biosseguranca_execucao",),
            ),
            ParagraphSpec(
                "execucao",
                "Desenvolver o acompanhamento da execução e as decisões do profissional.",
                120,
                150,
                ("preparo_biosseguranca_execucao",),
            ),
            ParagraphSpec(
                "orientacoes_aprendizado",
                "Agrupar orientações observadas e aprendizado técnico.",
                85,
                110,
                ("orientacoes_aprendizado",),
            ),
            ParagraphSpec(
                "fechamento",
                "Encerrar brevemente com síntese da compreensão alcançada.",
                50,
                70,
                ("orientacoes_aprendizado",),
            ),
        ),
    ),
)


def _validate_profile(profile: NarrativeProfile) -> None:
    paragraph_count = len(profile.paragraphs)
    if not MIN_PARAGRAPHS <= paragraph_count <= MAX_PARAGRAPHS:
        raise ValueError(f"perfil {profile.profile_id} tem quantidade inválida de parágrafos")
    if not MIN_TOTAL_WORDS <= profile.min_total_words <= MAX_TOTAL_WORDS:
        raise ValueError(f"perfil {profile.profile_id} tem mínimo total inválido")
    if not MIN_TOTAL_WORDS <= profile.max_total_words <= MAX_TOTAL_WORDS:
        raise ValueError(f"perfil {profile.profile_id} tem máximo total inválido")
    if profile.guaranteed_spread < MIN_GUARANTEED_SPREAD:
        raise ValueError(f"perfil {profile.profile_id} não garante variação de tamanho")

    keys = [paragraph.key for paragraph in profile.paragraphs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"perfil {profile.profile_id} contém chaves de parágrafo duplicadas")

    for paragraph in profile.paragraphs:
        if paragraph.min_words <= 0 or paragraph.max_words < paragraph.min_words:
            raise ValueError(f"perfil {profile.profile_id} contém orçamento inválido")
        unknown_groups = set(paragraph.source_groups) - set(FACT_GROUPS)
        if unknown_groups:
            raise ValueError(
                f"perfil {profile.profile_id} usa grupos desconhecidos: {sorted(unknown_groups)}"
            )


for _profile in PROFILES:
    _validate_profile(_profile)


def profile_for_position(position: int) -> NarrativeProfile:
    """Alterna os perfis A5, B4 e C6 conforme a posição no relatório."""
    if position < 1:
        raise ValueError("position deve ser maior ou igual a 1")
    return PROFILES[(position - 1) % len(PROFILES)]


def build_narrative_plan(activity: EnrichedActivity, position: int) -> NarrativePlan:
    """Cria um plano imutável para uma atividade já validada."""
    return NarrativePlan(
        activity_title=activity.titulo,
        report_type=activity.tipo_relato,
        position=position,
        profile=profile_for_position(position),
    )
