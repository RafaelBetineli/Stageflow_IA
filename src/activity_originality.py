"""Medição determinística de repetição entre relatórios de atividades."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


WORD_PATTERN = re.compile(r"\b\w+(?:[-']\w+)*\b", flags=re.UNICODE)
SENTENCE_PATTERN = re.compile(r"^.*?[.!?](?:\s|$)", flags=re.DOTALL)


def normalize_for_similarity(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(WORD_PATTERN.findall(without_marks))


def _paragraphs(sections: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        normalize_for_similarity(paragraph)
        for section in sections
        for paragraph in re.split(r"\n\s*\n", section.strip())
        if paragraph.strip()
    )


def _opening(section: str) -> str:
    match = SENTENCE_PATTERN.match(section.strip())
    sentence = match.group() if match else section.strip()
    return normalize_for_similarity(sentence)


def _ngrams(text: str, size: int = 5) -> frozenset[tuple[str, ...]]:
    words = normalize_for_similarity(text).split()
    if len(words) < size:
        return frozenset({tuple(words)}) if words else frozenset()
    return frozenset(tuple(words[index : index + size]) for index in range(len(words) - size + 1))


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ngram_hashes(text: str) -> frozenset[str]:
    return frozenset(_text_hash(" ".join(ngram)) for ngram in _ngrams(text))


def ngram_jaccard(left: str, right: str, *, size: int = 5) -> float:
    left_ngrams = _ngrams(left, size)
    right_ngrams = _ngrams(right, size)
    if not left_ngrams and not right_ngrams:
        return 1.0
    union = left_ngrams | right_ngrams
    return len(left_ngrams & right_ngrams) / len(union) if union else 0.0


@dataclass(frozen=True)
class ReportFingerprint:
    normalized_hash: str
    opening_hashes: tuple[str, ...]
    paragraph_hashes: tuple[str, ...]
    ngram_hashes: frozenset[str]

    @classmethod
    def from_sections(cls, sections: Iterable[str]) -> "ReportFingerprint":
        values = tuple(section.strip() for section in sections if section.strip())
        normalized = " ".join(normalize_for_similarity(section) for section in values)
        return cls(
            normalized_hash=_text_hash(normalized),
            opening_hashes=tuple(_text_hash(_opening(section)) for section in values),
            paragraph_hashes=tuple(_text_hash(paragraph) for paragraph in _paragraphs(values)),
            ngram_hashes=_ngram_hashes(normalized),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "normalized_hash": self.normalized_hash,
            "opening_hashes": list(self.opening_hashes),
            "paragraph_hashes": list(self.paragraph_hashes),
            "ngram_hashes": sorted(self.ngram_hashes),
        }

    @classmethod
    def from_dict(cls, data: object) -> "ReportFingerprint":
        if not isinstance(data, dict):
            raise ValueError("fingerprint deve ser um objeto")
        expected = {
            "normalized_hash",
            "opening_hashes",
            "paragraph_hashes",
            "ngram_hashes",
        }
        if set(data) != expected:
            raise ValueError("fingerprint possui campos inválidos")

        normalized_hash = data["normalized_hash"]
        opening_hashes = data["opening_hashes"]
        paragraph_hashes = data["paragraph_hashes"]
        ngram_hashes = data["ngram_hashes"]
        if not isinstance(normalized_hash, str):
            raise ValueError("normalized_hash inválido")
        for value, name in (
            (opening_hashes, "opening_hashes"),
            (paragraph_hashes, "paragraph_hashes"),
            (ngram_hashes, "ngram_hashes"),
        ):
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{name} inválido")
        return cls(
            normalized_hash=normalized_hash,
            opening_hashes=tuple(opening_hashes),
            paragraph_hashes=tuple(paragraph_hashes),
            ngram_hashes=frozenset(ngram_hashes),
        )


@dataclass(frozen=True)
class ActivityFingerprint:
    title_hash: str
    normalized_hash: str
    opening_hash: str
    paragraph_hashes: tuple[str, ...]
    ngram_hashes: frozenset[str]

    @classmethod
    def from_activity(cls, title: str, text: str) -> "ActivityFingerprint":
        normalized_title = normalize_for_similarity(title)
        normalized_text = normalize_for_similarity(text)
        paragraphs = _paragraphs((text,))
        return cls(
            title_hash=_text_hash(normalized_title),
            normalized_hash=_text_hash(normalized_text),
            opening_hash=_text_hash(_opening(text)),
            paragraph_hashes=tuple(_text_hash(paragraph) for paragraph in paragraphs),
            ngram_hashes=_ngram_hashes(normalized_text),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "title_hash": self.title_hash,
            "normalized_hash": self.normalized_hash,
            "opening_hash": self.opening_hash,
            "paragraph_hashes": list(self.paragraph_hashes),
            "ngram_hashes": sorted(self.ngram_hashes),
        }

    @classmethod
    def from_dict(cls, data: object) -> "ActivityFingerprint":
        if not isinstance(data, dict):
            raise ValueError("fingerprint de atividade deve ser um objeto")
        expected = {
            "title_hash",
            "normalized_hash",
            "opening_hash",
            "paragraph_hashes",
            "ngram_hashes",
        }
        if set(data) != expected:
            raise ValueError("fingerprint de atividade possui campos invalidos")

        scalar_fields = ("title_hash", "normalized_hash", "opening_hash")
        if any(not isinstance(data[field], str) for field in scalar_fields):
            raise ValueError("hash invalido no fingerprint de atividade")
        paragraph_hashes = data["paragraph_hashes"]
        ngram_hashes = data["ngram_hashes"]
        for value, name in (
            (paragraph_hashes, "paragraph_hashes"),
            (ngram_hashes, "ngram_hashes"),
        ):
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(f"{name} invalido no fingerprint de atividade")
        return cls(
            title_hash=data["title_hash"],
            normalized_hash=data["normalized_hash"],
            opening_hash=data["opening_hash"],
            paragraph_hashes=tuple(paragraph_hashes),
            ngram_hashes=frozenset(ngram_hashes),
        )


@dataclass(frozen=True)
class OriginalityIssue:
    code: str
    message: str
    previous_index: int | None = None


@dataclass(frozen=True)
class OriginalityReport:
    issues: tuple[OriginalityIssue, ...]
    maximum_similarity: float

    @property
    def is_acceptable(self) -> bool:
        return not self.issues


class ReportOriginalityValidator:
    """Rejeita duplicações exatas e similaridade textual excessiva."""

    def __init__(self, *, maximum_jaccard: float = 0.60) -> None:
        if not 0.0 <= maximum_jaccard <= 1.0:
            raise ValueError("maximum_jaccard deve estar entre 0 e 1")
        self.maximum_jaccard = maximum_jaccard

    def validate(
        self,
        candidate_sections: Iterable[str],
        previous_reports: Iterable[Iterable[str] | ReportFingerprint] = (),
    ) -> OriginalityReport:
        candidate = ReportFingerprint.from_sections(candidate_sections)
        issues: list[OriginalityIssue] = []
        maximum_similarity = 0.0

        if len(candidate.opening_hashes) != len(set(candidate.opening_hashes)):
            issues.append(
                OriginalityIssue(
                    "internal_repeated_opening",
                    "duas atividades do mesmo relatório possuem a mesma abertura",
                )
            )
        if len(candidate.paragraph_hashes) != len(set(candidate.paragraph_hashes)):
            issues.append(
                OriginalityIssue(
                    "internal_repeated_paragraph",
                    "o relatório contém parágrafos idênticos",
                )
            )

        for previous_index, sections in enumerate(previous_reports):
            previous = (
                sections
                if isinstance(sections, ReportFingerprint)
                else ReportFingerprint.from_sections(sections)
            )
            union = candidate.ngram_hashes | previous.ngram_hashes
            similarity = (
                len(candidate.ngram_hashes & previous.ngram_hashes) / len(union)
                if union
                else 1.0
            )
            maximum_similarity = max(maximum_similarity, similarity)

            if candidate.normalized_hash == previous.normalized_hash:
                issues.append(
                    OriginalityIssue(
                        "duplicate_report",
                        "texto integral idêntico a relatório anterior",
                        previous_index,
                    )
                )
            if (
                candidate.normalized_hash == previous.normalized_hash
                and set(candidate.opening_hashes) & set(previous.opening_hashes)
            ):
                issues.append(
                    OriginalityIssue(
                        "repeated_opening",
                        "uma abertura já foi usada em relatório anterior",
                        previous_index,
                    )
                )
            if set(candidate.paragraph_hashes) & set(previous.paragraph_hashes):
                issues.append(
                    OriginalityIssue(
                        "repeated_paragraph",
                        "um parágrafo já foi usado integralmente em relatório anterior",
                        previous_index,
                    )
                )
            if similarity > self.maximum_jaccard:
                issues.append(
                    OriginalityIssue(
                        "excessive_similarity",
                        f"similaridade {similarity:.3f} acima do limite {self.maximum_jaccard:.3f}",
                        previous_index,
                    )
                )

        unique: list[OriginalityIssue] = []
        seen: set[tuple[str, int | None]] = set()
        for issue in issues:
            identity = (issue.code, issue.previous_index)
            if identity not in seen:
                unique.append(issue)
                seen.add(identity)
        return OriginalityReport(tuple(unique), maximum_similarity)


class ActivityOriginalityValidator:
    """Compara uma atividade somente com versoes anteriores do mesmo titulo."""

    def __init__(self, *, maximum_jaccard: float = 0.65) -> None:
        if not 0.0 <= maximum_jaccard <= 1.0:
            raise ValueError("maximum_jaccard deve estar entre 0 e 1")
        self.maximum_jaccard = maximum_jaccard

    def validate(
        self,
        candidate: ActivityFingerprint,
        previous_activities: Iterable[ActivityFingerprint] = (),
    ) -> OriginalityReport:
        issues: list[OriginalityIssue] = []
        maximum_similarity = 0.0

        for previous_index, previous in enumerate(previous_activities):
            union = candidate.ngram_hashes | previous.ngram_hashes
            similarity = (
                len(candidate.ngram_hashes & previous.ngram_hashes) / len(union)
                if union
                else 1.0
            )
            maximum_similarity = max(maximum_similarity, similarity)

            if candidate.normalized_hash == previous.normalized_hash:
                issues.append(
                    OriginalityIssue(
                        "duplicate_activity",
                        "atividade integral identica a uma versao anterior",
                        previous_index,
                    )
                )
            if candidate.opening_hash == previous.opening_hash:
                issues.append(
                    OriginalityIssue(
                        "repeated_activity_opening",
                        "a atividade reutiliza uma abertura anterior",
                        previous_index,
                    )
                )
            if set(candidate.paragraph_hashes) & set(previous.paragraph_hashes):
                issues.append(
                    OriginalityIssue(
                        "repeated_activity_paragraph",
                        "a atividade reutiliza um paragrafo integral de versao anterior",
                        previous_index,
                    )
                )
            if similarity > self.maximum_jaccard:
                issues.append(
                    OriginalityIssue(
                        "excessive_activity_similarity",
                        f"similaridade da atividade {similarity:.3f} acima do limite "
                        f"{self.maximum_jaccard:.3f}",
                        previous_index,
                    )
                )

        unique: list[OriginalityIssue] = []
        seen: set[tuple[str, int | None]] = set()
        for issue in issues:
            identity = (issue.code, issue.previous_index)
            if identity not in seen:
                unique.append(issue)
                seen.add(identity)
        return OriginalityReport(tuple(unique), maximum_similarity)


class ReportOriginalityRegistry:
    """Mantém relatórios aceitos durante uma execução em lote."""

    FORMAT_VERSION = 2
    LEGACY_FORMAT_VERSION = 1

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._reports: dict[str, ReportFingerprint] = {}
        self._activities: dict[str, tuple[ActivityFingerprint, ...]] = {}
        if self.path is not None and self.path.exists():
            self._load()

    @property
    def reports(self) -> tuple[ReportFingerprint, ...]:
        return tuple(self._reports.values())

    def previous_for(self, report_id: str) -> tuple[ReportFingerprint, ...]:
        return tuple(
            fingerprint
            for existing_id, fingerprint in self._reports.items()
            if existing_id != report_id
        )

    def previous_activities_for(
        self,
        report_id: str,
        title: str,
    ) -> tuple[ActivityFingerprint, ...]:
        title_hash = _text_hash(normalize_for_similarity(title))
        return tuple(
            fingerprint
            for existing_id, fingerprints in self._activities.items()
            if existing_id != report_id
            for fingerprint in fingerprints
            if fingerprint.title_hash == title_hash
        )

    def add(
        self,
        report_id: str,
        sections: Iterable[str],
        activities: Iterable[tuple[str, str]] = (),
    ) -> None:
        section_values = tuple(sections)
        self._reports[report_id] = ReportFingerprint.from_sections(section_values)
        self._activities[report_id] = tuple(
            ActivityFingerprint.from_activity(title, text)
            for title, text in activities
            if text.strip()
        )
        self._save()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"registro de originalidade inválido: {error}") from error
        if not isinstance(data, dict) or data.get("version") not in {
            self.LEGACY_FORMAT_VERSION,
            self.FORMAT_VERSION,
        }:
            raise ValueError("versão inválida do registro de originalidade")
        reports = data.get("reports")
        if not isinstance(reports, dict):
            raise ValueError("campo reports inválido no registro de originalidade")
        if data["version"] == self.LEGACY_FORMAT_VERSION:
            self._reports = {
                str(report_id): ReportFingerprint.from_dict(fingerprint)
                for report_id, fingerprint in reports.items()
            }
            self._activities = {report_id: () for report_id in self._reports}
            return

        loaded_reports: dict[str, ReportFingerprint] = {}
        loaded_activities: dict[str, tuple[ActivityFingerprint, ...]] = {}
        for report_id, entry in reports.items():
            if not isinstance(entry, dict) or set(entry) != {"report", "activities"}:
                raise ValueError("entrada invalida no registro de originalidade")
            activities = entry["activities"]
            if not isinstance(activities, list):
                raise ValueError("activities invalido no registro de originalidade")
            normalized_id = str(report_id)
            loaded_reports[normalized_id] = ReportFingerprint.from_dict(entry["report"])
            loaded_activities[normalized_id] = tuple(
                ActivityFingerprint.from_dict(fingerprint)
                for fingerprint in activities
            )
        self._reports = loaded_reports
        self._activities = loaded_activities

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.FORMAT_VERSION,
            "reports": {
                report_id: {
                    "report": fingerprint.to_dict(),
                    "activities": [
                        activity.to_dict()
                        for activity in self._activities.get(report_id, ())
                    ],
                }
                for report_id, fingerprint in self._reports.items()
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class ReportOriginalityRejected(RuntimeError):
    """O relatório continuou excessivamente semelhante após a recomposição."""

    def __init__(self, report: OriginalityReport, *, attempts: int) -> None:
        codes = ", ".join(dict.fromkeys(issue.code for issue in report.issues))
        super().__init__(f"originalidade rejeitada após {attempts} tentativa(s): {codes}")
        self.report = report
        self.attempts = attempts
