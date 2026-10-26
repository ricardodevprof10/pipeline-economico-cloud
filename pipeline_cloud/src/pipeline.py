
from pathlib import Path
from datetime import datetime, timezone
import json
import logging
import time

import pandas as pd
import requests


BASE = Path(__file__).resolve().parents[1]
DADOS = BASE / "dados"

for pasta in ["bronze", "silver", "gold", "logs"]:
    (DADOS / pasta).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("pipeline_cloud")

URL = (
    "https://api.worldbank.org/v2/country/BRA/"
    "indicator/NY.GDP.MKTP.CD"
)

PARAMETROS = {
    "format": "json",
    "date": "2020:2024",
    "per_page": 100
}


def extrair():
    for tentativa in range(3):
        try:
            resposta = requests.get(
                URL,
                params=PARAMETROS,
                timeout=30
            )
            resposta.raise_for_status()
            conteudo = resposta.json()

            if (
                not isinstance(conteudo, list)
                or len(conteudo) < 2
                or not isinstance(conteudo[1], list)
            ):
                raise ValueError("JSON inesperado.")

            return conteudo

        except requests.exceptions.RequestException as erro:
            status = (
                erro.response.status_code
                if erro.response is not None
                else None
            )

            if status is not None and (
                400 <= status < 500 and status != 429
            ):
                raise

            if tentativa == 2:
                raise

            espera = 2 ** tentativa
            logger.warning(
                "Falha de rede. Nova tentativa em %ss.",
                espera
            )
            time.sleep(espera)


def transformar(registros):
    linhas = []

    for item in registros:
        linhas.append({
            "pais": (item.get("country") or {}).get("value"),
            "ano": item.get("date"),
            "pib_usd": item.get("value")
        })

    df = pd.DataFrame(
        linhas,
        columns=["pais", "ano", "pib_usd"]
    )

    df["ano"] = pd.to_numeric(
        df["ano"], errors="coerce"
    )
    df["pib_usd"] = pd.to_numeric(
        df["pib_usd"], errors="coerce"
    )

    df = df.dropna(
        subset=["pais", "ano", "pib_usd"]
    ).copy()

    df = df[df["pib_usd"] > 0].copy()
    df["ano"] = df["ano"].astype(int)

    df = df.drop_duplicates(
        subset=["pais", "ano"]
    )

    return df.sort_values("ano").reset_index(drop=True)


def gerar_gold(silver):
    gold = silver.copy()
    gold["pib_bilhoes_usd"] = (
        gold["pib_usd"] / 1_000_000_000
    )
    return gold


def executar():
    inicio = time.perf_counter()

    logger.info("Iniciando pipeline.")

    conteudo = extrair()

    with open(
        DADOS / "bronze" / "pib_original.json",
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(
            conteudo,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    silver = transformar(conteudo[1])

    if silver.empty:
        raise ValueError("Nenhum dado válido recebido.")

    gold = gerar_gold(silver)

    silver.to_csv(
        DADOS / "silver" / "pib.csv",
        index=False
    )

    gold.to_csv(
        DADOS / "gold" / "pib.csv",
        index=False
    )

    relatorio = {
        "status": "SUCESSO",
        "registros_bronze": len(conteudo[1]),
        "registros_silver": len(silver),
        "registros_gold": len(gold),
        "duracao_segundos": round(
            time.perf_counter() - inicio, 2
        ),
        "executado_em_utc": datetime.now(
            timezone.utc
        ).isoformat()
    }

    with open(
        DADOS / "logs" / "relatorio.json",
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(relatorio, arquivo, indent=2)

    logger.info("Pipeline concluído.")
    print(json.dumps(relatorio, indent=2))


if __name__ == "__main__":
    executar()
