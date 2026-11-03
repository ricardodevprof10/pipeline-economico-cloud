
import json
import os
import sys
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import psycopg


SCHEMA = "projeto_integrador"

BASE = Path("projeto_final/dados")
RESULTADOS = Path("projeto_final/resultados")

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


def validar_ambiente():
    if os.getenv("AMBIENTE") != "staging":
        raise RuntimeError(
            "Execucao permitida apenas em staging."
        )

    url = os.getenv("DATABASE_URL", "")

    esperado = os.getenv(
        "NEON_STAGING_HOST", ""
    ).strip().lower()

    if not url or not esperado:
        raise RuntimeError(
            "Credenciais de staging ausentes."
        )

    parsed = urlparse(url)

    host = (parsed.hostname or "").lower()

    if parsed.scheme not in (
        "postgresql",
        "postgres",
    ):
        raise RuntimeError(
            "Formato de conexao invalido."
        )

    if (
        host != esperado
        or not host.endswith(".neon.tech")
    ):
        raise RuntimeError(
            "Host diferente do staging esperado."
        )

    return url


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


def gerar_bronze():
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

    df["origem"] = "dados_sinteticos"

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
    )

    return df


def gerar_silver(bronze):
    df = bronze.copy()

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
    )

    return df


def gerar_gold(silver):
    df = (
        silver.groupby(
            "ano",
            as_index=False,
        )["pib_usd_bilhoes"]
        .sum()
    )

    df = df.rename(
        columns={
            "pib_usd_bilhoes":
            "pib_total_usd_bilhoes"
        }
    )

    destino = GOLD / "pib_por_ano.parquet"

    df.to_parquet(
        destino,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )

    registrar(
        "gold_concluida",
        registros=len(df),
    )

    return df


def validar_dados(bronze, silver, gold):
    if len(bronze) != 11:
        raise AssertionError(
            "Quantidade Bronze incorreta."
        )

    if len(silver) != 8:
        raise AssertionError(
            "Quantidade Silver incorreta."
        )

    if len(gold) != 2:
        raise AssertionError(
            "Quantidade Gold incorreta."
        )

    valores = dict(
        zip(
            gold["ano"],
            gold["pib_total_usd_bilhoes"],
        )
    )

    if valores.get(2022) != 2900:
        raise AssertionError(
            "Agregacao de 2022 incorreta."
        )

    if valores.get(2023) != 3160:
        raise AssertionError(
            "Agregacao de 2023 incorreta."
        )

    registrar(
        "qualidade_aprovada",
        bronze=len(bronze),
        silver=len(silver),
        gold=len(gold),
    )


def preparar_banco(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                projeto_integrador
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                projeto_integrador.indicadores (
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd_bilhoes NUMERIC NOT NULL,
                    atualizado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (codigo_pais, ano)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                projeto_integrador.execucoes (
                    execucao_id TEXT PRIMARY KEY,
                    registros_bronze INTEGER NOT NULL,
                    registros_silver INTEGER NOT NULL,
                    registros_gold INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    executado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )


def carregar_postgres(
    conexao,
    silver,
    bronze,
    gold,
    execucao_id,
):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            for linha in silver.itertuples(
                index=False
            ):
                cursor.execute(
                    """
                    INSERT INTO
                    projeto_integrador.indicadores
                    (
                        codigo_pais,
                        ano,
                        pib_usd_bilhoes
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (
                        codigo_pais,
                        ano
                    )
                    DO UPDATE SET
                        pib_usd_bilhoes =
                            EXCLUDED.pib_usd_bilhoes,
                        atualizado_em = NOW()
                    WHERE
                        projeto_integrador.indicadores
                        .pib_usd_bilhoes
                        IS DISTINCT FROM
                        EXCLUDED.pib_usd_bilhoes
                    """,
                    (
                        linha.codigo_pais,
                        int(linha.ano),
                        float(
                            linha.pib_usd_bilhoes
                        ),
                    ),
                )

            cursor.execute(
                """
                INSERT INTO
                projeto_integrador.execucoes
                (
                    execucao_id,
                    registros_bronze,
                    registros_silver,
                    registros_gold,
                    status
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    execucao_id,
                    len(bronze),
                    len(silver),
                    len(gold),
                    "sucesso",
                ),
            )

    registrar(
        "carga_postgresql_concluida",
        registros=len(silver),
    )


def verificar_persistencia(conexao, silver):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT codigo_pais, ano, pib_usd_bilhoes
            FROM projeto_integrador.indicadores
            ORDER BY codigo_pais, ano
            """
        )

        encontrados = cursor.fetchall()

    esperados = {
        (
            linha.codigo_pais,
            int(linha.ano),
        ): float(linha.pib_usd_bilhoes)
        for linha in silver.itertuples(index=False)
    }

    persistidos = {
        (pais, ano): float(pib)
        for pais, ano, pib in encontrados
    }

    for chave, valor in esperados.items():
        if persistidos.get(chave) != valor:
            raise AssertionError(
                f"Persistencia incorreta: {chave}"
            )

    return len(esperados)


def executar():
    inicio = time.perf_counter()
    execucao_id = uuid.uuid4().hex

    registrar(
        "pipeline_iniciado",
        execucao_id=execucao_id,
    )

    url = validar_ambiente()

    preparar_diretorios()

    bronze = gerar_bronze()

    silver = gerar_silver(bronze)

    gold = gerar_gold(silver)

    validar_dados(
        bronze,
        silver,
        gold,
    )

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        preparar_banco(conexao)

        carregar_postgres(
            conexao,
            silver,
            bronze,
            gold,
            execucao_id,
        )

        persistidos = verificar_persistencia(
            conexao,
            silver,
        )

    duracao = round(
        time.perf_counter() - inicio,
        4,
    )

    resultado = {
        "projeto": "pipeline_economico_integrador",
        "ambiente": "staging",
        "execucao_id": execucao_id,
        "camadas": {
            "bronze": len(bronze),
            "silver": len(silver),
            "gold": len(gold),
        },
        "registros_persistidos": persistidos,
        "validacao_aprovada": True,
        "duracao_segundos": duracao,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = (
        RESULTADOS / "relatorio_integrador.json"
    )

    destino.write_text(
        json.dumps(
            resultado,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registrar(
        "pipeline_finalizado",
        **resultado,
    )


if __name__ == "__main__":
    try:
        executar()

    except Exception as erro:
        registrar(
            "pipeline_falhou",
            tipo_erro=type(erro).__name__,
            mensagem=str(erro),
        )
        sys.exit(1)
