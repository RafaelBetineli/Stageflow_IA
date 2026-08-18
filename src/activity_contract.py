"""Contrato de dados para atividades enriquecidas da knowledge base."""

from dataclasses import dataclass
import re
from typing import Any, Mapping


REPORT_TYPE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

FACT_GROUPS = (
    "avaliacao_planejamento",
    "preparo_biosseguranca_execucao",
    "orientacoes_aprendizado",
)

RESTRICTION_GROUPS = (
    "acoes_exclusivas_profissional",
    "afirmacoes_nao_permitidas",
    "detalhes_nao_inventar",
)

REQUIRED_ACTIVITY_FIELDS = frozenset(
    {
        "titulo",
        "categoria",
        "tipo_relato",
        "termos_permitidos",
        "contexto_seguro",
        "referencias_ids",
        "fatos_permitidos",
        "papel_estagiario",
        "elementos_condicionais",
        "restricoes_validacao",
    }
)


class ActivityContractError(ValueError):
    """Indica que uma atividade não cumpre o contrato enriquecido."""


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ActivityContractError(f"{path} deve ser um objeto")
    return value


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActivityContractError(f"{path} deve ser um texto não vazio")

    text = value.strip()
    if "[cite:" in text.casefold():
        raise ActivityContractError(f"{path} contém marcador de citação residual")
    return text


def _require_text_list(
    value: Any,
    path: str,
    *,
    minimum: int = 1,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ActivityContractError(f"{path} deve ser uma lista")

    items = tuple(_require_text(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(items) < minimum:
        raise ActivityContractError(f"{path} deve conter pelo menos {minimum} item(ns)")

    normalized = [item.casefold() for item in items]
    if len(normalized) != len(set(normalized)):
        raise ActivityContractError(f"{path} contém itens duplicados")
    return items


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise ActivityContractError(f"{path} não contém: {', '.join(sorted(missing))}")
    if extra:
        raise ActivityContractError(f"{path} contém campos desconhecidos: {', '.join(sorted(extra))}")


@dataclass(frozen=True)
class ActivityFacts:
    avaliacao_planejamento: tuple[str, ...]
    preparo_biosseguranca_execucao: tuple[str, ...]
    orientacoes_aprendizado: tuple[str, ...]

    def get(self, group: str) -> tuple[str, ...]:
        if group not in FACT_GROUPS:
            raise KeyError(f"Grupo de fatos desconhecido: {group}")
        return getattr(self, group)

@dataclass(frozen=True)
class ActivityRestrictions:
    acoes_exclusivas_profissional: tuple[str, ...]
    afirmacoes_nao_permitidas: tuple[str, ...]
    detalhes_nao_inventar: tuple[str, ...]


@dataclass(frozen=True)
class EnrichedActivity:
    titulo: str
    categoria: str
    tipo_relato: str
    termos_permitidos: tuple[str, ...]
    contexto_seguro: str
    referencias_ids: tuple[str, ...]
    fatos_permitidos: ActivityFacts
    papel_estagiario: tuple[str, ...]
    elementos_condicionais: tuple[str, ...]
    restricoes_validacao: ActivityRestrictions

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, path: str = "atividade") -> "EnrichedActivity":
        data = _require_mapping(raw, path)
        _require_exact_keys(data, set(REQUIRED_ACTIVITY_FIELDS), path)

        report_type = _require_text(data["tipo_relato"], f"{path}.tipo_relato")
        if not REPORT_TYPE_PATTERN.fullmatch(report_type):
            raise ActivityContractError(
                f"{path}.tipo_relato deve usar identificador snake_case: '{report_type}'"
            )

        facts_raw = _require_mapping(data["fatos_permitidos"], f"{path}.fatos_permitidos")
        _require_exact_keys(facts_raw, set(FACT_GROUPS), f"{path}.fatos_permitidos")
        facts = ActivityFacts(
            avaliacao_planejamento=_require_text_list(
                facts_raw["avaliacao_planejamento"],
                f"{path}.fatos_permitidos.avaliacao_planejamento",
                minimum=2,
            ),
            preparo_biosseguranca_execucao=_require_text_list(
                facts_raw["preparo_biosseguranca_execucao"],
                f"{path}.fatos_permitidos.preparo_biosseguranca_execucao",
                minimum=2,
            ),
            orientacoes_aprendizado=_require_text_list(
                facts_raw["orientacoes_aprendizado"],
                f"{path}.fatos_permitidos.orientacoes_aprendizado",
                minimum=3,
            ),
        )

        restrictions_raw = _require_mapping(
            data["restricoes_validacao"], f"{path}.restricoes_validacao"
        )
        _require_exact_keys(
            restrictions_raw,
            set(RESTRICTION_GROUPS),
            f"{path}.restricoes_validacao",
        )
        restrictions = ActivityRestrictions(
            acoes_exclusivas_profissional=_require_text_list(
                restrictions_raw["acoes_exclusivas_profissional"],
                f"{path}.restricoes_validacao.acoes_exclusivas_profissional",
            ),
            afirmacoes_nao_permitidas=_require_text_list(
                restrictions_raw["afirmacoes_nao_permitidas"],
                f"{path}.restricoes_validacao.afirmacoes_nao_permitidas",
            ),
            detalhes_nao_inventar=_require_text_list(
                restrictions_raw["detalhes_nao_inventar"],
                f"{path}.restricoes_validacao.detalhes_nao_inventar",
            ),
        )

        return cls(
            titulo=_require_text(data["titulo"], f"{path}.titulo"),
            categoria=_require_text(data["categoria"], f"{path}.categoria"),
            tipo_relato=report_type,
            termos_permitidos=_require_text_list(
                data["termos_permitidos"], f"{path}.termos_permitidos", minimum=3
            ),
            contexto_seguro=_require_text(data["contexto_seguro"], f"{path}.contexto_seguro"),
            referencias_ids=_require_text_list(
                data["referencias_ids"], f"{path}.referencias_ids", minimum=0
            ),
            fatos_permitidos=facts,
            papel_estagiario=_require_text_list(
                data["papel_estagiario"], f"{path}.papel_estagiario", minimum=3
            ),
            elementos_condicionais=_require_text_list(
                data["elementos_condicionais"],
                f"{path}.elementos_condicionais",
                minimum=0,
            ),
            restricoes_validacao=restrictions,
        )

def parse_activity_collection(raw: Any) -> tuple[EnrichedActivity, ...]:
    """Valida uma lista completa e rejeita títulos duplicados."""
    if not isinstance(raw, list):
        raise ActivityContractError("a knowledge base deve ser uma lista")

    activities = tuple(
        EnrichedActivity.from_dict(item, path=f"atividades[{index}]")
        for index, item in enumerate(raw)
    )

    seen: dict[str, int] = {}
    for index, activity in enumerate(activities):
        normalized_title = activity.titulo.casefold()
        if normalized_title in seen:
            first = seen[normalized_title]
            raise ActivityContractError(
                f"título duplicado em atividades[{first}] e atividades[{index}]: "
                f"'{activity.titulo}'"
            )
        seen[normalized_title] = index

    return activities
