
import argparse
import json
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE = Path("orquestracao/dados")
RESULTADOS = Path("orquestracao/resultados")

BRONZE = BASE / "bronze"
SILVER = BASE / "silver"
GOLD = BASE / "gold"


def registrar(evento, **detalhes):
    registro = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "evento": evento,
        **detalhes,
    }

    print(
        json.dumps(
            registro,
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


def preparar_diretorios():
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


def etapa_bronze():
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

    df["origem"] = "laboratorio_orquestracao"

    df["ingerido_em"] = datetime.now(
        timezone.utc
    ).isoformat()

    destino = BRONZE / "indicadores.parquet"

    df.to_parquet(
        destino,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )

    registrar(
        "bronze_concluida",
        registros=len(df),
        arquivo=str(destino),
    )


def etapa_silver():
    origem = BRONZE / "indicadores.parquet"

    if not origem.exists():
        raise FileNotFoundError(
            "Arquivo Bronze nao encontrado."
        )

    df = pd.read_parquet(origem)

    df["codigo_pais"] = (
        df["codigo_pais"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["ano"] = pd.to_numeric(
        df["ano"],
        errors="coerce",
    )

    df["pib_usd_bilhoes"] = pd.to_numeric(
        df["pib_usd_bilhoes"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "codigo_pais",
            "ano",
            "pib_usd_bilhoes",
        ]
    )

    df = df[
        (df["codigo_pais"] != "")
        & (df["ano"] >= 1960)
        & (df["pib_usd_bilhoes"] >= 0)
    ]

    df = df.drop_duplicates(
        subset=["codigo_pais", "ano"],
        keep="last",
    )

    df["ano"] = df["ano"].astype(int)

    destino = SILVER / "indicadores_limpos.parquet"

    df.to_parquet(
        destino,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )

    registrar(
        "silver_concluida",
        registros=len(df),
        arquivo=str(destino),
    )


def etapa_gold():
    origem = SILVER / "indicadores_limpos.parquet"

    if not origem.exists():
        raise FileNotFoundError(
            "Arquivo Silver nao encontrado."
        )

    df = pd.read_parquet(origem)

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

    destino = GOLD / "pib_por_ano.parquet"

    agregado.to_parquet(
        destino,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )

    registrar(
        "gold_concluida",
        registros=len(agregado),
        arquivo=str(destino),
    )


def etapa_validacao():
    arquivos = {
        "bronze": BRONZE / "indicadores.parquet",
        "silver": SILVER / "indicadores_limpos.parquet",
        "gold": GOLD / "pib_por_ano.parquet",
    }

    for nome, caminho in arquivos.items():
        if not caminho.exists():
            raise FileNotFoundError(
                f"Camada ausente: {nome}"
            )

    bronze = pd.read_parquet(arquivos["bronze"])
    silver = pd.read_parquet(arquivos["silver"])
    gold = pd.read_parquet(arquivos["gold"])

    quantidades = {
        "bronze": len(bronze),
        "silver": len(silver),
        "gold": len(gold),
    }

    esperado = {
        "bronze": 11,
        "silver": 8,
        "gold": 2,
    }

    if quantidades != esperado:
        raise AssertionError(
            f"Quantidades inesperadas: {quantidades}"
        )

    valores = dict(
        zip(
            gold["ano"],
            gold["pib_total_usd_bilhoes"],
        )
    )

    if valores.get(2022) != 2900:
        raise AssertionError(
            "Valor Gold incorreto para 2022."
        )

    if valores.get(2023) != 3160:
        raise AssertionError(
            "Valor Gold incorreto para 2023."
        )

    relatorio = {
        "pipeline": "orquestracao_lakehouse",
        "camadas": quantidades,
        "validacao_aprovada": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = (
        RESULTADOS / "relatorio_orquestracao.json"
    )

    destino.write_text(
        json.dumps(
            relatorio,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registrar(
        "validacao_concluida",
        **relatorio,
    )


def executar(etapa):
    preparar_diretorios()

    etapas = {
        "bronze": etapa_bronze,
        "silver": etapa_silver,
        "gold": etapa_gold,
        "validacao": etapa_validacao,
    }

    inicio = time.perf_counter()

    registrar(
        "etapa_iniciada",
        etapa=etapa,
    )

    etapas[etapa]()

    registrar(
        "etapa_finalizada",
        etapa=etapa,
        duracao_segundos=round(
            time.perf_counter() - inicio,
            4,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--etapa",
        choices=[
            "bronze",
            "silver",
            "gold",
            "validacao",
        ],
        required=True,
    )

    argumentos = parser.parse_args()

    try:
        executar(argumentos.etapa)

    except Exception as erro:
        registrar(
            "etapa_falhou",
            etapa=argumentos.etapa,
            tipo_erro=type(erro).__name__,
            mensagem=str(erro),
        )
        sys.exit(1)
