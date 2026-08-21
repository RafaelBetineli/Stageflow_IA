"""Testes da homologação de originalidade sem persistência de textos."""

import json
import unittest
from pathlib import Path

from originality_audit import (
    adjusted_ngram_signature,
    normalize_narrative_for_audit,
    run_project_audit,
    signature_jaccard,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OriginalityAuditTests(unittest.TestCase):
    def test_normalization_removes_citation_and_required_phrase(self) -> None:
        left = (
            "A conferência de lote orientou a etapa (ANVISA, 2022). "
            "Mantive atenção ao registro realizado pela equipe."
        )
        right = (
            "A conferência de lote orientou a etapa (WHO, 2024b). "
            "Mantive atenção ao registro realizado pela equipe."
        )

        normalized_left = normalize_narrative_for_audit(
            left,
            excluded_phrases=("conferência de lote",),
        )
        normalized_right = normalize_narrative_for_audit(
            right,
            excluded_phrases=("conferência de lote",),
        )

        self.assertEqual(normalized_left, normalized_right)
        self.assertNotIn("anvisa", normalized_left)
        self.assertNotIn("conferencia de lote", normalized_left)

    def test_adjusted_signature_preserves_narrative_difference(self) -> None:
        first = adjusted_ngram_signature(
            "A equipe conferiu o material antes da rotina técnica.",
            size=3,
        )
        second = adjusted_ngram_signature(
            "O registro acadêmico destacou outra forma de acompanhamento.",
            size=3,
        )

        self.assertLess(signature_jaccard(first, second), 0.20)

    def test_all_project_areas_pass_a_privacy_safe_audit(self) -> None:
        summary = run_project_audit(
            PROJECT_ROOT / "knowledge_base",
            reports_per_area=8,
        )
        serialized = json.dumps(summary.to_dict(), ensure_ascii=False)

        self.assertTrue(summary.passed)
        self.assertEqual(5, len(summary.areas))
        self.assertNotIn("Preenchimento labial", serialized)
        self.assertNotIn("contexto_seguro", serialized)
        for area in summary.areas:
            with self.subTest(area=area.area):
                self.assertEqual(
                    area.available_activities,
                    area.covered_activities,
                )
                self.assertEqual(area.reports_generated, area.unique_reports)
                self.assertEqual(area.activities_generated, area.unique_activities)
                self.assertEqual(area.activities_generated, area.unique_openings)
                self.assertEqual(area.paragraphs_generated, area.unique_paragraphs)
                self.assertLessEqual(area.maximum_adjusted_similarity, 0.65)


if __name__ == "__main__":
    unittest.main()
