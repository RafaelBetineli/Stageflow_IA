"""
activity_selector.py

Módulo responsável por selecionar atividades já existentes na
knowledge_base, a partir de uma lista de títulos informados.

Este módulo NÃO gera texto e NÃO utiliza IA. Ele apenas consulta um
ActivityRepository já carregado e retorna os dados completos das
atividades encontradas.
"""

from activity_repository import ActivityRepository


class ActivitySelector:
    """
    Seleciona atividades de uma knowledge_base a partir de seus títulos.

    A classe depende de uma instância de ActivityRepository, já
    carregada, para realizar as buscas. Não acessa arquivos
    diretamente e não realiza nenhum tipo de geração de conteúdo.

    Attributes:
        repository (ActivityRepository): Repositório utilizado para
            consultar as atividades disponíveis.
    """

    def __init__(self, repository: ActivityRepository) -> None:
        """
        Inicializa o seletor com um repositório de atividades.

        Args:
            repository (ActivityRepository): Instância já carregada
                de ActivityRepository, utilizada para buscar
                atividades pelo título.
        """
        self.repository = repository

    def select(self, titulos: list[str]) -> list[dict]:
        """
        Seleciona as atividades correspondentes aos títulos informados.

        Para cada título da lista, consulta o repository utilizando
        find_by_title(). Títulos encontrados são adicionados à lista
        de saída. Títulos não encontrados são ignorados silenciosamente.

        Args:
            titulos (list[str]): Lista de títulos de atividades a
                serem buscadas.

        Returns:
            list[dict]: Lista de atividades encontradas, cada uma no
                formato:
                {
                    "titulo": "...",
                    "categoria": "...",
                    "palavras_chave": [...]
                }
        """
        atividades_encontradas: list[dict] = []

        for titulo in titulos:
            atividade = self.repository.find_by_title(titulo)
            if atividade is not None:
                atividades_encontradas.append(atividade)

        return atividades_encontradas

    def count_found(self, titulos: list[str]) -> int:
        """
        Conta quantas atividades da lista de títulos foram encontradas.

        Args:
            titulos (list[str]): Lista de títulos de atividades a
                serem buscadas.

        Returns:
            int: Quantidade de atividades encontradas no repository.
        """
        return len(self.select(titulos))
