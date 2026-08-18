"""Provas de escala e persistencia da originalidade por atividade."""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from activity_draft_validator import count_words
from activity_generator import ActivityGenerator
from activity_originality import (
    ActivityFingerprint,
    ActivityOriginalityValidator,
    ReportFingerprint,
    ReportOriginalityRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


class ActivityOriginalityScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activities = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))[:3]

    def test_duplicate_activity_is_rejected(self) -> None:
        text = "Abertura exclusiva da atividade.\n\nParagrafo tecnico completo."
        fingerprint = ActivityFingerprint.from_activity("Atividade exemplo", text)

        report = ActivityOriginalityValidator().validate(
            fingerprint,
            (fingerprint,),
        )
        codes = {issue.code for issue in report.issues}

        self.assertIn("duplicate_activity", codes)
        self.assertIn("repeated_activity_opening", codes)
        self.assertIn("repeated_activity_paragraph", codes)
        self.assertIn("excessive_activity_similarity", codes)

    def test_registry_persists_only_activity_fingerprints(self) -> None:
        title = "Preenchimento labial confidencial"
        text = "Abertura privada.\n\nConteudo privado do relatorio."

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "registry.json"
            registry = ReportOriginalityRegistry(path)
            registry.add("report-a", (text,), ((title, text),))
            stored = path.read_text(encoding="utf-8")
            reloaded = ReportOriginalityRegistry(path)

        self.assertNotIn(title, stored)
        self.assertNotIn("Abertura privada", stored)
        self.assertNotIn("Conteudo privado", stored)
        self.assertEqual(
            1,
            len(reloaded.previous_activities_for("report-b", title)),
        )
        self.assertEqual(
            (),
            reloaded.previous_activities_for("report-b", "Outro procedimento"),
        )

    def test_version_one_registry_is_migrated_on_next_save(self) -> None:
        old_text = "Relato salvo antes da comparacao por atividade."
        old_fingerprint = ReportFingerprint.from_sections((old_text,))

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "registry.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reports": {"old-report": old_fingerprint.to_dict()},
                    }
                ),
                encoding="utf-8",
            )
            registry = ReportOriginalityRegistry(path)
            self.assertEqual(1, len(registry.reports))
            self.assertEqual(
                (),
                registry.previous_activities_for("new-report", "Atividade"),
            )

            registry.add(
                "new-report",
                ("Novo relato.",),
                (("Atividade", "Novo relato."),),
            )
            migrated = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(2, migrated["version"])
        self.assertIn("activities", migrated["reports"]["old-report"])
        self.assertIn("activities", migrated["reports"]["new-report"])

    def test_one_hundred_reports_with_same_activities_are_acceptable(self) -> None:
        registry = ReportOriginalityRegistry()
        report_fingerprints = []
        activity_fingerprints: dict[str, list[ActivityFingerprint]] = {
            activity["titulo"]: [] for activity in self.activities
        }
        maximum_similarity = 0.0

        with contextlib.redirect_stdout(io.StringIO()):
            for variant in range(100):
                report_seed = hashlib.sha256(
                    f"scale-report-{variant}".encode("utf-8")
                ).hexdigest()
                generator = ActivityGenerator(
                    max_atividades=3,
                    report_seed=report_seed,
                    variant_index=int(report_seed[:16], 16),
                    originality_registry=registry,
                )
                result = generator.generate(self.activities)
                sections = tuple(result[f"ATV{position}"] for position in range(1, 4))
                report_fingerprints.append(ReportFingerprint.from_sections(sections))
                maximum_similarity = max(
                    maximum_similarity,
                    generator.last_originality_report.maximum_similarity,
                )

                self.assertLessEqual(generator.last_composition_attempts, 2)
                self.assertTrue(generator.last_originality_report.is_acceptable)
                for activity, text in zip(self.activities, sections):
                    self.assertGreaterEqual(count_words(text), 420)
                    self.assertLessEqual(count_words(text), 700)
                    activity_fingerprints[activity["titulo"]].append(
                        ActivityFingerprint.from_activity(activity["titulo"], text)
                    )

        self.assertEqual(100, len(registry.reports))
        self.assertEqual(100, len({item.normalized_hash for item in report_fingerprints}))
        self.assertLessEqual(maximum_similarity, 0.65)

        for fingerprints in activity_fingerprints.values():
            openings = [item.opening_hash for item in fingerprints]
            paragraphs = [
                paragraph
                for item in fingerprints
                for paragraph in item.paragraph_hashes
            ]
            self.assertEqual(100, len({item.normalized_hash for item in fingerprints}))
            self.assertEqual(len(openings), len(set(openings)))
            self.assertEqual(len(paragraphs), len(set(paragraphs)))


if __name__ == "__main__":
    unittest.main()
