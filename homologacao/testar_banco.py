
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula51"
TABELA = "indicadores_teste"


def validar_conexao():
    url = os.getenv("DATABASE_URL", "")
    host_esperado = os.getenv(
        "NEON_STAGING_HOST", ""
    ).strip().lower()

    if not url:
        raise RuntimeError(
            "DATABASE_URL nao configurada."
        )

    if not host_esperado:
        raise RuntimeError(
            "NEON_STAGING_HOST nao configurado."
        )

    parsed = urlparse(url)

    if parsed.scheme not in (
        "postgresql",
        "postgres",
    ):
        raise RuntimeError(
            "Formato da conexao invalido."
        )

    host_atual = (parsed.hostname or "").lower()

    if host_atual != host_esperado:
        raise RuntimeError(
            "Host diferente do staging esperado."
        )

    if not host_atual.endswith(".neon.tech"):
        raise RuntimeError(
            "Host nao identificado como Neon."
        )

    return url


def executar_teste():
    url = validar_conexao()

    with psycopg.connect(
        url,
        connect_timeout=15,
    ) as conexao:

        with conexao.transaction():
            with conexao.cursor() as cursor:
                cursor.execute(
                    "CREATE SCHEMA IF NOT EXISTS "
                    "homologacao_aula51"
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS
                    homologacao_aula51.indicadores_teste (
                        codigo_pais TEXT NOT NULL,
                        ano INTEGER NOT NULL,
                        pib_usd NUMERIC NOT NULL,
                        PRIMARY KEY (codigo_pais, ano)
                    )
                    """
                )

                cursor.execute(
                    """
                    INSERT INTO
                    homologacao_aula51.indicadores_teste
                    (codigo_pais, ano, pib_usd)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (codigo_pais, ano)
                    DO UPDATE SET
                        pib_usd = EXCLUDED.pib_usd
                    """,
                    ("BRA_TESTE", 2023, 2000),
                )

                cursor.execute(
                    """
                    SELECT pib_usd
                    FROM homologacao_aula51.indicadores_teste
                    WHERE codigo_pais = %s
                      AND ano = %s
                    """,
                    ("BRA_TESTE", 2023),
                )

                resultado = cursor.fetchone()

                if (
                    resultado is None
                    or resultado[0] != 2000
                ):
                    raise AssertionError(
                        "Falha na validacao da carga."
                    )

    return {
        "ambiente": "staging",
        "schema": SCHEMA,
        "tabela": TABELA,
        "registros_testados": 1,
        "status": "sucesso",
        "data_execucao": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def main():
    resultado = executar_teste()

    destino = Path(
        "homologacao/resultados/"
        "teste_staging.json"
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
        main()

    except Exception as erro:
        print(
            f"Falha: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        sys.exit(1)
