import unittest
from pathlib import Path

from input_validator import InputValidationError, InputValidator
from whatsapp_parser import WhatsAppParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "data" / "mensagem_zap.example.txt"


class InputValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = WhatsAppParser().parse(EXAMPLE.read_text(encoding="utf-8"))

    def test_versioned_example_is_valid(self) -> None:
        InputValidator().validate(self.data)

    def test_reports_missing_fields_together(self) -> None:
        self.data["NOME_ALUNO"] = ""
        self.data.pop("CNPJ")

        with self.assertRaises(InputValidationError) as context:
            InputValidator().validate(self.data)

        self.assertIn("Nome aluno", context.exception.issues[0])
        self.assertTrue(any("CNPJ" in issue for issue in context.exception.issues))

    def test_rejects_inverted_internship_dates(self) -> None:
        self.data["DATA_INICIO_ESTAGIO"] = "30/06/2026"
        self.data["DATA_FIM_ESTAGIO"] = "02/02/2026"

        with self.assertRaisesRegex(InputValidationError, "data final do estágio"):
            InputValidator().validate(self.data)


if __name__ == "__main__":
    unittest.main()
