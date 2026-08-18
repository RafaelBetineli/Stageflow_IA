"""
activity_repository.py

Módulo responsável por carregar arquivos JSON da pasta knowledge_base
e fornecer uma forma simples de consultar atividades pelo título.

Utiliza apenas bibliotecas nativas do Python (json e pathlib).
"""

import json
from pathlib import Path
from typing import Any, Optional

from activity_contract import parse_activity_collection


class ActivityRepository:
    """
    Repositório de atividades carregadas a partir de um arquivo JSON.

    A classe é responsável por:
    - Validar a existência do arquivo JSON informado.
    - Carregar o conteúdo do arquivo e mantê-lo em memória.
    - Permitir consultas sobre as atividades carregadas (listar todas
      ou buscar por título, de forma case insensitive).

    Attributes:
        caminho_arquivo (Path): Caminho do arquivo JSON carregado.
        _atividades (list[dict[str, Any]]): Lista de atividades em memória.
    """

    def __init__(self, caminho_json: str) -> None:
        """
        Inicializa o repositório a partir de um arquivo JSON.

        Args:
            caminho_json (str): Caminho (relativo ou absoluto) para o
                arquivo JSON localizado na pasta knowledge_base.

        Raises:
            FileNotFoundError: Se o arquivo informado não existir.
            ValueError: Se o conteúdo do arquivo não for uma lista JSON
                válida de atividades.
        """
        self.caminho_arquivo = Path(caminho_json)

        if not self.caminho_arquivo.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {self.caminho_arquivo}"
            )

        self._atividades: list[dict[str, Any]] = self._carregar_json()

    def _carregar_json(self) -> list[dict[str, Any]]:
        """
        Lê e interpreta o arquivo JSON informado no construtor.

        Returns:
            list[dict[str, Any]]: Lista de atividades carregadas.

        Raises:
            ValueError: Se o conteúdo do arquivo não for uma lista.
        """
        with self.caminho_arquivo.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        if not isinstance(dados, list):
            raise ValueError(
                f"O arquivo {self.caminho_arquivo} deve conter uma lista "
                "de atividades no formato JSON."
            )

        parse_activity_collection(dados)

        return dados

    @staticmethod
    def _normalize(texto: str) -> str:
        """
        Normaliza um texto para fins de comparação.

        Converte o texto para minúsculas e remove espaços extras
        nas extremidades.

        Args:
            texto (str): Texto a ser normalizado.

        Returns:
            str: Texto normalizado.
        """
        return texto.strip().lower()

    def get_all(self) -> list[dict[str, Any]]:
        """
        Retorna todas as atividades carregadas.

        Returns:
            list[dict[str, Any]]: Lista completa de atividades, no
                mesmo formato presente no arquivo JSON original.
        """
        return self._atividades

    def find_by_title(self, titulo: str) -> Optional[dict[str, Any]]:
        """
        Busca uma atividade pelo título, de forma case insensitive.

        Args:
            titulo (str): Título da atividade a ser buscada. A busca
                ignora diferenças entre maiúsculas e minúsculas e
                espaços extras nas extremidades.

        Returns:
            Optional[dict[str, Any]]: Dicionário da atividade encontrada,
                ou None caso nenhuma atividade corresponda ao título.
        """
        titulo_normalizado = self._normalize(titulo)

        for atividade in self._atividades:
            titulo_atividade = atividade.get("titulo", "")
            if self._normalize(titulo_atividade) == titulo_normalizado:
                return atividade

        return None
