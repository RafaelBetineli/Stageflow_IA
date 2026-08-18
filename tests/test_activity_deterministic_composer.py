"""Testes da composição determinística de atividades."""

import json
import unittest
from pathlib import Path

from activity_contract import FACT_GROUPS, parse_activity_collection
from activity_deterministic_composer import DeterministicActivityComposer
from activity_narrative_planner import build_narrative_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


class DeterministicComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activities = parse_activity_collection(raw)

    def test_all_activities_are_valid_without_model_calls(self) -> None:
        for variant in range(12):
            composer = DeterministicActivityComposer(
                report_seed=f"validation-{variant}",
                variant_index=variant,
            )
            for position, activity in enumerate(self.activities, start=1):
                with self.subTest(
                    variant=variant,
                    position=position,
                    title=activity.titulo,
                ):
                    plan = build_narrative_plan(activity, position)
                    result = composer.write(activity, plan)

                    self.assertTrue(result.final_report.is_acceptable)
                    self.assertEqual(len(plan.paragraphs), len(result.draft.paragraphs))
                    self.assertGreaterEqual(result.final_report.total_words, 420)
                    self.assertLessEqual(result.final_report.total_words, 700)

    def test_each_allowed_fact_appears_once(self) -> None:
        composer = DeterministicActivityComposer()

        for position, activity in enumerate(self.activities, start=1):
            with self.subTest(position=position, title=activity.titulo):
                result = composer.write(
                    activity,
                    build_narrative_plan(activity, position),
                )
                normalized_text = result.draft.text.casefold()
                for group in FACT_GROUPS:
                    for fact in activity.fatos_permitidos.get(group):
                        self.assertEqual(1, normalized_text.count(fact.casefold()), fact)


if __name__ == "__main__":
    unittest.main()
