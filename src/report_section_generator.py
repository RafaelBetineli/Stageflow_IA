"""
report_section_generator.py

Módulo responsável por gerar os blocos
textuais gerais do relatório de estágio (introdução, objetivos,
história da empresa, descrição da área, conclusão e referências).

Este módulo NÃO utiliza IA, NÃO utiliza Ollama, NÃO acessa APIs
externas e NÃO realiza leitura ou escrita de arquivos. Ele apenas
monta textos simples e seguros a partir dos dados do aluno já
disponíveis em memória.
"""

class ReportSectionGenerator:
    """
    Gera os blocos textuais gerais de um relatório de estágio.

    Os textos usam somente informações fornecidas e campos determinísticos.
    """

    def generate(
        self,
        dados_aluno: dict,
        atividades: list[dict] | None = None,
        referencias: str | None = None,
    ) -> dict:
        """
        Gera o dicionário de placeholders gerais do relatório.

        Args:
            dados_aluno (dict): Dados do aluno, podendo conter campos
                como NOME_ALUNO, EMPRESA_FANTASIA, EMPRESA,
                AREA_ESTAGIO, MODULO_ESTAGIO, DATA_INICIO_ESTAGIO,
                DATA_FIM_ESTAGIO e CARGA_HORARIA.
            atividades (list[dict] | None): Lista de atividades do
                estágio (opcional). Não é obrigatória para esta
                versão stub, mas fica disponível para uso futuro.

        Returns:
            dict: Dicionário no formato:
                {
                    "INTRODUCAO": "...",
                    "OBJETIVO_GERAL": "...",
                    "OBJETIVOS_ESPECIFICOS": "...",
                    "HISTORIA_EMPRESA": "...",
                    "DESCRICAO_AREA_EMPRESA": "...",
                    "CONCLUSAO": "...",
                    "REFERENCIAS": "...",
                }
        """
        return {
            "INTRODUCAO": self._gerar_introducao(dados_aluno),
            "OBJETIVO_GERAL": self._gerar_objetivo_geral(dados_aluno),
            "OBJETIVOS_ESPECIFICOS": self._gerar_objetivos_especificos(dados_aluno),
            "HISTORIA_EMPRESA": self._gerar_historia_empresa(dados_aluno),
            "DESCRICAO_AREA_EMPRESA": self._gerar_descricao_area(dados_aluno),
            "CONCLUSAO": self._gerar_conclusao(dados_aluno),
            "COMPLEMENTAR1": dados_aluno.get("COMPLEMENTAR1", ""),
            "COMPLEMENTAR2": dados_aluno.get("COMPLEMENTAR2", ""),
            "REFERENCIAS": referencias or "",
        }

    @staticmethod
    def _gerar_introducao(dados_aluno: dict) -> str:
        """
        Gera o texto de introdução do relatório.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto de introdução.
        """
        nome_aluno = dados_aluno.get("NOME_ALUNO", "")
        empresa = dados_aluno.get("EMPRESA_FANTASIA", "") or dados_aluno.get("EMPRESA", "")
        area_estagio = dados_aluno.get("AREA_ESTAGIO", "")
        modulo_estagio = dados_aluno.get("MODULO_ESTAGIO", "")

        return (
            f"O presente relatório tem como objetivo apresentar as atividades "
            f"desenvolvidas pelo(a) estagiário(a) {nome_aluno} durante o período "
            f"de estágio realizado em {empresa}, na área de {area_estagio}, "
            f"referente ao {modulo_estagio} do curso. O documento descreve as "
            f"atividades acompanhadas, os conhecimentos aplicados e as "
            f"experiências adquiridas ao longo do período."
        )

    @staticmethod
    def _gerar_objetivo_geral(dados_aluno: dict) -> str:
        """
        Gera o texto do objetivo geral do estágio.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto do objetivo geral.
        """
        area_estagio = dados_aluno.get("AREA_ESTAGIO", "")

        return (
            f"Proporcionar ao estagiário a vivência prática dos conhecimentos "
            f"teóricos adquiridos no curso, por meio do acompanhamento de "
            f"atividades relacionadas à área de {area_estagio}, contribuindo "
            f"para sua formação profissional e técnica."
        )

    @staticmethod
    def _gerar_objetivos_especificos(dados_aluno: dict) -> str:
        """
        Gera o texto dos objetivos específicos do estágio.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto com os objetivos específicos, separados por
                quebras de linha simples.
        """
        area_estagio = dados_aluno.get("AREA_ESTAGIO", "")

        objetivos = [
            f"Acompanhar as atividades práticas realizadas na área de {area_estagio};",
            "Aplicar os conhecimentos teóricos adquiridos durante o curso;",
            "Observar a rotina e os procedimentos adotados no local de estágio;",
            "Desenvolver habilidades técnicas e comportamentais relevantes para a área;",
            "Registrar as experiências e os aprendizados obtidos durante o período de estágio.",
        ]

        return "\n".join(objetivos)

    @staticmethod
    def _gerar_historia_empresa(dados_aluno: dict) -> str:
        """
        Gera o texto sobre a empresa onde o estágio foi realizado.

        O texto é neutro e seguro: apresenta a empresa apenas como
        campo de estágio, sem inventar ano de fundação, trajetória,
        número de unidades ou qualquer outra informação não fornecida
        em dados_aluno.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto sobre a empresa.
        """
        return str(dados_aluno["HISTORIA_EMPRESA_INFORMADA"])

    @staticmethod
    def _gerar_descricao_area(dados_aluno: dict) -> str:
        """
        Gera o texto de descrição da área onde o estágio foi realizado.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto de descrição da área.
        """
        return str(dados_aluno["DESCRICAO_AREA_INFORMADA"])

    @staticmethod
    def _gerar_conclusao(dados_aluno: dict) -> str:
        """
        Gera o texto de conclusão do relatório.

        Args:
            dados_aluno (dict): Dados do aluno.

        Returns:
            str: Texto de conclusão.
        """
        nome_aluno = dados_aluno.get("NOME_ALUNO", "")
        area_estagio = dados_aluno.get("AREA_ESTAGIO", "")
        carga_horaria = dados_aluno.get("CARGA_HORARIA", "")

        return (
            f"Ao longo do período de estágio, {nome_aluno} pôde vivenciar na "
            f"prática os conhecimentos teóricos adquiridos durante o curso, "
            f"na área de {area_estagio}, cumprindo uma carga horária de "
            f"{carga_horaria}. A experiência contribuiu de forma significativa "
            f"para a formação acadêmica e profissional do estagiário, "
            f"reforçando a importância da integração entre teoria e prática."
        )
