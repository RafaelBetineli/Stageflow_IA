"""
data_enricher.py
=================
Recebe um dicionário de dados do aluno e gera automaticamente campos
derivados utilizados pelos documentos (datas formatadas, quantidade
de dias de estágio, etc).

Responsabilidade única: dict → dict (enriquecido).

Este módulo NÃO lê JSON, NÃO salva arquivos e NÃO gera DOCX.
Apenas calcula e adiciona campos a um dicionário já em memória.

Não depende de bibliotecas externas — usa somente `datetime` da
biblioteca padrão do Python.
"""

from datetime import datetime
import re
from typing import Optional


class DataEnricher:
    """
    Enriquece dicionários de dados do aluno com campos calculados.

    Campos gerados (quando possível):
        DATA_INICIO_EXTENSO  →  a partir de DATA_INICIO_ESTAGIO
        DATA_FIM_EXTENSO     →  a partir de DATA_FIM_ESTAGIO
        QTD_DIAS             →  a partir de DATA_INICIO_ESTAGIO e DATA_FIM_ESTAGIO

    Se uma data estiver ausente ou em formato inválido, o campo
    derivado correspondente simplesmente não é gerado — nenhuma
    exceção é levantada.
    """

    _MESES = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    OPTIONAL_DOCUMENT_FIELDS = (
        "BAIRRO_ALUNO",
        "CEP_ALUNO",
        "EMPRESA_FANTASIA",
        "BAIRRO_EMPRESA",
        "TELEFONE_ALUNO",
        "TELEFONE_EMPRESA",
        "DIAS_ESTAGIO",
        "HORARIO_ESTAGIO",
        "CARGA_SEMANAL",
        "DEPENDENCIA",
        "HISTORICO_MODULOS",
        "COMPLEMENTAR1",
        "COMPLEMENTAR2",
        "OBSERVACOES_PLANO",
    )

    def enrich(self, data: dict, activity_count: int = 3) -> dict:
        """
        Recebe um dicionário de dados do aluno e retorna uma cópia
        enriquecida com os campos derivados.

        Parâmetros
        ----------
        data : dict
            Dicionário original. Espera-se que contenha (opcionalmente)
            as chaves "DATA_INICIO_ESTAGIO" e "DATA_FIM_ESTAGIO" no
            formato "DD/MM/AAAA".

        Retorna
        -------
        dict
            Cópia do dicionário original com os campos derivados
            adicionados (quando o cálculo foi possível).
        """
        dados_enriquecidos = data.copy()

        for field in self.OPTIONAL_DOCUMENT_FIELDS:
            dados_enriquecidos.setdefault(field, "")

        data_inicio = self._parse_date(data.get("DATA_INICIO_ESTAGIO"))
        data_fim    = self._parse_date(data.get("DATA_FIM_ESTAGIO"))

        # ── Data de início formatada ───────────────────────────────────
        if data_inicio is not None:
            dados_enriquecidos["DATA_INICIO_EXTENSO"] = self._date_to_extenso(data_inicio)

        # ── Data de fim formatada ────────────────────────────────────────
        if data_fim is not None:
            dados_enriquecidos["DATA_FIM_EXTENSO"] = self._date_to_extenso(data_fim)

        # ── Quantidade de dias (precisa das duas datas) ─────────────────
        if data_inicio is not None and data_fim is not None:
            qtd_dias = self._calcular_qtd_dias(data_inicio, data_fim)
            dados_enriquecidos["QTD_DIAS"] = str(qtd_dias)

        self._adicionar_cargas_atividades(dados_enriquecidos, activity_count)

        return dados_enriquecidos

    # ------------------------------------------------------------------
    # Métodos privados — parsing e cálculo
    # ------------------------------------------------------------------

    def _parse_date(self, valor) -> Optional[datetime]:
        """
        Converte uma string "DD/MM/AAAA" em um objeto datetime.

        Parâmetros
        ----------
        valor : str | None
            Texto da data no formato "DD/MM/AAAA". Pode ser None ou
            uma string vazia/inválida.

        Retorna
        -------
        datetime | None
            O objeto datetime correspondente, ou None se `valor` for
            ausente, vazio, ou não puder ser interpretado como data.
        """
        if not valor:
            return None

        try:
            return datetime.strptime(str(valor).strip(), "%d/%m/%Y")
        except ValueError:
            return None

    def _date_to_extenso(self, data: datetime) -> str:
        """
        Converte uma data para o formato exigido pela faculdade:
        dia numérico + nome do mês + ano numérico.

        Exemplo
        -------
        20/02/2026  →  "20 de fevereiro de 2026"

        Parâmetros
        ----------
        data : datetime
            Data a ser convertida.

        Retorna
        -------
        str
            Data formatada como "DD de mês de AAAA".
        """
        mes_nome = self._MESES[data.month - 1]
        return f"{data.day} de {mes_nome} de {data.year}"

    def _calcular_qtd_dias(self, data_inicio: datetime, data_fim: datetime) -> int:
        """
        Calcula a quantidade de dias corridos de estágio, de forma
        inclusiva — ou seja, contando tanto o dia de início quanto o
        dia de término.

        Exemplo
        -------
        20/02/2026 até 21/02/2026  →  2 dias
        (a universidade considera o próprio dia de início como o
        primeiro dia já realizado)

        Parâmetros
        ----------
        data_inicio : datetime
            Data de início do estágio.
        data_fim : datetime
            Data de término do estágio.

        Retorna
        -------
        int
            Número de dias corridos (inclusivo).
        """
        diferenca_dias = (data_fim - data_inicio).days

        return diferenca_dias + 1

    @staticmethod
    def _adicionar_cargas_atividades(data: dict, activity_count: int) -> None:
        """Distribui a carga total entre as atividades selecionadas."""
        if not 1 <= activity_count <= 10:
            raise ValueError("activity_count deve estar entre 1 e 10")

        match = re.search(r"\d+", str(data.get("CARGA_HORARIA", "")))
        total = int(match.group()) if match else 0
        base, remainder = divmod(total, activity_count)

        for position in range(1, 11):
            if position <= activity_count:
                hours = base + (1 if position <= remainder else 0)
                data[f"CARGA_ATV{position}"] = f"{hours} horas"
            else:
                data[f"CARGA_ATV{position}"] = ""
