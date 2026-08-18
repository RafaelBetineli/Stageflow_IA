"""Validação centralizada dos dados recebidos pelo pipeline."""

from __future__ import annotations

import re
from datetime import datetime


class InputValidationError(ValueError):
    """Agrupa todos os problemas encontrados na entrada do usuário."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("Entrada inválida:\n- " + "\n- ".join(self.issues))


class InputValidator:
    """Valida presença, formato e coerência dos dados essenciais."""

    REQUIRED_FIELDS = {
        "NOME_ALUNO": "Nome aluno",
        "RA_ALUNO": "RA",
        "EMAIL_ALUNO": "E-mail aluno",
        "CPF": "CPF",
        "RG": "RG",
        "ENDERECO_ALUNO": "Endereço aluno",
        "CIDADE_ALUNO": "Cidade aluno",
        "ESTADO_ALUNO": "Estado aluno",
        "SEMESTRE": "Semestre",
        "CAMPUS": "Campus",
        "PERIODO": "Período",
        "APOLICE": "Número da apólice",
        "SEGURADORA": "Seguradora",
        "DATA_INICIO_VIGENCIA": "Data início vigência",
        "DATA_FIM_VIGENCIA": "Data fim vigência",
        "EMPRESA": "Razão social",
        "CNPJ": "CNPJ",
        "RAMO_EMPRESA": "Ramo empresa",
        "ENDERECO_EMPRESA": "Endereço empresa",
        "CIDADE_EMPRESA": "Cidade empresa",
        "NOME_RT": "Nome RT",
        "EMAIL_RT": "E-mail RT",
        "CONSELHO_RT": "Conselho RT",
        "CARGO_REPRESENTANTE": "Cargo representante",
        "AREA_ESTAGIO": "Área estágio",
        "DATA_INICIO_ESTAGIO": "Data início estágio",
        "DATA_FIM_ESTAGIO": "Data fim estágio",
        "CARGA_HORARIA": "Carga horária",
        "MODULO_ESTAGIO": "Módulo estágio",
        "HISTORIA_EMPRESA_INFORMADA": "História da empresa",
        "DESCRICAO_AREA_INFORMADA": "Descrição da área",
    }

    DATE_FIELDS = (
        "DATA_INICIO_VIGENCIA",
        "DATA_FIM_VIGENCIA",
        "DATA_INICIO_ESTAGIO",
        "DATA_FIM_ESTAGIO",
    )

    def validate(self, data: dict[str, str]) -> None:
        issues: list[str] = []
        for key, label in self.REQUIRED_FIELDS.items():
            if not str(data.get(key, "")).strip():
                issues.append(f"campo obrigatório ausente ou vazio: {label}")

        parsed_dates: dict[str, datetime] = {}
        for key in self.DATE_FIELDS:
            value = str(data.get(key, "")).strip()
            if not value:
                continue
            try:
                parsed_dates[key] = datetime.strptime(value, "%d/%m/%Y")
            except ValueError:
                issues.append(f"{self.REQUIRED_FIELDS[key]} deve usar DD/MM/AAAA")

        self._validate_date_order(
            parsed_dates,
            "DATA_INICIO_ESTAGIO",
            "DATA_FIM_ESTAGIO",
            "a data final do estágio deve ser igual ou posterior à inicial",
            issues,
        )
        self._validate_date_order(
            parsed_dates,
            "DATA_INICIO_VIGENCIA",
            "DATA_FIM_VIGENCIA",
            "a data final da vigência deve ser igual ou posterior à inicial",
            issues,
        )

        for key, label in (("EMAIL_ALUNO", "E-mail aluno"), ("EMAIL_RT", "E-mail RT")):
            value = str(data.get(key, "")).strip()
            if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                issues.append(f"{label} possui formato inválido")

        if data.get("CPF") and not re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", str(data["CPF"]).strip()):
            issues.append("CPF deve usar o formato 000.000.000-00")
        if data.get("CNPJ") and not re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", str(data["CNPJ"]).strip()):
            issues.append("CNPJ deve usar o formato 00.000.000/0000-00")

        carga = str(data.get("CARGA_HORARIA", ""))
        match = re.search(r"\d+", carga)
        if carga and (match is None or int(match.group()) <= 0):
            issues.append("Carga horária deve conter um número positivo")

        if issues:
            raise InputValidationError(issues)

    @staticmethod
    def _validate_date_order(
        dates: dict[str, datetime],
        start_key: str,
        end_key: str,
        message: str,
        issues: list[str],
    ) -> None:
        if start_key in dates and end_key in dates and dates[end_key] < dates[start_key]:
            issues.append(message)
