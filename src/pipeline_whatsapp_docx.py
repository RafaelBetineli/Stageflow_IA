"""Pipeline local e determinístico para gerar os três documentos de estágio."""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from tempfile import TemporaryDirectory

from activity_originality import ReportOriginalityRegistry
from activity_pipeline import ActivityPipeline
from activity_repository import ActivityRepository
from data_enricher import DataEnricher
from document_generator import DocumentGenerator
from input_validator import InputValidator
from report_identity import build_report_identity
from report_section_generator import ReportSectionGenerator
from whatsapp_parser import WhatsAppParser


RAIZ = Path(__file__).resolve().parent
PROJETO = RAIZ.parent
CAMINHO_MENSAGEM = PROJETO / "data" / "mensagem_zap.txt"
PASTA_SAIDA = PROJETO / "output" / "docx"
PASTA_KNOWLEDGE_BASE = PROJETO / "knowledge_base"
PASTA_TEMPLATES_BASE = PROJETO / "templates"

MAPEAMENTO_AREA_ESTAGIO = {
    "estetica": {
        "knowledge_base": "biomedicina_estetica.json",
        "pasta_templates": "biomedicina",
        "sufixo_template": "biomedicina",
    },
    "drogaria": {
        "knowledge_base": "farmacia_drogaria.json",
        "pasta_templates": "farmacia",
        "sufixo_template": "farmacia",
    },
    "hospitalar": {
        "knowledge_base": "farmacia_hospitalar.json",
        "pasta_templates": "farmacia",
        "sufixo_template": "farmacia",
    },
    "manipulacao": {
        "knowledge_base": "farmacia_manipulacao.json",
        "pasta_templates": "farmacia",
        "sufixo_template": "farmacia",
    },
    "controle de qualidade": {
        "knowledge_base": "farmacia_controle_qualidade.json",
        "pasta_templates": "farmacia",
        "sufixo_template": "farmacia",
    },
}


def sanitizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFD", nome)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_]", "", sem_acento.lower().replace(" ", "_"))


def normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = sem_acento.encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().lower()


def resolver_contexto_estagio(area_estagio: str) -> dict:
    area_normalizada = normalizar_texto(area_estagio)
    config_area = MAPEAMENTO_AREA_ESTAGIO.get(area_normalizada)
    if not config_area:
        disponiveis = ", ".join(MAPEAMENTO_AREA_ESTAGIO)
        raise ValueError(
            f"Área de estágio não reconhecida: '{area_estagio}'. "
            f"Áreas disponíveis: {disponiveis}."
        )

    knowledge_base = PASTA_KNOWLEDGE_BASE / config_area["knowledge_base"]
    pasta_templates = PASTA_TEMPLATES_BASE / config_area["pasta_templates"]
    sufixo = config_area["sufixo_template"]
    templates = (
        ("relatorio", pasta_templates / f"modelo_relatorio_{sufixo}_automatizado.docx"),
        ("plano_estagio", pasta_templates / f"modelo_plano_{sufixo}_automatizado.docx"),
        ("termo_compromisso", pasta_templates / f"modelo_termo_{sufixo}_automatizado.docx"),
    )
    return {"knowledge_base": knowledge_base, "templates": templates}


def selecionar_titulos_atividades(
    dados_aluno: dict,
    atividades_disponiveis: list[dict],
    quantidade: int = 3,
) -> list[str]:
    if not 1 <= quantidade <= 3:
        raise ValueError("A quantidade de atividades deve estar entre 1 e 3.")
    if quantidade > len(atividades_disponiveis):
        raise ValueError(
            f"A base possui apenas {len(atividades_disponiveis)} atividades; "
            f"não é possível selecionar {quantidade}."
        )

    texto_base = "".join(
        str(dados_aluno.get(field, ""))
        for field in ("NOME_ALUNO", "RA_ALUNO", "AREA_ESTAGIO", "MODULO_ESTAGIO")
    )
    semente = int(hashlib.sha256(texto_base.encode("utf-8")).hexdigest(), 16)
    atividades = atividades_disponiveis.copy()
    random.Random(semente).shuffle(atividades)
    titulos = [str(atividade.get("titulo", "")).strip() for atividade in atividades[:quantidade]]
    if any(not titulo for titulo in titulos):
        raise ValueError("A knowledge base contém atividade sem título.")
    return titulos


def _validar_arquivos(contexto: dict) -> None:
    caminhos = (contexto["knowledge_base"], *(path for _, path in contexto["templates"]))
    ausentes = [str(path) for path in caminhos if not path.is_file()]
    if ausentes:
        raise FileNotFoundError("Arquivos obrigatórios ausentes:\n- " + "\n- ".join(ausentes))


def _publicar_documentos(temporarios: list[tuple[Path, Path]]) -> None:
    backups: list[tuple[Path, Path]] = []
    publicados: list[Path] = []
    try:
        for _, destino in temporarios:
            if destino.exists():
                backup = destino.with_suffix(destino.suffix + ".bak")
                backup.unlink(missing_ok=True)
                destino.replace(backup)
                backups.append((backup, destino))
        for origem, destino in temporarios:
            origem.replace(destino)
            publicados.append(destino)
    except Exception:
        for destino in publicados:
            destino.unlink(missing_ok=True)
        for backup, destino in backups:
            backup.replace(destino)
        raise
    else:
        for backup, _ in backups:
            backup.unlink(missing_ok=True)


def _validar_sobrescrita(destinos: tuple[Path, ...], overwrite: bool) -> None:
    existentes = tuple(destino for destino in destinos if destino.exists())
    if existentes and not overwrite:
        lista = "\n- ".join(str(path) for path in existentes)
        raise FileExistsError(
            "Documentos de saída já existem. Use --overwrite para substituí-los:\n"
            f"- {lista}"
        )


def run_pipeline(
    input_path: str | Path = CAMINHO_MENSAGEM,
    output_dir: str | Path = PASTA_SAIDA,
    quantidade: int = 3,
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    entrada = Path(input_path)
    saida = Path(output_dir)
    if not entrada.is_file():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {entrada}")

    dados = WhatsAppParser().parse(entrada.read_text(encoding="utf-8"))
    if not dados:
        raise ValueError("Nenhum campo reconhecido foi encontrado na entrada.")
    InputValidator().validate(dados)

    contexto = resolver_contexto_estagio(dados["AREA_ESTAGIO"])
    _validar_arquivos(contexto)
    dados_enriquecidos = DataEnricher().enrich(dados, activity_count=quantidade)

    nome_sanitizado = sanitizar_nome(dados_enriquecidos["NOME_ALUNO"])
    if not nome_sanitizado:
        raise ValueError("Nome do aluno não produz um nome de arquivo válido.")
    destinos = tuple(
        saida / f"{prefixo}_{nome_sanitizado}.docx"
        for prefixo, _ in contexto["templates"]
    )
    _validar_sobrescrita(destinos, overwrite)

    repository = ActivityRepository(str(contexto["knowledge_base"]))
    atividades_disponiveis = repository.get_all()
    titulos = selecionar_titulos_atividades(
        dados_enriquecidos,
        atividades_disponiveis,
        quantidade,
    )

    report_identity = build_report_identity(dados_enriquecidos)
    registry = ReportOriginalityRegistry(saida.parent / "originality_registry.json")
    activity_pipeline = ActivityPipeline(
        repository,
        area_estagio=dados_enriquecidos["AREA_ESTAGIO"],
        report_seed=report_identity.seed,
        variant_index=report_identity.variant_index,
        originality_registry=registry,
    )
    dados_atividades = activity_pipeline.build(titulos)
    if activity_pipeline.count_selected(titulos) != quantidade:
        raise RuntimeError("Nem todas as atividades selecionadas foram encontradas.")

    dados_secoes = ReportSectionGenerator().generate(
        dados_enriquecidos,
        referencias=dados_atividades.get("REFERENCIAS"),
    )
    dados_finais = {**dados_enriquecidos, **dados_atividades, **dados_secoes}

    saida.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".stageflow_", dir=saida) as temporary_dir:
        temporarios: list[tuple[Path, Path]] = []
        for (prefixo, template), destino in zip(contexto["templates"], destinos):
            temporario = Path(temporary_dir) / f"{prefixo}.docx"
            DocumentGenerator(template).generate(dados_finais, temporario)
            temporarios.append((temporario, destino))
        _publicar_documentos(temporarios)

    return destinos


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=CAMINHO_MENSAGEM)
    parser.add_argument("--output", type=Path, default=PASTA_SAIDA)
    parser.add_argument("--quantidade", type=int, default=3)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="substitui documentos já existentes para o mesmo aluno",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        caminhos = run_pipeline(
            args.input,
            args.output,
            args.quantidade,
            overwrite=args.overwrite,
        )
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print("Documentos gerados:")
    for caminho in caminhos:
        print(f"- {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
