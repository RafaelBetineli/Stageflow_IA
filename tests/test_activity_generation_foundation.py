"""Testes da fundação determinística do novo gerador de atividades."""

import copy
import json
import unittest
from pathlib import Path

from activity_contract import ActivityContractError, parse_activity_collection
from activity_narrative_planner import (
    MAX_TOTAL_WORDS,
    MIN_GUARANTEED_SPREAD,
    MIN_TOTAL_WORDS,
    PROFILES,
    build_narrative_plan,
    profile_for_position,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


class ActivityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_activities = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))

    def test_real_knowledge_base_satisfies_contract(self) -> None:
        activities = parse_activity_collection(self.raw_activities)

        self.assertEqual(22, len(activities))
        self.assertEqual("Preenchimento labial", activities[0].titulo)

    def test_all_project_knowledge_bases_satisfy_contract(self) -> None:
        for path in sorted((PROJECT_ROOT / "knowledge_base").glob("*.json")):
            with self.subTest(knowledge_base=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(parse_activity_collection(raw))

    def test_unknown_activity_field_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw_activities[:1])
        raw[0]["campo_inesperado"] = "valor"

        with self.assertRaisesRegex(ActivityContractError, "campos desconhecidos"):
            parse_activity_collection(raw)

    def test_residual_citation_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw_activities[:1])
        raw[0]["contexto_seguro"] += " [cite: 1]"

        with self.assertRaisesRegex(ActivityContractError, "citação residual"):
            parse_activity_collection(raw)

    def test_duplicate_title_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw_activities[:2])
        raw[1]["titulo"] = raw[0]["titulo"].upper()

        with self.assertRaisesRegex(ActivityContractError, "título duplicado"):
            parse_activity_collection(raw)

    def test_insufficient_fact_group_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw_activities[:1])
        raw[0]["fatos_permitidos"]["avaliacao_planejamento"] = ["um"]

        with self.assertRaisesRegex(ActivityContractError, "pelo menos 2"):
            parse_activity_collection(raw)


class NarrativePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activities = parse_activity_collection(raw)

    def test_profiles_have_four_five_and_six_paragraphs(self) -> None:
        counts = {profile.profile_id: len(profile.paragraphs) for profile in PROFILES}

        self.assertEqual({"A5": 5, "B4": 4, "C6": 6}, counts)

    def test_profile_budgets_satisfy_global_limits(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile.profile_id):
                self.assertGreaterEqual(profile.min_total_words, MIN_TOTAL_WORDS)
                self.assertLessEqual(profile.max_total_words, MAX_TOTAL_WORDS)
                self.assertGreaterEqual(profile.guaranteed_spread, MIN_GUARANTEED_SPREAD)

    def test_profiles_cycle_by_report_position(self) -> None:
        ids = [profile_for_position(position).profile_id for position in range(1, 7)]

        self.assertEqual(["A5", "B4", "C6", "A5", "B4", "C6"], ids)

    def test_invalid_position_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "maior ou igual a 1"):
            profile_for_position(0)

    def test_all_real_activities_receive_a_plan(self) -> None:
        plans = [
            build_narrative_plan(activity, position)
            for position, activity in enumerate(self.activities, start=1)
        ]

        self.assertEqual(len(self.activities), len(plans))
        self.assertTrue(all(plan.activity_title for plan in plans))
        self.assertTrue(all(plan.report_type for plan in plans))


if __name__ == "__main__":
    unittest.main()
