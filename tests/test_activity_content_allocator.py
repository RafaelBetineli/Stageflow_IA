"""Testes da alocacao deterministica de fatos entre paragrafos."""

import json
import unittest
from pathlib import Path

from activity_content_allocator import ContentAllocationError, allocate_activity_content
from activity_contract import parse_activity_collection
from activity_narrative_planner import NarrativePlan, build_narrative_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


class ContentAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activities = parse_activity_collection(raw)

    def _plan(self, activity_index: int = 0, position: int = 1) -> NarrativePlan:
        return build_narrative_plan(self.activities[activity_index], position)

    def test_each_fact_is_allocated_exactly_once(self) -> None:
        for position, activity in enumerate(self.activities, start=1):
            with self.subTest(activity=activity.titulo):
                plan = build_narrative_plan(activity, position)
                allocations = allocate_activity_content(activity, plan)
                allocated_facts = [fact for item in allocations for fact in item.facts]
                source_facts = [
                    fact
                    for group in (
                        "avaliacao_planejamento",
                        "preparo_biosseguranca_execucao",
                        "orientacoes_aprendizado",
                    )
                    for fact in activity.fatos_permitidos.get(group)
                ]

                self.assertCountEqual(source_facts, allocated_facts)
                self.assertEqual(len(allocated_facts), len(set(allocated_facts)))

    def test_context_is_used_only_by_planned_paragraphs(self) -> None:
        allocations = allocate_activity_content(self.activities[0], self._plan())

        for allocation in allocations:
            with self.subTest(paragraph=allocation.spec.key):
                self.assertEqual(allocation.spec.uses_context, allocation.context is not None)

    def test_shared_groups_keep_source_order_in_contiguous_blocks(self) -> None:
        activity = self.activities[1]
        allocations = allocate_activity_content(
            activity,
            build_narrative_plan(activity, 2),
        )
        source = list(activity.fatos_permitidos.preparo_biosseguranca_execucao)
        allocated = [
            fact
            for item in allocations
            for fact in item.facts
            if fact in source
        ]

        self.assertEqual(source, allocated)
        owners = [
            item.spec.key
            for item in allocations
            for fact in item.facts
            if fact in source
        ]
        self.assertEqual(sorted(owners, key=owners.index), owners)

    def test_plan_for_another_activity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContentAllocationError, "outra atividade"):
            allocate_activity_content(self.activities[1], self._plan())


if __name__ == "__main__":
    unittest.main()
