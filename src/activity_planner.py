"""
activity_planner.py

Módulo responsável por transformar uma lista de atividades já
selecionadas em um dicionário de placeholders, prontos para serem
utilizados pelo DocumentGenerator na geração dos documentos DOCX.

Este módulo NÃO gera texto, NÃO utiliza IA e NÃO acessa arquivos.
Ele apenas organiza dados que já existem em memória no formato
esperado pelos templates.
"""


class ActivityPlanner:
    """
    Prepara placeholders de atividades para uso em templates DOCX.

    A classe recebe uma lista de atividades (já filtradas por um
    ActivitySelector, por exemplo) e monta um dicionário de
    placeholders no formato TITULO_ATV1, TITULO_ATV2, ..., até o
    limite máximo configurado no construtor. Atividades que excedem
    esse limite são ignoradas, e placeholders sem atividade
    correspondente são preenchidos com string vazia.

    Attributes:
        max_atividades (int): Quantidade máxima de placeholders de
            atividades a serem gerados.
    """

    def __init__(self, max_atividades: int = 10) -> None:
        """
        Inicializa o planner com o limite máximo de atividades.

        Args:
            max_atividades (int): Quantidade máxima de placeholders
                TITULO_ATV a serem criados. Valor padrão: 10.
        """
        self.max_atividades = max_atividades

    def build_placeholders(self, atividades: list[dict]) -> dict:
        """
        Monta o dicionário de placeholders a partir das atividades.

        Para cada posição de 1 até max_atividades, o placeholder
        correspondente (ex.: TITULO_ATV1) é preenchido com o título
        da atividade na mesma posição da lista recebida. Caso não
        exista atividade suficiente, o placeholder é preenchido com
        string vazia. Atividades além do limite são ignoradas.

        Args:
            atividades (list[dict]): Lista de atividades selecionadas,
                cada uma contendo ao menos a chave "titulo".

        Returns:
            dict: Dicionário no formato:
                {
                    "TITULO_ATV1": "Preenchimento labial",
                    "TITULO_ATV2": "Skinbooster",
                    ...
                    "TITULO_ATV10": ""
                }
        """
        placeholders: dict = {}

        # Percorre as posições de 1 até o limite máximo configurado.
        for posicao in range(1, self.max_atividades + 1):
            nome_placeholder = f"TITULO_ATV{posicao}"

            # Índice da lista correspondente à posição atual (base 0).
            indice = posicao - 1

            if indice < len(atividades):
                # Existe atividade nessa posição: usa o título dela.
                placeholders[nome_placeholder] = atividades[indice].get(
                    "titulo", ""
                )
            else:
                # Não há atividade suficiente: placeholder vazio.
                placeholders[nome_placeholder] = ""

        return placeholders
