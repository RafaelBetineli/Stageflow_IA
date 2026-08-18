"""Testes das validacoes estruturais, estilisticas e clinicas do relato."""

import json
import unittest
from pathlib import Path

from activity_contract import parse_activity_collection
from activity_draft import StructuredDraft
from activity_draft_validator import ActivityDraftValidator
from activity_narrative_planner import build_narrative_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


def paragraph_with_words(opening: str, count: int, phrase: str = "") -> str:
    tokens = opening.split() + phrase.split()
    if len(tokens) > count:
        raise ValueError("conteudo inicial maior que o paragrafo")
    tokens.extend(["conteudo"] * (count - len(tokens)))
    return " ".join(tokens) + "."


def valid_paragraphs() -> list[tuple[str, str]]:
    return [
        ("abertura", paragraph_with_words("Nesta atividade", 55)),
        ("avaliacao_planejamento", paragraph_with_words("Na avaliacao", 112)),
        ("preparo_execucao", paragraph_with_words("Antes do procedimento", 150)),
        ("orientacoes_aprendizado", paragraph_with_words("As orientacoes", 125)),
        ("fechamento", paragraph_with_words("Ao final", 65)),
    ]


class ActivityDraftValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activity = parse_activity_collection(raw)[0]
        cls.plan = build_narrative_plan(cls.activity, 1)
        cls.validator = ActivityDraftValidator()

    def test_valid_draft_is_accepted(self) -> None:
        report = self.validator.validate(
            self.activity,
            self.plan,
            StructuredDraft(tuple(valid_paragraphs())),
        )

        self.assertTrue(report.is_acceptable)
        self.assertEqual(507, report.total_words)
        self.assertEqual((), report.paragraphs_to_repair)

    def test_uniform_paragraphs_are_rejected(self) -> None:
        paragraphs = [
            (spec.key, paragraph_with_words(f"Inicio {index}", 90))
            for index, spec in enumerate(self.plan.paragraphs)
        ]

        report = self.validator.validate(
            self.activity,
            self.plan,
            StructuredDraft(tuple(paragraphs)),
        )

        self.assertIn("uniform_paragraphs", {issue.code for issue in report.issues})
        self.assertFalse(report.is_acceptable)

    def test_clinical_claim_and_repeated_opening_are_detected(self) -> None:
        paragraphs = valid_paragraphs()
        paragraphs[1] = (
            "avaliacao_planejamento",
            paragraph_with_words("Acompanhei a avaliacao", 112),
        )
        paragraphs[2] = (
            "preparo_execucao",
            paragraph_with_words("Acompanhei o preparo", 150),
        )
        paragraphs[3] = (
            "orientacoes_aprendizado",
            paragraph_with_words(
                "As orientacoes",
                125,
                "garantiram um resultado natural",
            ),
        )

        report = self.validator.validate(
            self.activity,
            self.plan,
            StructuredDraft(tuple(paragraphs)),
        )
        codes = {issue.code for issue in report.issues}

        self.assertIn("repeated_opening", codes)
        self.assertIn("guaranteed_claim", codes)
        self.assertIn("result_claim", codes)

    def test_invented_context_and_desired_outcome_are_blocking(self) -> None:
        paragraphs = valid_paragraphs()
        paragraphs[1] = (
            "avaliacao_planejamento",
            paragraph_with_words(
                "Na avaliacao",
                112,
                "a paciente que procurava alcançar proporções desejadas foi recebida",
            ),
        )

        report = self.validator.validate(
            self.activity,
            self.plan,
            StructuredDraft(tuple(paragraphs)),
        )
        codes = {issue.code for issue in report.blocking_issues}

        self.assertIn("invented_patient_context", codes)
        self.assertIn("desired_outcome_claim", codes)

    def test_style_warning_does_not_reject_draft(self) -> None:
        paragraphs = valid_paragraphs()
        paragraphs[4] = (
            "fechamento",
            paragraph_with_words(
                "Ao final",
                65,
                "foi fundamental para entender a rotina",
            ),
        )

        report = self.validator.validate(
            self.activity,
            self.plan,
            StructuredDraft(tuple(paragraphs)),
        )

        self.assertTrue(report.is_acceptable)
        self.assertEqual(1, len(report.warning_issues))
        self.assertEqual((), report.paragraphs_to_repair)


if __name__ == "__main__":
    unittest.main()
