import tempfile
import unittest
from pathlib import Path

from docx import Document

from document_generator import DocumentGenerator, MissingPlaceholderValueError


class DocumentGeneratorTests(unittest.TestCase):
    def test_replaces_body_table_header_footer_and_split_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            paragraph = doc.add_paragraph()
            paragraph.add_run("Aluno: {{NOME_")
            paragraph.add_run("ALUNO}}")
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "RA: {{RA_ALUNO}}"
            doc.sections[0].header.paragraphs[0].text = "{{CABECALHO}}"
            doc.sections[0].footer.paragraphs[0].text = "{{RODAPE}}"
            doc.save(template)

            DocumentGenerator(template).generate(
                {
                    "NOME_ALUNO": "Aluno Exemplo",
                    "RA_ALUNO": "000000",
                    "CABECALHO": "Cabeçalho",
                    "RODAPE": "Rodapé",
                },
                output,
            )

            generated = Document(output)
            self.assertEqual("Aluno: Aluno Exemplo", generated.paragraphs[0].text)
            self.assertEqual("RA: 000000", generated.tables[0].cell(0, 0).text)
            self.assertEqual("Cabeçalho", generated.sections[0].header.paragraphs[0].text)
            self.assertEqual("Rodapé", generated.sections[0].footer.paragraphs[0].text)

    def test_missing_value_does_not_replace_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            doc.add_paragraph("{{OBRIGATORIO}}")
            doc.save(template)
            output.write_bytes(b"conteudo anterior")

            with self.assertRaises(MissingPlaceholderValueError):
                DocumentGenerator(template).generate({}, output)

            self.assertEqual(b"conteudo anterior", output.read_bytes())


if __name__ == "__main__":
    unittest.main()
