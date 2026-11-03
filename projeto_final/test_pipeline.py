
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from projeto_final import pipeline_integrador as pipeline


class TestPipelineIntegrador(unittest.TestCase):

    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()

        self.base = Path(self.temporario.name)

        self.bronze = self.base / "bronze"
        self.silver = self.base / "silver"
        self.gold = self.base / "gold"

        self.patches = [
            patch.object(
                pipeline,
                "BRONZE",
                self.bronze,
            ),
            patch.object(
                pipeline,
                "SILVER",
                self.silver,
            ),
            patch.object(
                pipeline,
                "GOLD",
                self.gold,
            ),
        ]

        for modificacao in self.patches:
            modificacao.start()

        self.addCleanup(self.encerrar_patches)
        self.addCleanup(self.temporario.cleanup)

        for diretorio in (
            self.bronze,
            self.silver,
            self.gold,
        ):
            diretorio.mkdir(
                parents=True,
                exist_ok=True,
            )

    def encerrar_patches(self):
        for modificacao in reversed(self.patches):
            modificacao.stop()

    def gerar_camadas(self):
        bronze = pipeline.gerar_bronze()

        silver = pipeline.gerar_silver(bronze)

        gold = pipeline.gerar_gold(silver)

        return bronze, silver, gold

    def test_bronze_preserva_registros(self):
        bronze = pipeline.gerar_bronze()

        self.assertEqual(len(bronze), 11)

        self.assertTrue(
            (
                self.bronze / "indicadores.parquet"
            ).exists()
        )

    def test_silver_remove_invalidos(self):
        bronze = pipeline.gerar_bronze()

        silver = pipeline.gerar_silver(bronze)

        self.assertEqual(len(silver), 8)

        self.assertFalse(
            silver[
                "pib_usd_bilhoes"
            ].isna().any()
        )

        self.assertTrue(
            (
                silver["pib_usd_bilhoes"] >= 0
            ).all()
        )

    def test_silver_remove_duplicados(self):
        bronze = pipeline.gerar_bronze()

        silver = pipeline.gerar_silver(bronze)

        duplicados = silver.duplicated(
            subset=["codigo_pais", "ano"]
        )

        self.assertFalse(duplicados.any())

    def test_gold_agrega_corretamente(self):
        bronze, silver, gold = (
            self.gerar_camadas()
        )

        self.assertEqual(len(gold), 2)

        valores = dict(
            zip(
                gold["ano"],
                gold["pib_total_usd_bilhoes"],
            )
        )

        self.assertEqual(
            valores[2022],
            2900,
        )

        self.assertEqual(
            valores[2023],
            3160,
        )

    def test_validacao_integrada(self):
        bronze, silver, gold = (
            self.gerar_camadas()
        )

        pipeline.validar_dados(
            bronze,
            silver,
            gold,
        )

    def test_validacao_rejeita_gold_incorreta(self):
        bronze, silver, gold = (
            self.gerar_camadas()
        )

        gold_incorreta = gold.copy()

        gold_incorreta.loc[
            gold_incorreta["ano"] == 2023,
            "pib_total_usd_bilhoes",
        ] = 9999

        with self.assertRaises(
            AssertionError
        ):
            pipeline.validar_dados(
                bronze,
                silver,
                gold_incorreta,
            )

    def test_arquivos_parquet_legiveis(self):
        self.gerar_camadas()

        arquivos = [
            self.bronze / "indicadores.parquet",
            self.silver
            / "indicadores_limpos.parquet",
            self.gold / "pib_por_ano.parquet",
        ]

        for arquivo in arquivos:
            self.assertTrue(arquivo.exists())

            dados = pd.read_parquet(arquivo)

            self.assertGreater(len(dados), 0)


if __name__ == "__main__":
    unittest.main()
