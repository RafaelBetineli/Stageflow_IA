"""Testes de integridade entre knowledge base, citacoes e referencias."""

import json
import unittest
from pathlib import Path

from activity_bibliography import BibliographyCatalog, BibliographyError
from activity_contract import parse_activity_collection
from activity_deterministic_composer import DeterministicActivityComposer
from activity_narrative_planner import build_narrative_plan
from activity_pipeline import ActivityPipeline
from activity_repository import ActivityRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"
REFERENCE_CATALOG = (
    PROJECT_ROOT / "knowledge_base" / "references" / "biomedicina_estetica.json"
)


class ActivityBibliographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activities = parse_activity_collection(raw)
        cls.catalog = BibliographyCatalog.from_file(REFERENCE_CATALOG)

    def test_all_activity_reference_ids_exist(self) -> None:
        for activity in self.activities:
            with self.subTest(title=activity.titulo):
                self.catalog.validate_activity_ids(activity.referencias_ids)

    def test_all_activities_receive_a_resolved_inline_citation(self) -> None:
        composer = DeterministicActivityComposer(
            bibliography_catalog=self.catalog,
            report_seed="all-citations-proof",
        )

        for position, activity in enumerate(self.activities, start=1):
            with self.subTest(position=position, title=activity.titulo):
                result = composer.write(
                    activity,
                    build_narrative_plan(activity, position),
                )
                self.assertEqual(1, len(result.citation_ids))
                citation = self.catalog.inline_citation(result.citation_ids[0])
                self.assertEqual(1, result.draft.text.count(citation))

    def test_pipeline_cites_and_lists_only_used_references(self) -> None:
        repository = ActivityRepository(str(KNOWLEDGE_BASE))
        pipeline = ActivityPipeline(
            repository,
            area_estagio="Estetica",
            report_seed="bibliography-proof",
        )
        selected = [activity.titulo for activity in self.activities[:3]]

        result = pipeline.build(selected)
        bibliography = result["REFERENCIAS"]

        self.assertEqual(3, len(pipeline.generator.last_citation_ids))
        for position, reference_id in enumerate(
            pipeline.generator.last_citation_ids,
            start=1,
        ):
            reference = self.catalog.require(reference_id)
            self.assertIn(reference.inline_citation, result[f"ATV{position}"])
            self.assertEqual(1, bibliography.count(reference.reference))

    def test_repeated_source_is_deduplicated_in_bibliography(self) -> None:
        reference_id = "signorini_2016_ha_fillers"
        reference = self.catalog.require(reference_id)
        bibliography = self.catalog.format_references((reference_id, reference_id))

        self.assertEqual(reference.reference, bibliography)

    def test_activity_without_inline_citation_is_rejected(self) -> None:
        with self.assertRaisesRegex(BibliographyError, "nao contem citacao"):
            self.catalog.validate_usage(
                ("Relato sem marcador autor-data.",),
                ("signorini_2016_ha_fillers",),
            )

    def test_unknown_reference_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(BibliographyError, "inexistente"):
            self.catalog.require("fonte_inventada_2099")


if __name__ == "__main__":
    unittest.main()
