
import json
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


BASE = Path("lakehouse/dados")

BRONZE = BASE / "bronze"
SILVER = BASE / "silver"
GOLD = BASE / "gold"

RESULTADOS = Path("lakehouse/resultados")


def criar_diretorios():
    for diretorio in (
        BRONZE,
        SILVER,
        GOLD,
        RESULTADOS,
    ):
        diretorio.mkdir(
            parents=True,
            exist_ok=True,
        )


def gerar_dados():
    dados = [
        ("BRA", 2022, 1900),
        ("ARG", 2022, 630),
        ("CHL", 2022, 300),
        ("URY", 2022, 70),
        ("BRA", 2023, 2100),
        ("ARG", 2023, 650),
        ("CHL", 2023, 330),
        ("URY", 2023, 80),
        ("BRA", 2023, 2100),
        ("ARG", 2023, None),
        ("", 2023, 500),
    ]

    df = pd.DataFrame(
        dados,
        columns=[
            "codigo_pais",
            "ano",
            "pib_usd_bilhoes",
        ],
    )

    df["origem"] = "laboratorio_sintetico"

    df["ingerido_em"] = datetime.now(
        timezone.utc
    ).isoformat()

    return df


def construir_bronze():
    df = gerar_dados()

    caminho = BRONZE / "indicadores.parquet"

    df.to_parquet(
        caminho,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    return df


def construir_silver(df):
    tratado = df.copy()

    tratado["codigo_pais"] = (
        tratado["codigo_pais"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    tratado["ano"] = pd.to_numeric(
        tratado["ano"],
        errors="coerce",
    )

    tratado["pib_usd_bilhoes"] = (
        pd.to_numeric(
            tratado["pib_usd_bilhoes"],
            errors="coerce",
        )
    )

    tratado = tratado.dropna(
        subset=[
            "codigo_pais",
            "ano",
            "pib_usd_bilhoes",
        ]
    )

    tratado = tratado[
        (tratado["codigo_pais"] != "")
        & (tratado["ano"] >= 1960)
        & (tratado["pib_usd_bilhoes"] >= 0)
    ]

    tratado = tratado.drop_duplicates(
        subset=["codigo_pais", "ano"],
        keep="last",
    )

    tratado["ano"] = tratado["ano"].astype(int)

    caminho = SILVER / "indicadores_limpos.parquet"

    tratado.to_parquet(
        caminho,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    return tratado


def construir_gold(df):
    agregado = (
        df.groupby("ano", as_index=False)
        ["pib_usd_bilhoes"]
        .sum()
    )

    agregado = agregado.rename(
        columns={
            "pib_usd_bilhoes":
            "pib_total_usd_bilhoes"
        }
    )

    caminho = GOLD / "pib_por_ano.parquet"

    agregado.to_parquet(
        caminho,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    return agregado


def validar_camadas(bronze, silver, gold):
    if len(bronze) != 11:
        raise AssertionError(
            "Quantidade inesperada na Bronze."
        )

    if len(silver) != 8:
        raise AssertionError(
            "Quantidade inesperada na Silver."
        )

    if len(gold) != 2:
        raise AssertionError(
            "Quantidade inesperada na Gold."
        )

    valores = dict(
        zip(
            gold["ano"],
            gold["pib_total_usd_bilhoes"],
        )
    )

    if valores[2022] != 2900:
        raise AssertionError(
            "Agregacao incorreta para 2022."
        )

    if valores[2023] != 3160:
        raise AssertionError(
            "Agregacao incorreta para 2023."
        )

    for caminho in (
        BRONZE / "indicadores.parquet",
        SILVER / "indicadores_limpos.parquet",
        GOLD / "pib_por_ano.parquet",
    ):
        if not caminho.exists():
            raise AssertionError(
                f"Arquivo ausente: {caminho}"
            )

        pq.read_metadata(caminho)


def comparar_formatos(df):
    caminho_csv = RESULTADOS / "comparacao.csv"

    caminho_parquet = (
        RESULTADOS / "comparacao.parquet"
    )

    df.to_csv(
        caminho_csv,
        index=False,
    )

    df.to_parquet(
        caminho_parquet,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    return {
        "csv_bytes": caminho_csv.stat().st_size,
        "parquet_bytes": (
            caminho_parquet.stat().st_size
        ),
    }


def executar():
    inicio = time.perf_counter()

    criar_diretorios()

    bronze = construir_bronze()
    silver = construir_silver(bronze)
    gold = construir_gold(silver)

    validar_camadas(
        bronze,
        silver,
        gold,
    )

    formatos = comparar_formatos(silver)

    duracao = round(
        time.perf_counter() - inicio,
        4,
    )

    resultado = {
        "laboratorio": "arquitetura_medallion",
        "camadas": {
            "bronze": len(bronze),
            "silver": len(silver),
            "gold": len(gold),
        },
        "formatos": formatos,
        "duracao_segundos": duracao,
        "validacao_aprovada": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = (
        RESULTADOS / "relatorio_lakehouse.json"
    )

    destino.write_text(
        json.dumps(
            resultado,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            resultado,
            indent=4,
            ensure_ascii=False,
        )
    )

    print("\nCAMADA GOLD")
    print(gold.to_string(index=False))


if __name__ == "__main__":
    try:
        executar()

    except Exception as erro:
        print(
            f"Falha: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        sys.exit(1)
