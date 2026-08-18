"""Validação determinística dos relatos de atividade compostos pelo sistema."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from activity_contract import EnrichedActivity, FACT_GROUPS
from activity_draft import StructuredDraft
from activity_narrative_planner import MAX_TOTAL_WORDS, MIN_TOTAL_WORDS, NarrativePlan


IssueSeverity = Literal["blocking", "repairable", "warning"]

WORD_PATTERN = re.compile(r"\b\w+(?:[-']\w+)*\b", flags=re.UNICODE)
GENERIC_OPENINGS = frozenset(
    {"acompanhei", "aprendi", "durante", "observei", "percebi", "pude"}
)
CLINICAL_PATTERNS = (
    (
        "guaranteed_claim",
        re.compile(r"\bgarant(?!(?:ia|ias)\b)\w*\b", flags=re.IGNORECASE),
        "afirmação de garantia ou certeza clínica",
    ),
    (
        "effectiveness_claim",
        re.compile(
            r"(?:\b(?:foi|seria|mostrou-se|considerad[oa])\s+(?:eficaz|efetiv[oa])\b|"
            r"\beficácia\s+(?:comprovada|garantida)\b)",
            flags=re.IGNORECASE,
        ),
        "afirmação não autorizada de eficácia",
    ),
    (
        "success_claim",
        re.compile(r"\bsucesso\b", flags=re.IGNORECASE),
        "avaliação não autorizada de sucesso",
    ),
    (
        "result_claim",
        re.compile(
            r"(?:\bresultad\w*\b[^.!?]{0,80}\b(?:satisfat\w*|natural|harmoni\w*|"
            r"perfeit\w*|definit\w*|desejad\w*|imediat\w*)\b|"
            r"\b(?:satisfat\w*|natural|harmoni\w*|perfeit\w*|definit\w*|"
            r"desejad\w*|imediat\w*)\b[^.!?]{0,40}\bresultad\w*\b)",
            flags=re.IGNORECASE,
        ),
        "avaliação não autorizada do resultado",
    ),
    (
        "desired_outcome_claim",
        re.compile(
            r"\b(?:alcanç\w*|ating\w*|obt\w*|promov\w*)\b[^.!?]{0,80}"
            r"\b(?:aparênc\w*|harmoni\w*|proporç\w*|resultad\w*|simetri\w*)\b",
            flags=re.IGNORECASE,
        ),
        "promessa ou finalidade estética apresentada como resultado alcançado",
    ),
    (
        "invented_patient_context",
        re.compile(
            r"\b(?:cliente|paciente)\s+que\s+(?:buscava|desejava|procurava|"
            r"relatou|solicitou)\b",
            flags=re.IGNORECASE,
        ),
        "motivação ou relato do paciente não informado nos dados",
    ),
    (
        "autonomous_action",
        re.compile(
            r"\b(?:eu\s+)?(?:apliquei|conduzi|diagnostiquei|executei|prescrevi|"
            r"realizei|orientei)\b",
            flags=re.IGNORECASE,
        ),
        "ação clínica autônoma atribuída ao estudante",
    ),
    (
        "prompt_leakage",
        re.compile(
            r"\b(?:dados da atividade|fatos permitidos|não invente|estas instruções)\b",
            flags=re.IGNORECASE,
        ),
        "trecho das instruções exposto no relato",
    ),
)
NUMERIC_DETAIL_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ml|mg|ui|unidades?|%|j/cm²|mm)\b",
    flags=re.IGNORECASE,
)
STYLE_PATTERNS = (
    (
        "generic_learning_formula",
        re.compile(
            r"\b(?:foi|é) fundamental para (?:entender|compreender)\b",
            flags=re.IGNORECASE,
        ),
        "fórmula genérica de aprendizado",
    ),
    (
        "inflated_reaction",
        re.compile(
            r"\b(?:fiquei impressionad[oa]|extremamente enriquecedor[ao]|"
            r"experiência enriquecedora)\b",
            flags=re.IGNORECASE,
        ),
        "reação pessoal exagerada ou genérica",
    ),
)


def count_words(text: str) -> int:
    """Conta palavras de modo estável para validação e testes."""
    return len(WORD_PATTERN.findall(text))


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(WORD_PATTERN.findall(without_marks))


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    paragraph_key: str | None = None


@dataclass(frozen=True)
class DraftValidationReport:
    issues: tuple[ValidationIssue, ...]
    paragraph_word_counts: tuple[tuple[str, int], ...]

    @property
    def total_words(self) -> int:
        return sum(count for _, count in self.paragraph_word_counts)

    @property
    def blocking_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "blocking")

    @property
    def repairable_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "repairable")

    @property
    def warning_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def paragraphs_to_repair(self) -> tuple[str, ...]:
        selected: list[str] = []
        for issue in self.issues:
            if (
                issue.severity in {"blocking", "repairable"}
                and issue.paragraph_key
                and issue.paragraph_key not in selected
            ):
                selected.append(issue.paragraph_key)
        return tuple(selected)

    @property
    def is_acceptable(self) -> bool:
        return not self.blocking_issues and not self.repairable_issues


class ActivityDraftValidator:
    """Aplica critérios clínicos e estruturais sem consultar o modelo."""

    def validate(
        self,
        activity: EnrichedActivity,
        plan: NarrativePlan,
        draft: StructuredDraft,
    ) -> DraftValidationReport:
        expected_keys = tuple(spec.key for spec in plan.paragraphs)
        actual_keys = tuple(key for key, _ in draft.paragraphs)
        counts = tuple((key, count_words(text)) for key, text in draft.paragraphs)
        count_by_key = dict(counts)
        issues: list[ValidationIssue] = []

        if actual_keys != expected_keys:
            issues.append(
                ValidationIssue(
                    "paragraph_structure",
                    "blocking",
                    "quantidade ou ordem de parágrafos diferente do plano",
                )
            )
            return DraftValidationReport(tuple(issues), counts)

        for spec in plan.paragraphs:
            count = count_by_key[spec.key]
            if count < spec.min_words - 20:
                issues.append(
                    ValidationIssue(
                        "paragraph_too_short",
                        "repairable",
                        f"parágrafo com {count} palavras; precisa de maior desenvolvimento",
                        spec.key,
                    )
                )
            elif count > spec.max_words + 20:
                issues.append(
                    ValidationIssue(
                        "paragraph_too_long",
                        "repairable",
                        f"parágrafo com {count} palavras; precisa ser condensado",
                        spec.key,
                    )
                )

        total_words = sum(count_by_key.values())
        if total_words < MIN_TOTAL_WORDS:
            target = max(
                plan.paragraphs,
                key=lambda spec: spec.target_words - count_by_key[spec.key],
            )
            issues.append(
                ValidationIssue(
                    "total_too_short",
                    "repairable",
                    f"relato com {total_words} palavras; mínimo esperado é {MIN_TOTAL_WORDS}",
                    target.key,
                )
            )
        elif total_words > MAX_TOTAL_WORDS:
            target = max(
                plan.paragraphs,
                key=lambda spec: count_by_key[spec.key] - spec.target_words,
            )
            issues.append(
                ValidationIssue(
                    "total_too_long",
                    "repairable",
                    f"relato com {total_words} palavras; máximo esperado é {MAX_TOTAL_WORDS}",
                    target.key,
                )
            )

        paragraph_sizes = tuple(count_by_key.values())
        if len(paragraph_sizes) >= 4 and max(paragraph_sizes) - min(paragraph_sizes) < 30:
            target = max(
                plan.paragraphs,
                key=lambda spec: spec.target_words - count_by_key[spec.key],
            )
            issues.append(
                ValidationIssue(
                    "uniform_paragraphs",
                    "repairable",
                    "parágrafos excessivamente uniformes; a variação é inferior a 30 palavras",
                    target.key,
                )
            )

        allowed_source = " ".join(
            [activity.contexto_seguro]
            + [
                fact
                for group in FACT_GROUPS
                for fact in activity.fatos_permitidos.get(group)
            ]
        )
        normalized_allowed = _normalize(allowed_source)
        normalized_title = _normalize(activity.titulo)
        seen_openings: set[str] = set()
        title_seen = False

        for key, text in draft.paragraphs:
            normalized_text = _normalize(text)
            words = normalized_text.split()
            opening = words[0] if words else ""

            if opening in GENERIC_OPENINGS:
                if opening in seen_openings:
                    issues.append(
                        ValidationIssue(
                            "repeated_opening",
                            "repairable",
                            f"abertura repetida com '{opening}'",
                            key,
                        )
                    )
                seen_openings.add(opening)

            title_occurrences = (
                normalized_text.count(normalized_title) if normalized_title else 0
            )
            if title_occurrences and (title_seen or title_occurrences > 1):
                issues.append(
                    ValidationIssue(
                        "repeated_full_title",
                        "repairable",
                        "nome completo da atividade repetido após a abertura",
                        key,
                    )
                )
            if title_occurrences:
                title_seen = True

            for code, pattern, message in CLINICAL_PATTERNS:
                if pattern.search(text):
                    issues.append(ValidationIssue(code, "blocking", message, key))

            for match in NUMERIC_DETAIL_PATTERN.finditer(text):
                if _normalize(match.group()) not in normalized_allowed:
                    issues.append(
                        ValidationIssue(
                            "invented_numeric_detail",
                            "blocking",
                            "dose, concentração ou medida numérica sem apoio nos dados",
                            key,
                        )
                    )
                    break

            for code, pattern, message in STYLE_PATTERNS:
                if pattern.search(text):
                    issues.append(ValidationIssue(code, "warning", message, key))

        unique: list[ValidationIssue] = []
        seen: set[tuple[str, str | None]] = set()
        for issue in issues:
            identity = (issue.code, issue.paragraph_key)
            if identity not in seen:
                unique.append(issue)
                seen.add(identity)

        return DraftValidationReport(tuple(unique), counts)
