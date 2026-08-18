"""Testes de identidade, variação e limite de recomposição."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from activity_generator import ActivityGenerator
from activity_originality import (
    OriginalityIssue,
    OriginalityReport,
    ReportFingerprint,
    ReportOriginalityRegistry,
    ReportOriginalityRejected,
    ReportOriginalityValidator,
)
from report_identity import build_report_identity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


class SequencedOriginalityValidator:
    def __init__(self, reports: list[OriginalityReport]) -> None:
        self.reports = reports
        self.calls = 0

    def validate(self, candidate_sections, previous_reports=()) -> OriginalityReport:
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return report


class ActivityOriginalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activities = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))[:3]

    def test_report_identity_is_stable_and_ignores_cpf(self) -> None:
        data = {
            "RA_ALUNO": "123",
            "EMAIL_ALUNO": "aluno@example.com",
            "AREA_ESTAGIO": "Estética",
            "MODULO_ESTAGIO": "I",
            "DATA_INICIO_ESTAGIO": "01/02/2026",
            "DATA_FIM_ESTAGIO": "30/04/2026",
            "CPF": "111.111.111-11",
        }
        first = build_report_identity(data)
        second = build_report_identity({**data, "CPF": "999.999.999-99"})
        changed = build_report_identity({**data, "RA_ALUNO": "456"})

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_exact_report_is_rejected(self) -> None:
        sections = (
            "Primeira abertura exclusiva. Conteúdo técnico da atividade.",
            "Segunda abertura exclusiva. Outro conteúdo técnico.",
        )

        report = ReportOriginalityValidator().validate(sections, (sections,))
        codes = {issue.code for issue in report.issues}

        self.assertIn("duplicate_report", codes)
        self.assertIn("repeated_opening", codes)
        self.assertIn("repeated_paragraph", codes)
        self.assertFalse(report.is_acceptable)

    def test_same_report_id_can_be_replaced_reproducibly(self) -> None:
        registry = ReportOriginalityRegistry()
        sections = ("Abertura própria. Conteúdo do relatório.",)
        registry.add("report-a", sections)

        self.assertEqual((), registry.previous_for("report-a"))
        self.assertEqual(1, len(registry.previous_for("report-b")))

    def test_persistent_registry_stores_only_fingerprints(self) -> None:
        sections = ("Abertura privada. Conteúdo original do relatório.",)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "registry.json"
            registry = ReportOriginalityRegistry(path)
            registry.add("report-a", sections)

            stored = path.read_text(encoding="utf-8")
            reloaded = ReportOriginalityRegistry(path)

        self.assertNotIn("Abertura privada", stored)
        self.assertNotIn("Conteúdo original", stored)
        self.assertEqual(1, len(reloaded.reports))
        self.assertEqual((), reloaded.previous_for("report-a"))

    def test_generator_allows_only_one_recomposition(self) -> None:
        rejected = OriginalityReport(
            (OriginalityIssue("duplicate_report", "duplicado"),),
            1.0,
        )
        accepted = OriginalityReport((), 0.40)
        validator = SequencedOriginalityValidator([rejected, accepted])
        generator = ActivityGenerator(
            max_atividades=3,
            report_seed="bounded-repair",
            variant_index=0,
            originality_validator=validator,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            generator.generate(self.activities)

        self.assertEqual(2, validator.calls)
        self.assertEqual(2, generator.last_composition_attempts)

    def test_same_identity_regenerates_the_same_report(self) -> None:
        registry = ReportOriginalityRegistry()
        outputs = []

        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(2):
                generator = ActivityGenerator(
                    max_atividades=3,
                    report_seed="stable-report",
                    variant_index=7,
                    originality_registry=registry,
                )
                outputs.append(generator.generate(self.activities))

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(1, len(registry.reports))

    def test_persistent_similarity_stops_after_two_compositions(self) -> None:
        rejected = OriginalityReport(
            (OriginalityIssue("repeated_paragraph", "repetido"),),
            0.70,
        )
        validator = SequencedOriginalityValidator([rejected])
        generator = ActivityGenerator(
            max_atividades=3,
            report_seed="persistent-rejection",
            variant_index=0,
            originality_validator=validator,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ReportOriginalityRejected) as raised:
                generator.generate(self.activities)

        self.assertEqual(2, validator.calls)
        self.assertEqual(2, raised.exception.attempts)

    def test_twelve_reports_have_no_repeated_opening_or_paragraph(self) -> None:
        registry = ReportOriginalityRegistry()
        fingerprints = []
        maximum_similarity = 0.0

        with contextlib.redirect_stdout(io.StringIO()):
            for variant in range(12):
                generator = ActivityGenerator(
                    max_atividades=3,
                    report_seed=f"batch-report-{variant}",
                    variant_index=variant,
                    originality_registry=registry,
                )
                result = generator.generate(self.activities)
                sections = tuple(result[f"ATV{position}"] for position in range(1, 4))
                fingerprints.append(ReportFingerprint.from_sections(sections))
                maximum_similarity = max(
                    maximum_similarity,
                    generator.last_originality_report.maximum_similarity,
                )
                self.assertLessEqual(generator.last_composition_attempts, 2)
                self.assertTrue(generator.last_originality_report.is_acceptable)
                self.assertTrue(all(not text.startswith("Texto temporário") for text in sections))

        self.assertEqual(12, len(registry.reports))
        self.assertEqual(12, len({item.normalized_hash for item in fingerprints}))
        all_openings = [opening for item in fingerprints for opening in item.opening_hashes]
        all_paragraphs = [paragraph for item in fingerprints for paragraph in item.paragraph_hashes]
        self.assertEqual(len(all_openings), len(set(all_openings)))
        self.assertEqual(len(all_paragraphs), len(set(all_paragraphs)))
        self.assertLessEqual(maximum_similarity, 0.60)


if __name__ == "__main__":
    unittest.main()
