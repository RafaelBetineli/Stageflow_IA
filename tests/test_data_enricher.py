import unittest

from data_enricher import DataEnricher


class DataEnricherTests(unittest.TestCase):
    def test_derives_dates_and_distributes_workload(self) -> None:
        result = DataEnricher().enrich(
            {
                "DATA_INICIO_ESTAGIO": "01/02/2026",
                "DATA_FIM_ESTAGIO": "03/02/2026",
                "CARGA_HORARIA": "100 horas",
            },
            activity_count=3,
        )

        self.assertEqual("3", result["QTD_DIAS"])
        self.assertEqual("1 de fevereiro de 2026", result["DATA_INICIO_EXTENSO"])
        self.assertEqual(["34 horas", "33 horas", "33 horas"], [
            result["CARGA_ATV1"], result["CARGA_ATV2"], result["CARGA_ATV3"]
        ])
        self.assertEqual("", result["CARGA_ATV4"])


if __name__ == "__main__":
    unittest.main()
