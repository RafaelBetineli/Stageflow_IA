"""
whatsapp_parser.py
==================
Converte mensagens padronizadas do WhatsApp em dicionários Python
compatíveis com os placeholders do sistema de geração de relatórios.

Responsabilidade única: texto → dict.

Não salva arquivos, não gera JSON, não depende de bibliotecas externas.
"""


class WhatsAppParser:
    """
    Interpreta mensagens do WhatsApp no formato 'Campo: Valor'
    e retorna um dicionário com as chaves mapeadas para o sistema.

    Fluxo interno do método parse():
        Para cada linha do texto recebido:
            1. Ignora linha vazia
            2. Verifica se contém ":"
            3. Separa campo e valor
            4. Busca o campo no CAMPO_MAP
            5. Se encontrado, adiciona ao dicionário de saída
    """

    # Mapeamento de rótulos do WhatsApp → chaves do sistema
    # Para adicionar novos campos, basta incluir uma entrada aqui.
    CAMPO_MAP: dict[str, str] = {
        "Nome aluno":       "NOME_ALUNO",
        "RA":               "RA_ALUNO",
        "Telefone aluno":   "TELEFONE_ALUNO",
        "E-mail aluno":     "EMAIL_ALUNO",
        "CPF":              "CPF",
        "RG":               "RG",

        "Endereço aluno":   "ENDERECO_ALUNO",
        "Bairro aluno":     "BAIRRO_ALUNO",
        "Cidade aluno":     "CIDADE_ALUNO",
        "Estado aluno":     "ESTADO_ALUNO",
        "CEP aluno":        "CEP_ALUNO",

        "Semestre":         "SEMESTRE",
        "Campus":           "CAMPUS",
        "Período":          "PERIODO",

        "Número da apólice": "APOLICE",
        "Seguradora":        "SEGURADORA",
        "Data início vigência": "DATA_INICIO_VIGENCIA",
        "Data fim vigência":    "DATA_FIM_VIGENCIA",

        "Nome fantasia":     "EMPRESA_FANTASIA",
        "Razão social":      "EMPRESA",
        "CNPJ":               "CNPJ",
        "Ramo empresa":       "RAMO_EMPRESA",

        "Endereço empresa":  "ENDERECO_EMPRESA",
        "Bairro empresa":    "BAIRRO_EMPRESA",
        "Cidade empresa":    "CIDADE_EMPRESA",
        "Telefone empresa":  "TELEFONE_EMPRESA",

        "Nome RT":           "NOME_RT",
        "E-mail RT":         "EMAIL_RT",
        "Conselho RT":       "CONSELHO_RT",
        "Cargo representante": "CARGO_REPRESENTANTE",

        "Área estágio":      "AREA_ESTAGIO",
        "Data início estágio": "DATA_INICIO_ESTAGIO",
        "Data fim estágio":   "DATA_FIM_ESTAGIO",
        "Carga horária":      "CARGA_HORARIA",
        "Carga horária semanal": "CARGA_SEMANAL",
        "Dias de estágio":    "DIAS_ESTAGIO",
        "Horário de estágio": "HORARIO_ESTAGIO",
        "Módulo estágio":     "MODULO_ESTAGIO",
        "Dependência":        "DEPENDENCIA",
        "Histórico dos módulos": "HISTORICO_MODULOS",
        "História da empresa": "HISTORIA_EMPRESA_INFORMADA",
        "Descrição da área":  "DESCRICAO_AREA_INFORMADA",
        "Relato de caso":     "COMPLEMENTAR1",
        "Interações medicamentosas": "COMPLEMENTAR2",
        "Observações do plano": "OBSERVACOES_PLANO",
    }

    def parse(self, texto: str) -> dict[str, str]:
        """
        Converte um texto de múltiplas linhas em um dicionário de dados.

        Parâmetros
        ----------
        texto : str
            String com uma ou mais linhas no formato 'Campo: Valor'.
            Linhas vazias e campos desconhecidos são ignorados. Linhas
            recuadas sem ``:`` continuam o último campo reconhecido.

        Retorna
        -------
        dict[str, str]
            Dicionário com as chaves mapeadas para o sistema.
            Exemplo: {"NOME_ALUNO": "João Silva", "RA_ALUNO": "123456"}
        """
        resultado: dict[str, str] = {}

        ultima_chave: str | None = None

        for linha in texto.splitlines():

            # 1. Ignora linhas vazias
            if not linha.strip():
                continue

            # 2. Linhas recuadas continuam campos textuais longos.
            if ":" not in linha:
                if ultima_chave is not None and linha[:1].isspace():
                    continuacao = linha.strip()
                    if continuacao:
                        resultado[ultima_chave] = (
                            f"{resultado[ultima_chave]}\n{continuacao}"
                        )
                continue

            # 3. Separa campo e valor pelo PRIMEIRO ":" encontrado
            #    Isso preserva valores que contenham ":" (ex: URLs, e-mails)
            campo_bruto, valor_bruto = linha.split(":", maxsplit=1)

            campo = campo_bruto.strip()
            valor = valor_bruto.strip()

            # 4. Busca o campo no mapeamento
            chave_sistema = self.CAMPO_MAP.get(campo)

            # 5. Adiciona ao resultado somente se o campo for reconhecido
            if chave_sistema is not None:
                resultado[chave_sistema] = valor
                ultima_chave = chave_sistema
            else:
                ultima_chave = None

        return resultado
