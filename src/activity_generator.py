"""Integra a geração estruturada de atividades ao pipeline existente."""

from typing import Protocol

from activity_bibliography import BibliographyCatalog, load_project_bibliography_catalog
from activity_contract import ActivityContractError, EnrichedActivity
from activity_deterministic_composer import DeterministicActivityComposer
from activity_draft import ActivityCompositionError, StructuredDraft
from activity_draft_validator import DraftValidationReport
from activity_narrative_planner import NarrativePlan, build_narrative_plan
from activity_originality import (
    ActivityFingerprint,
    ActivityOriginalityValidator,
    OriginalityReport,
    ReportOriginalityRegistry,
    ReportOriginalityRejected,
    ReportOriginalityValidator,
)


class ActivityTextResult(Protocol):
    draft: StructuredDraft
    final_report: DraftValidationReport
    citation_ids: tuple[str, ...]


class ActivityTextWriter(Protocol):
    def write(
        self,
        activity: EnrichedActivity,
        plan: NarrativePlan,
    ) -> ActivityTextResult:
        """Gera e valida o relato de uma atividade."""


class ActivityGenerationError(RuntimeError):
    """Uma atividade não pôde ser composta e validada."""


class ActivityGenerator:
    """Gera placeholders ATV sem alterar a interface pública do pipeline."""

    def __init__(
        self,
        max_atividades: int = 10,
        area_estagio: str = "não informado",
        *,
        writer: ActivityTextWriter | None = None,
        report_seed: str = "default",
        variant_index: int = 0,
        originality_validator: ReportOriginalityValidator | None = None,
        activity_originality_validator: ActivityOriginalityValidator | None = None,
        originality_registry: ReportOriginalityRegistry | None = None,
        bibliography_catalog: BibliographyCatalog | None = None,
    ) -> None:
        self.max_atividades = max_atividades
        self.area_estagio = area_estagio
        self.report_seed = report_seed
        self.variant_index = variant_index
        self._writer_override = writer
        self.bibliography_catalog = (
            bibliography_catalog
            if bibliography_catalog is not None
            else load_project_bibliography_catalog()
        )
        self.writer = writer or self._build_default_writer(attempt=0)
        self.originality_validator = originality_validator or ReportOriginalityValidator()
        self.activity_originality_validator = (
            activity_originality_validator or ActivityOriginalityValidator()
        )
        self.originality_registry = originality_registry or ReportOriginalityRegistry()
        self.last_originality_report: OriginalityReport | None = None
        self.last_activity_originality_reports: tuple[OriginalityReport, ...] = ()
        self.last_composition_attempts = 0
        self.last_citation_ids: tuple[str, ...] = ()
        self._attempt_citation_ids: list[str] = []

    def _build_default_writer(self, *, attempt: int) -> DeterministicActivityComposer:
        return DeterministicActivityComposer(
            report_seed=self.report_seed,
            variant_index=self.variant_index + attempt,
            bibliography_catalog=self.bibliography_catalog,
        )

    def _writer_for_attempt(self, attempt: int) -> ActivityTextWriter:
        if self._writer_override is not None:
            return self._writer_override
        return self._build_default_writer(attempt=attempt)

    def generate(self, atividades: list[dict]) -> dict[str, str]:
        """Preenche ATV1...ATVn ou interrompe a geração na primeira falha."""
        for attempt in range(2):
            textos = self._generate_once(
                atividades,
                writer=self._writer_for_attempt(attempt),
            )
            sections = tuple(
                textos[f"ATV{position}"]
                for position in range(1, min(len(atividades), self.max_atividades) + 1)
                if textos[f"ATV{position}"].strip()
            )
            report = self.originality_validator.validate(
                sections,
                self.originality_registry.previous_for(self.report_seed),
            )
            activity_entries = tuple(
                (
                    str(atividades[position - 1].get("titulo", "")),
                    textos[f"ATV{position}"],
                )
                for position in range(
                    1,
                    min(len(atividades), self.max_atividades) + 1,
                )
                if textos[f"ATV{position}"].strip()
            )
            activity_reports = tuple(
                self.activity_originality_validator.validate(
                    ActivityFingerprint.from_activity(title, text),
                    self.originality_registry.previous_activities_for(
                        self.report_seed,
                        title,
                    ),
                )
                for title, text in activity_entries
            )
            self.last_activity_originality_reports = activity_reports
            combined_report = OriginalityReport(
                report.issues
                + tuple(
                    issue
                    for activity_report in activity_reports
                    for issue in activity_report.issues
                ),
                max(
                    (report.maximum_similarity,)
                    + tuple(
                        activity_report.maximum_similarity
                        for activity_report in activity_reports
                    )
                ),
            )
            self.last_originality_report = combined_report
            self.last_composition_attempts = attempt + 1
            if combined_report.is_acceptable:
                self.last_citation_ids = tuple(
                    dict.fromkeys(self._attempt_citation_ids)
                )
                self.originality_registry.add(
                    self.report_seed,
                    sections,
                    activity_entries,
                )
                return textos
            if attempt == 0:
                print("[ORIGINALIDADE] Recomposição única acionada.")

        raise ReportOriginalityRejected(
            self.last_originality_report,
            attempts=self.last_composition_attempts,
        )

    def _generate_once(
        self,
        atividades: list[dict],
        *,
        writer: ActivityTextWriter,
    ) -> dict[str, str]:
        textos: dict[str, str] = {}
        self._attempt_citation_ids = []

        for posicao in range(1, self.max_atividades + 1):
            placeholder = f"ATV{posicao}"
            indice = posicao - 1
            if indice >= len(atividades):
                textos[placeholder] = ""
                continue

            textos[placeholder] = self._gerar_texto_atividade(
                atividades[indice],
                posicao,
                writer,
            )

        return textos

    def _gerar_texto_atividade(
        self,
        atividade_raw: dict,
        posicao: int,
        writer: ActivityTextWriter,
    ) -> str:
        titulo = str(atividade_raw.get("titulo", ""))

        try:
            activity = EnrichedActivity.from_dict(
                atividade_raw,
                path=f"atividade_ATV{posicao}",
            )
            plan = build_narrative_plan(activity, posicao)
            result = writer.write(activity, plan)
            self._attempt_citation_ids.extend(getattr(result, "citation_ids", ()))
            warnings = len(result.final_report.warning_issues)
            print(
                f"[ATIVIDADE] ATV{posicao} - {titulo}: aceito com "
                f"{result.final_report.total_words} palavras, "
                f"{warnings} aviso(s)."
            )
            return result.draft.text

        except (ActivityContractError, ActivityCompositionError) as error:
            raise ActivityGenerationError(
                f"ATV{posicao} ({titulo}) não pôde ser gerada: {error}"
            ) from error
        except Exception as error:
            raise ActivityGenerationError(
                f"ATV{posicao} ({titulo}) falhou com {type(error).__name__}: {error}"
            ) from error
