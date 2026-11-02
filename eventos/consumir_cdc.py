
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula55"
CONSUMIDOR = "consumidor_indicadores_v1"


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


def criar_estrutura(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula55
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula55.indicadores_projetados (
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL,
                    PRIMARY KEY (codigo_pais, ano)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula55.eventos_processados (
                    consumidor TEXT NOT NULL,
                    evento_id BIGINT NOT NULL,
                    processado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (consumidor, evento_id)
                )
                """
            )

            cursor.execute(
                """
                SELECT to_regclass(
                    'homologacao_aula54.eventos_cdc'
                )
                """
            )

            if cursor.fetchone()[0] is None:
                raise RuntimeError(
                    "Tabela CDC da aula 54 nao encontrada."
                )


def consumir_eventos(conexao):
    metricas = {
        "eventos_lidos": 0,
        "eventos_processados": 0,
        "eventos_ignorados": 0,
    }

    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (55, 1),
            )

            cursor.execute(
                """
                SELECT
                    id,
                    operacao,
                    codigo_pais,
                    ano,
                    valor_novo
                FROM homologacao_aula54.eventos_cdc
                ORDER BY id
                """
            )

            eventos = cursor.fetchall()
            metricas["eventos_lidos"] = len(eventos)

            for (
                evento_id,
                operacao,
                codigo,
                ano,
                valor_novo,
            ) in eventos:

                cursor.execute(
                    """
                    INSERT INTO
                    homologacao_aula55.eventos_processados
                    (consumidor, evento_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING evento_id
                    """,
                    (CONSUMIDOR, evento_id),
                )

                reservado = cursor.fetchone()

                if reservado is None:
                    metricas["eventos_ignorados"] += 1
                    continue

                if operacao in ("INSERT", "UPDATE"):
                    if valor_novo is None:
                        raise ValueError(
                            "Evento sem valor novo."
                        )

                    cursor.execute(
                        """
                        INSERT INTO
                        homologacao_aula55.indicadores_projetados
                        (codigo_pais, ano, pib_usd)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (codigo_pais, ano)
                        DO UPDATE SET
                            pib_usd = EXCLUDED.pib_usd
                        """,
                        (codigo, ano, valor_novo),
                    )

                elif operacao == "DELETE":
                    cursor.execute(
                        """
                        DELETE FROM
                        homologacao_aula55.indicadores_projetados
                        WHERE codigo_pais = %s
                          AND ano = %s
                        """,
                        (codigo, ano),
                    )

                else:
                    raise ValueError(
                        f"Operacao desconhecida: {operacao}"
                    )

                metricas["eventos_processados"] += 1

    return metricas


def contar_projecao(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula55.indicadores_projetados
            """
        )

        return cursor.fetchone()[0]


def executar():
    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        criar_estrutura(conexao)

        primeira = consumir_eventos(conexao)
        segunda = consumir_eventos(conexao)

        total = contar_projecao(conexao)

    if segunda["eventos_processados"] != 0:
        raise AssertionError(
            "Falha no teste de idempotencia."
        )

    resultado = {
        "ambiente": "staging",
        "consumidor": CONSUMIDOR,
        "primeira_execucao": primeira,
        "segunda_execucao": segunda,
        "registros_na_projecao": total,
        "idempotencia_aprovada": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "eventos/resultados/"
        "relatorio_consumidor.json"
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
