"""Gate externo de similaridade sem persistir os relatos analisados."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol


INLINE_CITATION_PATTERN = re.compile(
    r"\([^()\n]{1,160},\s*\d{4}[a-z]?\)",
    flags=re.IGNORECASE,
)
PROVIDER_NAME = "plagiarismcheck.org"
PROVIDER_BASE_URL = "https://plagiarismcheck.org"


class PlagiarismError(RuntimeError):
    """Erro base da verificação externa de similaridade."""


class PlagiarismConfigurationError(PlagiarismError):
    """A política antiplágio está incompleta ou inválida."""


class PlagiarismProviderError(PlagiarismError):
    """O provedor não respondeu com um resultado utilizável."""


class PlagiarismTimeoutError(PlagiarismProviderError):
    """O provedor não concluiu a análise dentro do prazo."""


@dataclass(frozen=True)
class PlagiarismPolicy:
    mode: str = "disabled"
    maximum_similarity_percent: float = 25.0
    timeout_seconds: float = 120.0
    poll_interval_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.mode not in {"disabled", "required"}:
            raise PlagiarismConfigurationError(
                "STAGEFLOW_PLAGIARISM_MODE deve ser disabled ou required"
            )
        if not 0.0 <= self.maximum_similarity_percent <= 100.0:
            raise PlagiarismConfigurationError(
                "o limite antiplágio deve estar entre 0 e 100"
            )
        if self.timeout_seconds <= 0:
            raise PlagiarismConfigurationError("o timeout antiplágio deve ser positivo")
        if self.poll_interval_seconds < 0:
            raise PlagiarismConfigurationError(
                "o intervalo de consulta antiplágio não pode ser negativo"
            )

    @classmethod
    def from_environment(cls) -> "PlagiarismPolicy":
        try:
            return cls(
                mode=os.getenv("STAGEFLOW_PLAGIARISM_MODE", "disabled")
                .strip()
                .casefold(),
                maximum_similarity_percent=float(
                    os.getenv("STAGEFLOW_PLAGIARISM_MAX_PERCENT", "25")
                ),
                timeout_seconds=float(
                    os.getenv("STAGEFLOW_PLAGIARISM_TIMEOUT_SECONDS", "120")
                ),
                poll_interval_seconds=float(
                    os.getenv("STAGEFLOW_PLAGIARISM_POLL_SECONDS", "3")
                ),
            )
        except ValueError as error:
            raise PlagiarismConfigurationError(
                "configuração numérica antiplágio inválida"
            ) from error


@dataclass(frozen=True)
class PlagiarismResult:
    provider: str
    similarity_percent: float
    source_count: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.similarity_percent <= 100.0:
            raise PlagiarismProviderError(
                "o provedor retornou uma porcentagem fora do intervalo esperado"
            )
        if self.source_count < 0:
            raise PlagiarismProviderError(
                "o provedor retornou uma quantidade de fontes inválida"
            )


@dataclass(frozen=True)
class PlagiarismDecision:
    skipped: bool
    cache_hit: bool
    maximum_similarity_percent: float
    result: PlagiarismResult | None = None

    @property
    def is_acceptable(self) -> bool:
        return self.skipped or (
            self.result is not None
            and self.result.similarity_percent <= self.maximum_similarity_percent
        )


class PlagiarismChecker(Protocol):
    provider: str

    def check(self, text: str) -> PlagiarismResult:
        """Verifica um texto sem receber dados de identidade do relatório."""


class JsonTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        data: bytes | None,
        timeout: float,
    ) -> object:
        """Executa uma requisição e devolve o JSON decodificado."""


class UrllibJsonTransport:
    """Transporte mínimo que não inclui corpo remoto em mensagens de erro."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        data: bytes | None,
        timeout: float,
    ) -> object:
        request = urllib.request.Request(
            url,
            data=data,
            headers=dict(headers),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise PlagiarismProviderError(
                        "resposta antiplágio excedeu o limite permitido"
                    )
        except urllib.error.HTTPError as error:
            raise PlagiarismProviderError(
                f"provedor antiplágio respondeu HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise PlagiarismProviderError(
                "não foi possível acessar o provedor antiplágio"
            ) from error

        try:
            return json.loads(payload.decode("utf-8")) if payload else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PlagiarismProviderError(
                "provedor antiplágio retornou JSON inválido"
            ) from error


def prepare_activity_text(sections: Iterable[str]) -> str:
    """Remove marcadores de citação e une somente os relatos das atividades."""
    prepared_sections: list[str] = []
    for section in sections:
        paragraphs = [
            " ".join(INLINE_CITATION_PATTERN.sub(" ", paragraph).split())
            for paragraph in re.split(r"\n\s*\n", section.strip())
            if paragraph.strip()
        ]
        if paragraphs:
            prepared_sections.append("\n\n".join(paragraphs))
    prepared = "\n\n".join(prepared_sections)
    if not prepared:
        raise PlagiarismError("nenhum relato disponível para verificação antiplágio")
    return prepared


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PlagiarismCheckOrgClient:
    """Cliente de polling para a API individual do PlagiarismCheck.org."""

    provider = PROVIDER_NAME

    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 3.0,
        transport: JsonTransport | None = None,
        sleeper=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        if not token.strip():
            raise PlagiarismConfigurationError(
                "STAGEFLOW_PLAGIARISM_TOKEN é obrigatório no modo required"
            )
        self._token = token.strip()
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.transport = transport or UrllibJsonTransport()
        self._sleeper = sleeper
        self._monotonic = monotonic

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "X-API-TOKEN": self._token,
        }

    @staticmethod
    def _object(value: object, name: str) -> dict:
        if not isinstance(value, dict):
            raise PlagiarismProviderError(
                f"resposta antiplágio sem objeto {name} válido"
            )
        return value

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
    ) -> object:
        headers = self._headers
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self.transport.request(
            method,
            f"{PROVIDER_BASE_URL}{path}",
            headers=headers,
            data=data,
            timeout=self.timeout_seconds,
        )

    def _submit(self, text: str) -> int:
        payload = self._request(
            "POST",
            "/api/v1/text",
            data=urllib.parse.urlencode(
                {
                    "text": text,
                    "filename": "stageflow_activities.txt",
                }
            ).encode("utf-8"),
        )
        root = self._object(payload, "raiz")
        data = self._object(root.get("data"), "data")
        text_data = self._object(data.get("text"), "text")
        scan_id = text_data.get("id")
        if not isinstance(scan_id, int) or isinstance(scan_id, bool):
            raise PlagiarismProviderError(
                "provedor antiplágio não retornou um ID de análise válido"
            )
        return scan_id

    def _poll_result(self, scan_id: int) -> PlagiarismResult:
        deadline = self._monotonic() + self.timeout_seconds
        while True:
            payload = self._request("GET", f"/api/v1/text/{scan_id}")
            root = self._object(payload, "raiz")
            data = self._object(root.get("data"), "data")
            report = data.get("report")
            if isinstance(report, dict) and report.get("percent") is not None:
                try:
                    similarity = float(report["percent"])
                    source_count = int(report.get("source_count", 0))
                except (TypeError, ValueError) as error:
                    raise PlagiarismProviderError(
                        "provedor antiplágio retornou métricas inválidas"
                    ) from error
                return PlagiarismResult(
                    provider=self.provider,
                    similarity_percent=similarity,
                    source_count=source_count,
                )

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise PlagiarismTimeoutError(
                    "provedor antiplágio não concluiu a análise no prazo"
                )
            self._sleeper(min(self.poll_interval_seconds, remaining))

    def _delete(self, scan_id: int) -> None:
        self._request("DELETE", f"/api/v1/text/{scan_id}")

    def check(self, text: str) -> PlagiarismResult:
        scan_id: int | None = None
        try:
            scan_id = self._submit(text)
            return self._poll_result(scan_id)
        finally:
            if scan_id is not None:
                try:
                    self._delete(scan_id)
                except PlagiarismError:
                    pass


class PlagiarismRegistry:
    """Cache atômico de resultados que persiste somente hashes e métricas."""

    FORMAT_VERSION = 1

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._checks: dict[str, PlagiarismResult] = {}
        if self.path is not None and self.path.exists():
            self._load()

    @staticmethod
    def _cache_key(content_hash: str, provider: str) -> str:
        return hashlib.sha256(
            f"v1:{provider}:{content_hash}".encode("utf-8")
        ).hexdigest()

    def get(self, content_hash: str, provider: str) -> PlagiarismResult | None:
        return self._checks.get(self._cache_key(content_hash, provider))

    def add(self, content_hash: str, result: PlagiarismResult) -> None:
        self._checks[self._cache_key(content_hash, result.provider)] = result
        self._save()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PlagiarismConfigurationError(
                "cache antiplágio inválido"
            ) from error
        if not isinstance(payload, dict) or payload.get("version") != self.FORMAT_VERSION:
            raise PlagiarismConfigurationError("versão inválida do cache antiplágio")
        checks = payload.get("checks")
        if not isinstance(checks, dict):
            raise PlagiarismConfigurationError("campo checks inválido no cache antiplágio")

        loaded: dict[str, PlagiarismResult] = {}
        for key, value in checks.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise PlagiarismConfigurationError("entrada inválida no cache antiplágio")
            try:
                loaded[key] = PlagiarismResult(
                    provider=str(value["provider"]),
                    similarity_percent=float(value["similarity_percent"]),
                    source_count=int(value["source_count"]),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise PlagiarismConfigurationError(
                    "métrica inválida no cache antiplágio"
                ) from error
        self._checks = loaded

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.FORMAT_VERSION,
            "checks": {
                key: {
                    "provider": result.provider,
                    "similarity_percent": result.similarity_percent,
                    "source_count": result.source_count,
                }
                for key, result in self._checks.items()
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class PlagiarismGate:
    """Aplica política, cache e verificação externa sobre os relatos."""

    def __init__(
        self,
        policy: PlagiarismPolicy,
        *,
        checker: PlagiarismChecker | None = None,
        registry: PlagiarismRegistry | None = None,
    ) -> None:
        if policy.mode == "required" and checker is None:
            raise PlagiarismConfigurationError(
                "um verificador antiplágio é obrigatório no modo required"
            )
        self.policy = policy
        self.checker = checker
        self.registry = registry or PlagiarismRegistry()

    @classmethod
    def from_environment(cls, registry_path: str | Path) -> "PlagiarismGate":
        policy = PlagiarismPolicy.from_environment()
        checker: PlagiarismChecker | None = None
        if policy.mode == "required":
            checker = PlagiarismCheckOrgClient(
                os.getenv("STAGEFLOW_PLAGIARISM_TOKEN", ""),
                timeout_seconds=policy.timeout_seconds,
                poll_interval_seconds=policy.poll_interval_seconds,
            )
        return cls(
            policy,
            checker=checker,
            registry=(
                PlagiarismRegistry(registry_path)
                if policy.mode == "required"
                else PlagiarismRegistry()
            ),
        )

    def verify(self, sections: Iterable[str]) -> PlagiarismDecision:
        if self.policy.mode == "disabled":
            return PlagiarismDecision(
                skipped=True,
                cache_hit=False,
                maximum_similarity_percent=self.policy.maximum_similarity_percent,
            )

        prepared = prepare_activity_text(sections)
        content_hash = content_fingerprint(prepared)
        result = self.registry.get(content_hash, self.checker.provider)
        cache_hit = result is not None
        if result is None:
            result = self.checker.check(prepared)
            self.registry.add(content_hash, result)
        return PlagiarismDecision(
            skipped=False,
            cache_hit=cache_hit,
            maximum_similarity_percent=self.policy.maximum_similarity_percent,
            result=result,
        )


class PlagiarismRejected(PlagiarismError):
    """As duas variantes permitidas excederam o limite configurado."""

    def __init__(self, result: PlagiarismResult, *, attempts: int) -> None:
        super().__init__(
            "similaridade externa reprovada após "
            f"{attempts} tentativa(s): {result.similarity_percent:.2f}%"
        )
        self.result = result
        self.attempts = attempts
