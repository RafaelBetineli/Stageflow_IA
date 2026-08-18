"""Catalogo local de fontes e validacao de citacoes das atividades."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence


CATALOG_FIELDS = frozenset(
    {"id", "citation", "reference", "url", "verified_on"}
)
CITATION_PATTERN = re.compile(r"^.+,\s*\d{4}[a-z]?$", re.IGNORECASE)


class BibliographyError(ValueError):
    """Indica inconsistencia no catalogo ou no uso das referencias."""


@dataclass(frozen=True)
class BibliographicReference:
    reference_id: str
    citation: str
    reference: str
    url: str
    verified_on: str

    @classmethod
    def from_dict(cls, raw: object, *, path: str) -> "BibliographicReference":
        if not isinstance(raw, dict):
            raise BibliographyError(f"{path} deve ser um objeto")

        actual = set(raw)
        missing = CATALOG_FIELDS - actual
        extra = actual - CATALOG_FIELDS
        if missing:
            raise BibliographyError(
                f"{path} nao contem: {', '.join(sorted(missing))}"
            )
        if extra:
            raise BibliographyError(
                f"{path} contem campos desconhecidos: {', '.join(sorted(extra))}"
            )

        values: dict[str, str] = {}
        for field in CATALOG_FIELDS:
            value = raw[field]
            if not isinstance(value, str) or not value.strip():
                raise BibliographyError(f"{path}.{field} deve ser um texto nao vazio")
            values[field] = value.strip()

        if not CITATION_PATTERN.fullmatch(values["citation"]):
            raise BibliographyError(
                f"{path}.citation deve seguir o formato autor-data"
            )
        if not values["url"].startswith("https://"):
            raise BibliographyError(f"{path}.url deve usar HTTPS")
        if values["url"] not in values["reference"]:
            raise BibliographyError(f"{path}.reference deve conter a URL verificada")
        if values["citation"].rsplit(",", 1)[-1].strip()[:4] not in values["reference"]:
            raise BibliographyError(f"{path}.reference nao contem o ano da citacao")

        return cls(
            reference_id=values["id"],
            citation=values["citation"],
            reference=values["reference"],
            url=values["url"],
            verified_on=values["verified_on"],
        )

    @property
    def inline_citation(self) -> str:
        return f"({self.citation})"


class BibliographyCatalog:
    """Resolve IDs em citacoes e referencias previamente verificadas."""

    def __init__(self, references: Iterable[BibliographicReference] = ()) -> None:
        self._references: dict[str, BibliographicReference] = {}
        citations: set[str] = set()
        for reference in references:
            if reference.reference_id in self._references:
                raise BibliographyError(
                    f"ID bibliografico duplicado: {reference.reference_id}"
                )
            if reference.citation.casefold() in citations:
                raise BibliographyError(
                    f"Citacao autor-data duplicada: {reference.citation}"
                )
            self._references[reference.reference_id] = reference
            citations.add(reference.citation.casefold())

    @classmethod
    def from_file(cls, path: str | Path) -> "BibliographyCatalog":
        catalog_path = Path(path)
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise BibliographyError("o catalogo bibliografico deve ser uma lista")
        return cls(
            BibliographicReference.from_dict(item, path=f"referencias[{index}]")
            for index, item in enumerate(raw)
        )

    def __bool__(self) -> bool:
        return bool(self._references)

    def require(self, reference_id: str) -> BibliographicReference:
        try:
            return self._references[reference_id]
        except KeyError as error:
            raise BibliographyError(
                f"referencia bibliografica inexistente: {reference_id}"
            ) from error

    def validate_activity_ids(self, reference_ids: Sequence[str]) -> None:
        if not reference_ids:
            raise BibliographyError("a atividade deve possuir ao menos uma referencia")
        if len(reference_ids) != len(set(reference_ids)):
            raise BibliographyError("a atividade contem IDs bibliograficos duplicados")
        for reference_id in reference_ids:
            self.require(reference_id)

    def inline_citation(self, reference_id: str) -> str:
        return self.require(reference_id).inline_citation

    def format_references(self, reference_ids: Sequence[str]) -> str:
        ordered_ids = tuple(dict.fromkeys(reference_ids))
        return "\n".join(self.require(item).reference for item in ordered_ids)

    def validate_usage(
        self,
        activity_texts: Sequence[str],
        reference_ids: Sequence[str],
    ) -> None:
        if not self._references:
            return

        ordered_ids = tuple(dict.fromkeys(reference_ids))
        combined_text = "\n".join(activity_texts)
        all_catalog_citations = tuple(
            reference.inline_citation for reference in self._references.values()
        )

        for position, activity_text in enumerate(activity_texts, start=1):
            if not any(citation in activity_text for citation in all_catalog_citations):
                raise BibliographyError(
                    f"ATV{position} nao contem citacao bibliografica valida"
                )

        for reference_id in ordered_ids:
            citation = self.inline_citation(reference_id)
            if citation not in combined_text:
                raise BibliographyError(
                    f"referencia sem citacao no texto: {reference_id}"
                )

        expected_citations = {
            self.inline_citation(reference_id) for reference_id in ordered_ids
        }
        catalog_citations = {
            citation for citation in all_catalog_citations if citation in combined_text
        }
        unexpected = catalog_citations - expected_citations
        if unexpected:
            raise BibliographyError(
                "citacao sem referencia selecionada: " + ", ".join(sorted(unexpected))
            )


@lru_cache(maxsize=1)
def load_project_bibliography_catalog() -> BibliographyCatalog:
    """Carrega todos os catalogos locais, sem acesso de rede em execucao."""
    directory = Path(__file__).resolve().parents[1] / "knowledge_base" / "references"
    if not directory.exists():
        return BibliographyCatalog()

    references: list[BibliographicReference] = []
    for path in sorted(directory.glob("*.json")):
        catalog = BibliographyCatalog.from_file(path)
        references.extend(catalog._references.values())
    return BibliographyCatalog(references)
