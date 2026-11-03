
import json
import os
import sys
import time

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula59"
TOTAL_REGISTROS = 50000

CONSULTA = """
SELECT codigo_pais, ano, pib_usd
FROM homologacao_aula59.indicadores_performance
WHERE codigo_pais = 'BRA'
  AND ano = 2023
"""


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
            "Configuracao de staging ausente."
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


def preparar_dados(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula59
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula59.indicadores_performance (
                    id BIGINT PRIMARY KEY,
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO
                homologacao_aula59.indicadores_performance
                (id, codigo_pais, ano, pib_usd)
                SELECT
                    numero,
                    CASE
                        WHEN MOD(numero, 10) = 0
                            THEN 'BRA'
                        WHEN MOD(numero, 10) = 1
                            THEN 'ARG'
                        WHEN MOD(numero, 10) = 2
                            THEN 'CHL'
                        ELSE 'OUT'
                    END,
                    2000 + MOD(numero, 25),
                    1000 + numero
                FROM generate_series(
                    1, %s
                ) AS numero
                ON CONFLICT (id) DO NOTHING
                """,
                (TOTAL_REGISTROS,),
            )

            cursor.execute(
                """
                DROP INDEX IF EXISTS
                homologacao_aula59.idx_pais_ano
                """
            )

            cursor.execute(
                """
                ANALYZE
                homologacao_aula59.indicadores_performance
                """
            )


def medir_consulta(conexao):
    with conexao.cursor() as cursor:
        inicio = time.perf_counter()

        cursor.execute(CONSULTA)
        linhas = cursor.fetchall()

        duracao = (
            time.perf_counter() - inicio
        ) * 1000

        cursor.execute(
            """
            EXPLAIN (
                ANALYZE,
                BUFFERS,
                FORMAT JSON
            )
            """
            + CONSULTA
        )

        plano = cursor.fetchone()[0][0]

    return {
        "tempo_ms": round(duracao, 4),
        "linhas_encontradas": len(linhas),
        "plano": plano,
    }


def criar_indice(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE INDEX idx_pais_ano
                ON homologacao_aula59.indicadores_performance
                (codigo_pais, ano)
                """
            )

            cursor.execute(
                """
                ANALYZE
                homologacao_aula59.indicadores_performance
                """
            )


def tipos_de_nos(plano):
    tipos = []

    def visitar(no):
        tipos.append(
            no.get("Node Type")
        )

        for filho in no.get("Plans", []):
            visitar(filho)

    visitar(plano["Plan"])

    return tipos


def executar():
    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        preparar_dados(conexao)

        sem_indice = medir_consulta(conexao)

        criar_indice(conexao)

        com_indice = medir_consulta(conexao)

    if (
        sem_indice["linhas_encontradas"]
        != com_indice["linhas_encontradas"]
    ):
        raise AssertionError(
            "Consultas retornaram quantidades diferentes."
        )

    tipos_antes = tipos_de_nos(
        sem_indice["plano"]
    )

    tipos_depois = tipos_de_nos(
        com_indice["plano"]
    )

    tempo_antes = sem_indice["tempo_ms"]
    tempo_depois = com_indice["tempo_ms"]

    ganho_percentual = (
        round(
            (
                1 - tempo_depois / tempo_antes
            ) * 100,
            2,
        )
        if tempo_antes > 0
        else None
    )

    resultado = {
        "ambiente": "staging",
        "registros_sinteticos": TOTAL_REGISTROS,
        "sem_indice": {
            "tempo_ms": tempo_antes,
            "linhas": sem_indice[
                "linhas_encontradas"
            ],
            "operadores": tipos_antes,
            "tempo_plano_ms": sem_indice[
                "plano"
            ]["Execution Time"],
        },
        "com_indice": {
            "tempo_ms": tempo_depois,
            "linhas": com_indice[
                "linhas_encontradas"
            ],
            "operadores": tipos_depois,
            "tempo_plano_ms": com_indice[
                "plano"
            ]["Execution Time"],
        },
        "ganho_percentual": ganho_percentual,
        "resultado_consistente": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "performance/resultados/"
        "relatorio_performance.json"
    )

    destino.parent.mkdir(
        parents=True,
        exist_ok=True,
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


if __name__ == "__main__":
    try:
        executar()

    except Exception as erro:
        print(
            f"Falha: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        sys.exit(1)
