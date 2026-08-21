"""Homologa a diversidade dos relatos sem persistir conteúdo textual."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from activity_generator import ActivityGenerator
from activity_originality import (
    ActivityFingerprint,
    ReportFingerprint,
    ReportOriginalityRegistry,
    normalize_for_similarity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_BASE_DIRECTORY = PROJECT_ROOT / "knowledge_base"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "originality_audit.json"
INLINE_CITATION_PATTERN = re.compile(
    r"\([^()\n]{1,160},\s*\d{4}[a-z]?\)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class AreaAuditSummary:
    area: str
    available_activities: int
    covered_activities: int
    reports_generated: int
    activities_generated: int
    unique_reports: int
    unique_activities: int
    unique_openings: int
    paragraphs_generated: int
    unique_paragraphs: int
    recompositions: int
    maximum_runtime_similarity: float
    maximum_adjusted_similarity: float
    passed: bool


@dataclass(frozen=True)
class ProjectAuditSummary:
    schema_version: int
    reports_per_area: int
    activities_per_report: int
    maximum_adjusted_jaccard: float
    areas: tuple[AreaAuditSummary, ...]

    @property
    def passed(self) -> bool:
        return all(area.passed for area in self.areas)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy": {
                "reports_per_area": self.reports_per_area,
                "activities_per_report": self.activities_per_report,
                "maximum_adjusted_jaccard": self.maximum_adjusted_jaccard,
            },
            "passed": self.passed,
            "areas": [asdict(area) for area in self.areas],
        }


def _normalized_required_phrases(activity: Mapping[str, object]) -> tuple[str, ...]:
    phrases: list[str] = []
    for field in ("titulo", "categoria", "contexto_seguro"):
        value = activity.get(field)
        if isinstance(value, str) and value.strip():
            phrases.append(value)

    terms = activity.get("termos_permitidos")
    if isinstance(terms, list):
        phrases.extend(term for term in terms if isinstance(term, str))

    facts = activity.get("fatos_permitidos")
    if isinstance(facts, dict):
        for values in facts.values():
            if isinstance(values, list):
                phrases.extend(value for value in values if isinstance(value, str))

    normalized = {
        normalize_for_similarity(phrase)
        for phrase in phrases
        if normalize_for_similarity(phrase)
    }
    return tuple(sorted(normalized, key=lambda value: (-len(value), value)))


def normalize_narrative_for_audit(
    text: str,
    *,
    excluded_phrases: Iterable[str] = (),
) -> str:
    """Remove citações e conteúdo fixo antes de medir a variação narrativa."""
    normalized = normalize_for_similarity(INLINE_CITATION_PATTERN.sub(" ", text))
    exclusions = {
        normalize_for_similarity(phrase)
        for phrase in excluded_phrases
        if normalize_for_similarity(phrase)
    }
    for phrase in sorted(exclusions, key=lambda value: (-len(value), value)):
        normalized = re.sub(
            rf"(?<!\w){re.escape(phrase)}(?!\w)",
            " ",
            normalized,
        )
    return " ".join(normalized.split())


def adjusted_ngram_signature(
    text: str,
    *,
    excluded_phrases: Iterable[str] = (),
    size: int = 5,
) -> frozenset[tuple[str, ...]]:
    if size < 1:
        raise ValueError("size deve ser positivo")
    words = normalize_narrative_for_audit(
        text,
        excluded_phrases=excluded_phrases,
    ).split()
    if len(words) < size:
        return frozenset({tuple(words)}) if words else frozenset()
    return frozenset(
        tuple(words[index : index + size])
        for index in range(len(words) - size + 1)
    )


def signature_jaccard(
    left: frozenset[tuple[str, ...]],
    right: frozenset[tuple[str, ...]],
) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _profile_aligned_selection(
    activities: Sequence[dict],
    *,
    report_index: int,
    count: int,
) -> list[dict]:
    selected: list[dict] = []
    for position in range(count):
        candidates = activities[position::3]
        if not candidates:
            raise ValueError(
                f"nenhuma atividade disponível para o perfil {position + 1}"
            )
        selected.append(candidates[report_index % len(candidates)])
    return selected


def audit_area(
    knowledge_base: str | Path,
    *,
    reports: int,
    activities_per_report: int = 3,
    maximum_adjusted_jaccard: float = 0.65,
) -> AreaAuditSummary:
    path = Path(knowledge_base)
    activities = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(activities, list) or not activities:
        raise ValueError(f"knowledge base vazia ou inválida: {path}")
    if reports < 1:
        raise ValueError("reports deve ser positivo")
    if not 1 <= activities_per_report <= min(3, len(activities)):
        raise ValueError("activities_per_report deve estar entre 1 e 3")
    if not 0.0 <= maximum_adjusted_jaccard <= 1.0:
        raise ValueError("maximum_adjusted_jaccard deve estar entre 0 e 1")

    registry = ReportOriginalityRegistry()
    report_fingerprints: list[ReportFingerprint] = []
    activity_fingerprints: dict[str, list[ActivityFingerprint]] = {}
    adjusted_signatures: dict[str, list[frozenset[tuple[str, ...]]]] = {}
    covered_titles: set[str] = set()
    maximum_runtime_similarity = 0.0
    maximum_adjusted_similarity = 0.0
    recompositions = 0

    for report_index in range(reports):
        selected = _profile_aligned_selection(
            activities,
            report_index=report_index,
            count=activities_per_report,
        )
        seed = hashlib.sha256(
            f"originality-audit:{path.stem}:{report_index}".encode("utf-8")
        ).hexdigest()
        generator = ActivityGenerator(
            max_atividades=activities_per_report,
            report_seed=seed,
            variant_index=int(seed[:16], 16),
            originality_registry=registry,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            result = generator.generate(selected)

        sections = tuple(
            result[f"ATV{position}"]
            for position in range(1, activities_per_report + 1)
        )
        report_fingerprints.append(ReportFingerprint.from_sections(sections))
        maximum_runtime_similarity = max(
            maximum_runtime_similarity,
            generator.last_originality_report.maximum_similarity,
        )
        recompositions += generator.last_composition_attempts - 1

        for activity, text in zip(selected, sections):
            title = str(activity["titulo"])
            covered_titles.add(title)
            activity_fingerprints.setdefault(title, []).append(
                ActivityFingerprint.from_activity(title, text)
            )
            signature = adjusted_ngram_signature(
                text,
                excluded_phrases=_normalized_required_phrases(activity),
            )
            previous = adjusted_signatures.setdefault(title, [])
            if previous:
                maximum_adjusted_similarity = max(
                    maximum_adjusted_similarity,
                    max(signature_jaccard(signature, item) for item in previous),
                )
            previous.append(signature)

    all_activity_fingerprints = [
        fingerprint
        for fingerprints in activity_fingerprints.values()
        for fingerprint in fingerprints
    ]
    all_paragraph_hashes = [
        paragraph
        for fingerprint in all_activity_fingerprints
        for paragraph in fingerprint.paragraph_hashes
    ]
    generated_activities = len(all_activity_fingerprints)
    unique_activities = sum(
        len({fingerprint.normalized_hash for fingerprint in fingerprints})
        for fingerprints in activity_fingerprints.values()
    )
    unique_openings = len(
        {fingerprint.opening_hash for fingerprint in all_activity_fingerprints}
    )
    unique_paragraphs = len(set(all_paragraph_hashes))
    unique_reports = len(
        {fingerprint.normalized_hash for fingerprint in report_fingerprints}
    )
    passed = all(
        (
            len(covered_titles) == len(activities),
            unique_reports == reports,
            unique_activities == generated_activities,
            unique_openings == generated_activities,
            unique_paragraphs == len(all_paragraph_hashes),
            maximum_adjusted_similarity <= maximum_adjusted_jaccard,
        )
    )
    return AreaAuditSummary(
        area=path.stem,
        available_activities=len(activities),
        covered_activities=len(covered_titles),
        reports_generated=reports,
        activities_generated=generated_activities,
        unique_reports=unique_reports,
        unique_activities=unique_activities,
        unique_openings=unique_openings,
        paragraphs_generated=len(all_paragraph_hashes),
        unique_paragraphs=unique_paragraphs,
        recompositions=recompositions,
        maximum_runtime_similarity=round(maximum_runtime_similarity, 6),
        maximum_adjusted_similarity=round(maximum_adjusted_similarity, 6),
        passed=passed,
    )


def run_project_audit(
    knowledge_base_directory: str | Path = DEFAULT_KNOWLEDGE_BASE_DIRECTORY,
    *,
    reports_per_area: int = 25,
    activities_per_report: int = 3,
    maximum_adjusted_jaccard: float = 0.65,
) -> ProjectAuditSummary:
    directory = Path(knowledge_base_directory)
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError(f"nenhuma knowledge base encontrada em {directory}")
    areas = tuple(
        audit_area(
            path,
            reports=reports_per_area,
            activities_per_report=activities_per_report,
            maximum_adjusted_jaccard=maximum_adjusted_jaccard,
        )
        for path in paths
    )
    return ProjectAuditSummary(
        schema_version=1,
        reports_per_area=reports_per_area,
        activities_per_report=activities_per_report,
        maximum_adjusted_jaccard=maximum_adjusted_jaccard,
        areas=areas,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--knowledge-base-directory",
        type=Path,
        default=DEFAULT_KNOWLEDGE_BASE_DIRECTORY,
    )
    parser.add_argument("--reports-per-area", type=int, default=25)
    parser.add_argument("--activities-per-report", type=int, default=3)
    parser.add_argument("--maximum-adjusted-jaccard", type=float, default=0.65)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        summary = run_project_audit(
            args.knowledge_base_directory,
            reports_per_area=args.reports_per_area,
            activities_per_report=args.activities_per_report,
            maximum_adjusted_jaccard=args.maximum_adjusted_jaccard,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2

    for area in summary.areas:
        status = "APROVADA" if area.passed else "REPROVADA"
        print(
            f"{area.area}: {status}; "
            f"similaridade ajustada máxima={area.maximum_adjusted_similarity:.3f}; "
            f"recomposições={area.recompositions}"
        )
    print(f"Resumo gravado em: {args.output}")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
