"""
activity_pipeline.py

Módulo responsável por orquestrar o fluxo completo de seleção e
preparação de atividades, unindo ActivityRepository, ActivitySelector,
ActivityPlanner e ActivityGenerator em um único ponto de entrada.

Este módulo NÃO acessa arquivos diretamente e NÃO gera texto por conta
própria: ele apenas coordena os outros módulos já existentes,
combinando seus resultados em um único dicionário de placeholders.
"""

from activity_repository import ActivityRepository
from activity_selector import ActivitySelector
from activity_planner import ActivityPlanner
from activity_generator import ActivityGenerator
from activity_originality import ReportOriginalityRegistry
from activity_bibliography import BibliographyCatalog


class ActivityPipeline:
    """
    Orquestra a seleção e preparação de placeholders de atividades.

    A classe recebe um ActivityRepository já carregado e, internamente,
    instancia um ActivitySelector, um ActivityPlanner e um
    ActivityGenerator. A partir de uma lista de títulos, ela coordena
    esses três componentes para produzir um único dicionário de
    placeholders, prontos para uso pelo DocumentGenerator.

    Attributes:
        repository (ActivityRepository): Repositório de atividades
            utilizado para as buscas.
        area_estagio (str): Área do estágio, repassada ao
            ActivityGenerator para contextualizar a geração dos
            textos das atividades.
        selector (ActivitySelector): Responsável por selecionar as
            atividades existentes a partir dos títulos informados.
        planner (ActivityPlanner): Responsável por montar os
            placeholders de título (TITULO_ATV1, TITULO_ATV2, ...).
        generator (ActivityGenerator): Responsável por montar os
            placeholders de texto (ATV1, ATV2, ...).
    """

    def __init__(
        self,
        repository: ActivityRepository,
        area_estagio: str = "não informado",
        *,
        report_seed: str = "default",
        variant_index: int = 0,
        originality_registry: ReportOriginalityRegistry | None = None,
    ) -> None:
        """
        Inicializa o pipeline a partir de um repositório de atividades.

        Args:
            repository (ActivityRepository): Instância já carregada
                de ActivityRepository, utilizada para buscar
                atividades pelo título.
            area_estagio (str): Área do estágio, usada para
                contextualizar a geração dos textos das atividades.
                Quando não informada, usa "não informado".
        """
        self.repository = repository
        self.area_estagio = area_estagio

        catalog_path = (
            repository.caminho_arquivo.parent
            / "references"
            / repository.caminho_arquivo.name
        )
        self.bibliography_catalog = (
            BibliographyCatalog.from_file(catalog_path)
            if catalog_path.exists()
            else BibliographyCatalog()
        )

        # Componentes internos do pipeline, criados a partir do repository.
        self.selector = ActivitySelector(repository)
        self.planner = ActivityPlanner()
        self.generator = ActivityGenerator(
            area_estagio=area_estagio,
            report_seed=report_seed,
            variant_index=variant_index,
            originality_registry=originality_registry,
            bibliography_catalog=self.bibliography_catalog,
        )

    def build(self, titulos: list[str]) -> dict:
        """
        Executa o fluxo completo de seleção e geração de placeholders.

        Fluxo interno:
            1. Seleciona as atividades existentes a partir dos títulos.
            2. Monta os placeholders de título (TITULO_ATV1, ...).
            3. Monta os placeholders de texto (ATV1, ...).
            4. Une os dois dicionários de placeholders em um único.

        Args:
            titulos (list[str]): Lista de títulos de atividades a
                serem buscadas e processadas.

        Returns:
            dict: Dicionário único contendo todos os placeholders de
                título e de texto, no formato:
                {
                    "TITULO_ATV1": "Preenchimento labial",
                    ...
                    "ATV1": "Relato composto e validado para a atividade ...",
                    ...
                }
        """
        # Passo 1: seleciona as atividades encontradas no repository.
        atividades = self.selector.select(titulos)

        # Passo 2: monta os placeholders de título.
        placeholders_titulo = self.planner.build_placeholders(atividades)

        # Passo 3: monta os placeholders de texto.
        placeholders_texto = self.generator.generate(atividades)

        textos_gerados = tuple(
            placeholders_texto[f"ATV{position}"]
            for position in range(1, len(atividades) + 1)
            if placeholders_texto.get(f"ATV{position}", "").strip()
        )
        self.bibliography_catalog.validate_usage(
            textos_gerados,
            self.generator.last_citation_ids,
        )
        referencias = self.bibliography_catalog.format_references(
            self.generator.last_citation_ids
        )

        # Passo 4: une os dois dicionários em um único resultado.
        resultado = {
            **placeholders_titulo,
            **placeholders_texto,
            "REFERENCIAS": referencias,
        }

        # Passo 5: retorna o resultado final.
        return resultado


    def count_selected(self, titulos: list[str]) -> int:
        """
        Conta quantas atividades da lista de títulos foram selecionadas.

        Args:
            titulos (list[str]): Lista de títulos de atividades a
                serem buscadas.

        Returns:
            int: Quantidade de atividades encontradas no repository.
        """
        return len(self.selector.select(titulos))
