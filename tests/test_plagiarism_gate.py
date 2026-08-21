"""Testes do gate antiplágio, cache privado e cliente HTTP."""

import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

from plagiarism_gate import (
    PlagiarismCheckOrgClient,
    PlagiarismConfigurationError,
    PlagiarismGate,
    PlagiarismPolicy,
    PlagiarismRegistry,
    PlagiarismResult,
    content_fingerprint,
    prepare_activity_text,
)


class SequenceChecker:
    provider = "fake-provider"

    def __init__(self, results: list[PlagiarismResult]) -> None:
        self.results = results
        self.texts: list[str] = []

    def check(self, text: str) -> PlagiarismResult:
        self.texts.append(text)
        return self.results.pop(0)


class RecordingTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, *, headers, data, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class PlagiarismGateTests(unittest.TestCase):
    def test_preparation_removes_citations_and_preserves_only_activity_text(self) -> None:
        prepared = prepare_activity_text(
            (
                "Relato técnico (AUTOR, 2025).\n\nSegundo parágrafo.",
                "Outra atividade (SILVA et al., 2024b).",
            )
        )

        self.assertNotIn("AUTOR", prepared)
        self.assertNotIn("SILVA", prepared)
        self.assertIn("Relato técnico", prepared)
        self.assertIn("Outra atividade", prepared)

    def test_gate_reuses_hash_cache_without_persisting_text(self) -> None:
        result = PlagiarismResult("fake-provider", 12.5, 2)
        checker = SequenceChecker([result])

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "registry.json"
            gate = PlagiarismGate(
                PlagiarismPolicy(mode="required"),
                checker=checker,
                registry=PlagiarismRegistry(path),
            )
            first = gate.verify(("Conteúdo acadêmico confidencial.",))
            reloaded_gate = PlagiarismGate(
                PlagiarismPolicy(mode="required"),
                checker=checker,
                registry=PlagiarismRegistry(path),
            )
            second = reloaded_gate.verify(("Conteúdo acadêmico confidencial.",))
            stored = path.read_text(encoding="utf-8")

        self.assertTrue(first.is_acceptable)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(1, len(checker.texts))
        self.assertNotIn("Conteúdo acadêmico confidencial", stored)
        self.assertNotIn(content_fingerprint("Conteúdo acadêmico confidencial."), stored)

    def test_registry_serialization_contains_only_metrics_and_opaque_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "registry.json"
            registry = PlagiarismRegistry(path)
            registry.add(
                "content-hash-not-the-text",
                PlagiarismResult("provider", 8.0, 1),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        entry = next(iter(payload["checks"].values()))
        self.assertEqual(
            {"provider", "similarity_percent", "source_count"},
            set(entry),
        )

    def test_provider_client_submits_polls_and_deletes_scan(self) -> None:
        transport = RecordingTransport(
            [
                {"success": True, "data": {"text": {"id": 15}}},
                {"data": {"id": 15, "state": 2, "report": None}},
                {
                    "data": {
                        "id": 15,
                        "state": 3,
                        "report": {"percent": "18.75", "source_count": 4},
                    }
                },
                {"success": True},
            ]
        )
        client = PlagiarismCheckOrgClient(
            "secret-token",
            timeout_seconds=1,
            poll_interval_seconds=0,
            transport=transport,
            sleeper=lambda _: None,
        )

        result = client.check("Texto técnico para análise.")

        self.assertEqual(18.75, result.similarity_percent)
        self.assertEqual(4, result.source_count)
        self.assertEqual(["POST", "GET", "GET", "DELETE"], [
            call["method"] for call in transport.calls
        ])
        submitted = urllib.parse.parse_qs(
            transport.calls[0]["data"].decode("utf-8")
        )
        self.assertEqual(["Texto técnico para análise."], submitted["text"])
        self.assertEqual(
            "secret-token",
            transport.calls[0]["headers"]["X-API-TOKEN"],
        )
        self.assertTrue(transport.calls[-1]["url"].endswith("/api/v1/text/15"))

    def test_disabled_gate_never_calls_checker(self) -> None:
        gate = PlagiarismGate(PlagiarismPolicy(mode="disabled"))

        decision = gate.verify(("Texto não enviado.",))

        self.assertTrue(decision.skipped)
        self.assertTrue(decision.is_acceptable)

    def test_required_environment_without_token_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {"STAGEFLOW_PLAGIARISM_MODE": "required"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                PlagiarismConfigurationError,
                "TOKEN",
            ):
                PlagiarismGate.from_environment("unused.json")


if __name__ == "__main__":
    unittest.main()
