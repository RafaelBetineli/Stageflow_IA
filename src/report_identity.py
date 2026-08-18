"""Identidade estável usada para variar a redação de cada relatório."""

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping


IDENTITY_FIELDS = (
    "RA_ALUNO",
    "EMAIL_ALUNO",
    "AREA_ESTAGIO",
    "MODULO_ESTAGIO",
    "DATA_INICIO_ESTAGIO",
    "DATA_FIM_ESTAGIO",
)


@dataclass(frozen=True)
class ReportIdentity:
    seed: str
    variant_index: int


def build_report_identity(data: Mapping[str, object]) -> ReportIdentity:
    """Cria uma identidade reproduzível sem usar documentos sensíveis."""
    payload = {
        field: str(data.get(field, "")).strip().casefold()
        for field in IDENTITY_FIELDS
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ReportIdentity(seed=digest, variant_index=int(digest[:16], 16))
