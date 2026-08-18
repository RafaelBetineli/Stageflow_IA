"""Testes da variacao de abertura entre atividades do mesmo relatorio."""

import json
import re
import unittest
from pathlib import Path

from activity_contract import parse_activity_collection
from activity_deterministic_composer import DeterministicActivityComposer
from activity_narrative_planner import build_narrative_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base" / "biomedicina_estetica.json"


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]


def first_paragraph_sentences(text: str) -> list[str]:
    paragraph = re.split(r"\n\s*\n", text.strip(), maxsplit=1)[0]
    return re.split(r"(?<=[.!?])\s+", paragraph)


class ActivityOpeningVariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = json.loads(KNOWLEDGE_BASE.read_text(encoding="utf-8"))
        cls.activities = parse_activity_collection(raw)[:10]

    def test_first_ten_activities_use_distinct_opening_templates(self) -> None:
        composer = DeterministicActivityComposer(
            report_seed="same-report-openings",
            variant_index=4,
        )
        templates = []

        for position, activity in enumerate(self.activities, start=1):
            result = composer.write(
                activity,
                build_narrative_plan(activity, position),
            )
            opening = first_sentence(result.draft.text)
            templates.append(opening.replace(activity.titulo, "{title}"))

        self.assertEqual(len(templates), len(set(templates)))

    def test_technical_opening_does_not_repeat_the_old_formula(self) -> None:
        composer = DeterministicActivityComposer(
            report_seed="technical-opening-proof",
            variant_index=4,
        )
        technical_leads = []

        for position, activity in enumerate(self.activities, start=1):
            result = composer.write(
                activity,
                build_narrative_plan(activity, position),
            )
            sentences = first_paragraph_sentences(result.draft.text)
            self.assertNotIn("O princípio técnico observado é", sentences[1])
            technical_leads.append(sentences[1].split(",", 1)[0])

        self.assertGreaterEqual(len(set(technical_leads)), 8)

    def test_openings_remain_reproducible_for_same_report(self) -> None:
        openings_by_run = []

        for _ in range(2):
            composer = DeterministicActivityComposer(
                report_seed="stable-opening-report",
                variant_index=7,
            )
            openings_by_run.append(
                tuple(
                    first_sentence(
                        composer.write(
                            activity,
                            build_narrative_plan(activity, position),
                        ).draft.text
                    )
                    for position, activity in enumerate(self.activities, start=1)
                )
            )

        self.assertEqual(openings_by_run[0], openings_by_run[1])


if __name__ == "__main__":
    unittest.main()
