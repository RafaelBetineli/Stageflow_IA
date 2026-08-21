import tempfile
import unittest
from pathlib import Path

from docx import Document

from document_generator import DocumentGenerator
from pipeline_whatsapp_docx import run_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_TEXT = (PROJECT_ROOT / "data" / "mensagem_zap.example.txt").read_text(
    encoding="utf-8"
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

    def test_existing_document_is_preserved_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "entrada.txt"
            output_dir = root / "docx"
            input_path.write_text(EXAMPLE_TEXT, encoding="utf-8")
            output_dir.mkdir()
            existing = output_dir / "relatorio_aluno_exemplo.docx"
            existing.write_bytes(b"documento anterior")

            with self.assertRaisesRegex(FileExistsError, "--overwrite"):
                run_pipeline(input_path, output_dir, quantidade=3)

            self.assertEqual(b"documento anterior", existing.read_bytes())
            self.assertFalse((root / "originality_registry.json").exists())
            self.assertEqual([existing], list(output_dir.iterdir()))

    def test_overwrite_replaces_existing_documents_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "entrada.txt"
            output_dir = root / "docx"
            input_path.write_text(EXAMPLE_TEXT, encoding="utf-8")
            output_dir.mkdir()
            expected = tuple(
                output_dir / f"{prefixo}_aluno_exemplo.docx"
                for prefixo in ("relatorio", "plano_estagio", "termo_compromisso")
            )
            for path in expected:
                path.write_bytes(b"documento anterior")

            outputs = run_pipeline(
                input_path,
                output_dir,
                quantidade=3,
                overwrite=True,
            )

            self.assertEqual(expected, outputs)
            for output in outputs:
                self.assertNotEqual(b"documento anterior", output.read_bytes())
                Document(output)


if __name__ == "__main__":
    unittest.main()
