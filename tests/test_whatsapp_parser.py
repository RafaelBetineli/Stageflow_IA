import unittest

from whatsapp_parser import WhatsAppParser


class WhatsAppParserTests(unittest.TestCase):
    def test_maps_extended_fields_and_multiline_values(self) -> None:
        text = """Nome aluno: Aluno Exemplo
Ramo empresa: Serviços farmacêuticos
História da empresa: Primeira linha.
  Segunda linha.
Campo desconhecido: ignorado
  Esta linha também deve ser ignorada.
"""

        result = WhatsAppParser().parse(text)

        self.assertEqual("Aluno Exemplo", result["NOME_ALUNO"])
        self.assertEqual("Serviços farmacêuticos", result["RAMO_EMPRESA"])
        self.assertEqual(
            "Primeira linha.\nSegunda linha.",
            result["HISTORIA_EMPRESA_INFORMADA"],
        )
        self.assertNotIn("Campo desconhecido", result)


if __name__ == "__main__":
    unittest.main()
