"""Distribuição determinística dos fatos seguros entre os parágrafos."""

from dataclasses import dataclass

from activity_contract import EnrichedActivity, FACT_GROUPS
from activity_narrative_planner import NarrativePlan, ParagraphSpec


class ContentAllocationError(ValueError):
    """Indica que os fatos não puderam ser distribuídos pelo plano."""


@dataclass(frozen=True)
class AllocatedParagraph:
    spec: ParagraphSpec
    context: str | None
    facts: tuple[str, ...]


def _contiguous_counts(item_count: int, weights: list[int]) -> list[int]:
    """Divide itens em blocos contíguos proporcionais aos pesos."""
    total_weight = sum(weights)
    exact = [item_count * weight / total_weight for weight in weights]
    counts = [int(value) for value in exact]
    remaining = item_count - sum(counts)
    order = sorted(
        range(len(weights)),
        key=lambda index: (exact[index] - counts[index], weights[index], -index),
        reverse=True,
    )
    for index in order[:remaining]:
        counts[index] += 1
    return counts


def allocate_activity_content(
    activity: EnrichedActivity,
    plan: NarrativePlan,
) -> tuple[AllocatedParagraph, ...]:
    """Atribui cada fato a um único parágrafo, ponderando seu orçamento."""
    if activity.titulo != plan.activity_title:
        raise ContentAllocationError("o plano pertence a outra atividade")

    assigned: list[list[str]] = [[] for _ in plan.paragraphs]
    for group in FACT_GROUPS:
        candidates = [
            index
            for index, paragraph in enumerate(plan.paragraphs)
            if group in paragraph.source_groups
        ]
        if not candidates:
            raise ContentAllocationError(f"nenhum parágrafo recebe o grupo '{group}'")

        facts = activity.fatos_permitidos.get(group)
        counts = _contiguous_counts(
            len(facts),
            [plan.paragraphs[index].target_words for index in candidates],
        )
        fact_offset = 0
        for candidate, count in zip(candidates, counts):
            assigned[candidate].extend(facts[fact_offset : fact_offset + count])
            fact_offset += count

    allocations = tuple(
        AllocatedParagraph(
            spec=paragraph,
            context=activity.contexto_seguro if paragraph.uses_context else None,
            facts=tuple(assigned[index]),
        )
        for index, paragraph in enumerate(plan.paragraphs)
    )

    for allocation in allocations:
        if not allocation.context and not allocation.facts:
            raise ContentAllocationError(
                f"o parágrafo '{allocation.spec.key}' ficou sem conteúdo seguro"
            )

    return allocations
