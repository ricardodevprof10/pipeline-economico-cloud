
import json
import os
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula60"


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


def preparar_estrutura(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula60
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula60.indicadores (
                    id TEXT PRIMARY KEY,
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE OR REPLACE VIEW
                homologacao_aula60.visao_indicadores
                AS
                SELECT
                    codigo_pais,
                    ano,
                    pib_usd
                FROM homologacao_aula60.indicadores
                """
            )


def testar_operacoes(conexao):
    identificador = uuid.uuid4().hex

    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO homologacao_aula60.indicadores
                (id, codigo_pais, ano, pib_usd)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    identificador,
                    "BRA",
                    2023,
                    2100,
                ),
            )

            cursor.execute(
                """
                SELECT codigo_pais, ano, pib_usd
                FROM homologacao_aula60.visao_indicadores
                WHERE codigo_pais = %s
                  AND ano = %s
                """,
                ("BRA", 2023),
            )

            registros = cursor.fetchall()

            if not registros:
                raise AssertionError(
                    "A view nao retornou registros."
                )

            cursor.execute(
                """
                SELECT
                    has_table_privilege(
                        current_user,
                        'homologacao_aula60.indicadores',
                        'SELECT'
                    ),
                    has_table_privilege(
                        current_user,
                        'homologacao_aula60.indicadores',
                        'INSERT'
                    ),
                    has_table_privilege(
                        current_user,
                        'homologacao_aula60.indicadores',
                        'UPDATE'
                    ),
                    has_table_privilege(
                        current_user,
                        'homologacao_aula60.indicadores',
                        'DELETE'
                    )
                """
            )

            privilegios = cursor.fetchone()

    return {
        "leitura_view_aprovada": True,
        "privilegios_usuario_conexao": {
            "select": privilegios[0],
            "insert": privilegios[1],
            "update": privilegios[2],
            "delete": privilegios[3],
        },
    }


def verificar_seguranca_view(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                schemaname,
                viewname,
                definition
            FROM pg_views
            WHERE schemaname = %s
              AND viewname = %s
            """,
            (
                SCHEMA,
                "visao_indicadores",
            ),
        )

        resultado = cursor.fetchone()

    if resultado is None:
        raise AssertionError(
            "View de leitura nao encontrada."
        )

    return {
        "schema": resultado[0],
        "view": resultado[1],
        "criada": True,
    }


def executar():
    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        preparar_estrutura(conexao)

        operacoes = testar_operacoes(conexao)

        view = verificar_seguranca_view(
            conexao
        )

    resultado = {
        "ambiente": "staging",
        "laboratorio": "seguranca_postgresql",
        "operacoes": operacoes,
        "view": view,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "seguranca/resultados/"
        "relatorio_seguranca.json"
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
