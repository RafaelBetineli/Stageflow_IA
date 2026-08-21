# StageFlow IA

Sistema em Python para gerar documentos de estágio em DOCX a partir de uma
mensagem padronizada de WhatsApp.

O pipeline atual é local e determinístico. Ele não usa Ollama, modelos de
linguagem ou APIs externas para escrever as atividades.

## Fluxo principal

```text
data/mensagem_zap.txt
  -> WhatsAppParser
  -> InputValidator
  -> DataEnricher
  -> resolução da área de estágio
  -> seleção determinística de atividades
  -> composição e validação dos relatos
  -> validação de originalidade
  -> gate antiplágio externo (quando requerido)
  -> preenchimento dos templates DOCX
  -> output/docx/
```

O mesmo conjunto de dados produz a mesma seleção e a mesma variante textual.
Alunos ou módulos diferentes recebem combinações distintas. O registro local
de originalidade armazena apenas impressões digitais dos textos anteriores.

## Áreas disponíveis

- Biomedicina estética
- Farmácia em drogaria
- Farmácia hospitalar
- Farmácia de manipulação
- Farmácia em controle de qualidade

Todas as knowledge bases seguem o contrato enriquecido com fatos permitidos,
papel do estagiário e restrições de validação. A composição mantém o estudante
como observador ou auxiliar sob supervisão e rejeita afirmações clínicas não
autorizadas.

As citações e referências bibliográficas são resolvidas a partir dos catálogos
verificados em `knowledge_base/references/`. Todas as cinco áreas disponíveis
possuem catálogo próprio, e cada atividade referencia ao menos uma fonte real.

## Requisitos

- Python 3.10 ou superior
- `python-docx==1.2.0`

Instalação:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Execução

1. Copie `data/mensagem_zap.example.txt` para `data/mensagem_zap.txt`.
2. Substitua todos os dados fictícios pelos dados do estágio.
3. Execute, a partir da raiz do projeto:

```powershell
python src\pipeline_whatsapp_docx.py --input data\mensagem_zap.txt --output output\docx
```

O pipeline mantém os dados pessoais apenas em memória e grava os três documentos
em `output/docx/`. A entrada real e os documentos gerados são ignorados pelo Git.
Use `--quantidade 1`, `2` ou `3` para alterar o número de atividades. Erros de
entrada, composição ou preenchimento interrompem a execução com código de saída
não zero, sem publicar documentos parciais.

## Verificação antiplágio externa

O gate externo usa a API individual do PlagiarismCheck.org e permanece
desativado por padrão. Para torná-lo obrigatório antes da publicação dos DOCX:

```powershell
$env:STAGEFLOW_PLAGIARISM_MODE = "required"
$env:STAGEFLOW_PLAGIARISM_TOKEN = "SEU_TOKEN"
python src\pipeline_whatsapp_docx.py --input data\mensagem_zap.txt --output output\docx
```

O token deve permanecer somente no ambiente; arquivos `.env` são ignorados pelo
Git. O serviço externo pode consumir créditos da conta. Consulte os termos e a
política de retenção do provedor antes do uso com dados reais.

Somente os relatos `ATV1...ATV3`, sem dados cadastrais e sem os marcadores das
citações, são enviados. O pipeline consulta o resultado por polling e solicita
a exclusão remota do scan ao final. Localmente, `output/plagiarism_registry.json`
guarda apenas um hash opaco, a porcentagem e a quantidade de fontes.

Configurações opcionais:

- `STAGEFLOW_PLAGIARISM_MAX_PERCENT`: limite de aprovação, padrão `25`.
- `STAGEFLOW_PLAGIARISM_TIMEOUT_SECONDS`: prazo total de polling, padrão `120`.
- `STAGEFLOW_PLAGIARISM_POLL_SECONDS`: intervalo entre consultas, padrão `3`.

Uma primeira reprovação aciona somente uma nova variante textual. Se a segunda
versão exceder o limite, ou se o provedor falhar no modo `required`, nenhum DOCX
é publicado. No modo `disabled`, o terminal informa explicitamente que a
verificação externa não foi executada.

Campos textuais longos podem continuar em linhas recuadas:

```text
História da empresa: Primeiro parágrafo ou linha.
  Continuação do mesmo campo.
```

## Estrutura

```text
stageflow_ia/
|-- data/
|   |-- mensagem_zap.example.txt
|   `-- mensagem_zap.txt              # local, ignorado pelo Git
|-- knowledge_base/
|   |-- references/
|   `-- *.json
|-- src/
|   |-- pipeline_whatsapp_docx.py
|   |-- activity_pipeline.py
|   |-- activity_deterministic_composer.py
|   |-- activity_draft_validator.py
|   |-- activity_originality.py
|   |-- activity_bibliography.py
|   |-- plagiarism_gate.py
|   `-- document_generator.py
|-- templates/
|   |-- biomedicina/
|   `-- farmacia/
|-- tests/
`-- requirements.txt
```

## Garantias da geração

- 4 a 6 parágrafos e 420 a 700 palavras por atividade.
- Aberturas, estruturas e tamanhos de parágrafo variáveis.
- Uso exclusivo dos fatos autorizados pela knowledge base.
- Validações estruturais, estilísticas e clínicas determinísticas.
- Uma recomposição determinística no máximo em caso de similaridade excessiva.
- Gate externo configurável antes da publicação, com uma nova variante no máximo.
- Falha explícita quando uma atividade não puder ser composta e validada.
- Verificação de placeholders no corpo, tabelas, cabeçalhos e rodapés.
- Publicação conjunta dos três DOCX somente após a geração completa.
- Referências listadas no documento somente quando citadas no texto.

## Validação

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

O GitHub Actions executa a mesma suíte em cada `push` e `pull_request`.

## Homologação de originalidade

Para avaliar todas as áreas em lote, sem gravar os relatos gerados:

```powershell
python src\originality_audit.py --reports-per-area 25
```

A auditoria percorre todas as atividades nos três perfis narrativos, desconsidera
citações e frases técnicas fixas da knowledge base no cálculo ajustado e exige
relatórios, atividades, aberturas e parágrafos únicos. O limite padrão de
similaridade Jaccard ajustada é `0.65`. O arquivo
`output/originality_audit.json` contém somente áreas, contagens, máximos de
similaridade e resultado de aprovação; nenhum texto ou dado pessoal é salvo.

Antes de publicar uma nova knowledge base, toda atividade deve passar por
`parse_activity_collection`, possuir ao menos um item em `referencias_ids` e
usar somente IDs existentes no catálogo correspondente.
