"""Testes do ponto único de integração do pipeline de atividades."""

import json
import re
import unittest
from dataclasses import dataclass
from pathlib import Path

from activity_draft_validator import DraftValidationReport
from activity_deterministic_composer import DeterministicActivityComposer
from activity_draft import StructuredDraft
from activity_generator import ActivityGenerationError, ActivityGenerator
from activity_originality import ReportOriginalityRegistry
from activity_pipeline import ActivityPipeline
from activity_repository import ActivityRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


@dataclass
class RecordedCall:
    title: str
    profile_id: str
    position: int


@dataclass(frozen=True)
class RecordedWritingResult:
    draft: StructuredDraft
    final_report: DraftValidationReport
    citation_ids: tuple[str, ...] = ()


class RecordingWriter:
    def __init__(self, *, fail_positions: set[int] | None = None) -> None:
        self.fail_positions = fail_positions or set()
        self.calls: list[RecordedCall] = []

    def write(self, activity, plan) -> RecordedWritingResult:
        self.calls.append(
            RecordedCall(activity.titulo, plan.profile.profile_id, plan.position)
        )
        if plan.position in self.fail_positions:
            raise RuntimeError("falha simulada")

        draft = StructuredDraft(((plan.paragraphs[0].key, f"Relato {activity.titulo}"),))
        report = DraftValidationReport((), ((plan.paragraphs[0].key, 500),))
        return RecordedWritingResult(draft, report)


class SequencedWriterGenerator(ActivityGenerator):
    def __init__(self, writers: tuple[RecordingWriter, ...], **kwargs) -> None:
        self._writers = writers
        super().__init__(**kwargs)

    def _build_default_writer(self, *, attempt: int) -> RecordingWriter:
        return self._writers[min(attempt, len(self._writers) - 1)]


class ActivityGeneratorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activities = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))

    def test_first_three_positions_use_a5_b4_and_c6(self) -> None:
        writer = RecordingWriter()
        generator = ActivityGenerator(max_atividades=3, writer=writer)

        result = generator.generate(self.activities[:3])

        self.assertEqual(["A5", "B4", "C6"], [call.profile_id for call in writer.calls])
        self.assertEqual([1, 2, 3], [call.position for call in writer.calls])
        self.assertEqual("Relato Preenchimento labial", result["ATV1"])
        self.assertEqual("Relato Toxina botulínica", result["ATV2"])
        self.assertEqual("Relato Bioestimulador de colágeno", result["ATV3"])

    def test_failure_stops_generation_without_publishing_fallback(self) -> None:
        writer = RecordingWriter(fail_positions={1})
        generator = ActivityGenerator(max_atividades=2, writer=writer)

        with self.assertRaisesRegex(ActivityGenerationError, "ATV1"):
            generator.generate(self.activities[:2])

        self.assertEqual(1, len(writer.calls))

    def test_default_composer_uses_one_bounded_structural_retry(self) -> None:
        first = RecordingWriter(fail_positions={1})
        second = RecordingWriter()
        generator = SequencedWriterGenerator(
            (first, second),
            max_atividades=2,
            report_seed="structural-retry",
        )

        result = generator.generate(self.activities[:2])

        self.assertTrue(result["ATV1"])
        self.assertEqual(1, len(first.calls))
        self.assertEqual(2, len(second.calls))
        self.assertEqual(2, generator.last_composition_attempts)

    def test_missing_positions_remain_empty(self) -> None:
        writer = RecordingWriter()
        generator = ActivityGenerator(max_atividades=3, writer=writer)

        result = generator.generate(self.activities[:1])

        self.assertTrue(result["ATV1"])
        self.assertEqual("", result["ATV2"])
        self.assertEqual("", result["ATV3"])

    def test_real_pipeline_uses_deterministic_composer(self) -> None:
        repository = ActivityRepository(str(KNOWLEDGE_BASE))
        pipeline = ActivityPipeline(repository, area_estagio="Estética")
        titles = [activity["titulo"] for activity in self.activities[:3]]

        result = pipeline.build(titles)

        self.assertIsInstance(pipeline.generator.writer, DeterministicActivityComposer)
        for position, paragraph_count in enumerate((5, 4, 6), start=1):
            text = result[f"ATV{position}"]
            paragraphs = [
                paragraph
                for paragraph in re.split(r"\n\s*\n", text.strip())
                if paragraph
            ]
            self.assertFalse(text.startswith("Texto temporário"))
            self.assertGreaterEqual(len(text.split()), 420)
            self.assertEqual(paragraph_count, len(paragraphs))
        self.assertEqual("", result["ATV4"])

    def test_each_project_knowledge_base_builds_without_fallback(self) -> None:
        for path in sorted((PROJECT_ROOT / "knowledge_base").glob("*.json")):
            with self.subTest(knowledge_base=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                titles = [activity["titulo"] for activity in raw[:3]]
                pipeline = ActivityPipeline(
                    ActivityRepository(str(path)),
                    area_estagio=path.stem,
                    report_seed=f"integration:{path.stem}",
                    originality_registry=ReportOriginalityRegistry(),
                )

                result = pipeline.build(titles)

                for position in range(1, 4):
                    text = result[f"ATV{position}"]
                    self.assertFalse(text.startswith("Texto temporário"))
                    self.assertGreaterEqual(len(text.split()), 420)

                self.assertTrue(result["REFERENCIAS"])


if __name__ == "__main__":
    unittest.main()
