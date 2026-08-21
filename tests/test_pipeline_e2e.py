import tempfile
import unittest
from pathlib import Path

from docx import Document

from document_generator import DocumentGenerator
from pipeline_whatsapp_docx import run_pipeline
from plagiarism_gate import (
    PlagiarismGate,
    PlagiarismPolicy,
    PlagiarismProviderError,
    PlagiarismRejected,
    PlagiarismRegistry,
    PlagiarismResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_TEXT = (PROJECT_ROOT / "data" / "mensagem_zap.example.txt").read_text(
    encoding="utf-8"
)


class SequenceChecker:
    provider = "fake-provider"

    def __init__(self, scores: list[float] | None = None, *, error=None) -> None:
        self.scores = scores or []
        self.error = error
        self.texts: list[str] = []

    def check(self, text: str) -> PlagiarismResult:
        self.texts.append(text)
        if self.error is not None:
            raise self.error
        return PlagiarismResult(
            self.provider,
            self.scores.pop(0),
            source_count=2,
        )


def required_gate(checker: SequenceChecker) -> PlagiarismGate:
    return PlagiarismGate(
        PlagiarismPolicy(mode="required", maximum_similarity_percent=25.0),
        checker=checker,
        registry=PlagiarismRegistry(),
    )


class PipelineEndToEndTests(unittest.TestCase):
    def test_generates_three_complete_documents_for_every_area(self) -> None:
        for area in (
            "Estética",
            "Drogaria",
            "Hospitalar",
            "Manipulação",
            "Controle de qualidade",
        ):
            with self.subTest(area=area), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                input_path = root / "entrada.txt"
                input_path.write_text(
                    EXAMPLE_TEXT.replace("Área estágio: Drogaria", f"Área estágio: {area}"),
                    encoding="utf-8",
                )

                outputs = run_pipeline(input_path, root / "docx", quantidade=3)

                self.assertEqual(3, len(outputs))
                for output in outputs:
                    self.assertTrue(output.is_file())
                    document = Document(output)
                    self.assertFalse(DocumentGenerator._collect_placeholders(document))
                    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
                    self.assertNotIn("Texto temporário", text)

    def test_external_rejection_uses_one_variant_then_publishes(self) -> None:
        checker = SequenceChecker([80.0, 12.0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "entrada.txt"
            input_path.write_text(EXAMPLE_TEXT, encoding="utf-8")

            outputs = run_pipeline(
                input_path,
                root / "docx",
                quantidade=3,
                plagiarism_gate=required_gate(checker),
            )

        self.assertEqual(2, len(checker.texts))
        self.assertEqual(3, len(outputs))
        self.assertNotEqual(checker.texts[0], checker.texts[1])
        for private_value in (
            "Aluno Exemplo",
            "Empresa Exemplo",
            "000.000.000-00",
            "aluno@example.invalid",
        ):
            self.assertNotIn(private_value, checker.texts[0])
            self.assertNotIn(private_value, checker.texts[1])

    def test_two_external_rejections_publish_no_document(self) -> None:
        checker = SequenceChecker([80.0, 70.0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "entrada.txt"
            output = root / "docx"
            input_path.write_text(EXAMPLE_TEXT, encoding="utf-8")

            with self.assertRaises(PlagiarismRejected):
                run_pipeline(
                    input_path,
                    output,
                    quantidade=3,
                    plagiarism_gate=required_gate(checker),
                )

            self.assertEqual([], list(output.glob("*.docx")))
        self.assertEqual(2, len(checker.texts))

    def test_required_provider_failure_publishes_no_document(self) -> None:
        checker = SequenceChecker(
            error=PlagiarismProviderError("indisponível")
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "entrada.txt"
            output = root / "docx"
            input_path.write_text(EXAMPLE_TEXT, encoding="utf-8")

            with self.assertRaises(PlagiarismProviderError):
                run_pipeline(
                    input_path,
                    output,
                    quantidade=3,
                    plagiarism_gate=required_gate(checker),
                )

            self.assertEqual([], list(output.glob("*.docx")))


if __name__ == "__main__":
    unittest.main()
