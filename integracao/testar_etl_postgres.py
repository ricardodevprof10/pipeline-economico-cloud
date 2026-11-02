
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import errors


SCHEMA = "homologacao_aula52"
TABELA = "indicadores_integracao"

DADOS_TESTE = [
    ("BRA", 2023, 2000),
    ("ARG", 2023, 650),
    ("CHL", 2023, 330),
]


def validar_ambiente():
    ambiente = os.getenv("AMBIENTE", "")
    url = os.getenv("DATABASE_URL", "")
    host_esperado = os.getenv(
        "NEON_STAGING_HOST", ""
    ).strip().lower()

    if ambiente != "staging":
        raise RuntimeError(
            "Execucao permitida apenas em staging."
        )

    if not url or not host_esperado:
        raise RuntimeError(
            "Credenciais de staging ausentes."
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

    if (
        host_atual != host_esperado
        or not host_atual.endswith(".neon.tech")
    ):
        raise RuntimeError(
            "Host diferente do staging esperado."
        )

    return url


def validar_dados(dados):
    if not dados:
        raise ValueError(
            "Lista de dados vazia."
        )

    chaves = set()

    for codigo, ano, pib in dados:
        if not codigo or not isinstance(
            codigo, str
        ):
            raise ValueError(
                "Codigo do pais invalido."
            )

        if (
            not isinstance(ano, int)
            or isinstance(ano, bool)
            or ano < 1960
        ):
            raise ValueError(
                "Ano invalido."
            )

        if (
            not isinstance(pib, (int, float))
            or isinstance(pib, bool)
            or pib < 0
        ):
            raise ValueError(
                "PIB invalido."
            )

        chave = (codigo, ano)

        if chave in chaves:
            raise ValueError(
                "Duplicidade detectada na origem."
            )

        chaves.add(chave)

    return True


def criar_tabela(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula52
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula52.indicadores_integracao (
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL
                        CHECK (pib_usd >= 0),
                    PRIMARY KEY (codigo_pais, ano)
                )
                """
            )


def testar_carga(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                homologacao_aula52.indicadores_integracao
                WHERE ano = %s
                  AND codigo_pais IN (%s, %s, %s)
                """,
                (2023, "BRA", "ARG", "CHL"),
            )

            cursor.executemany(
                """
                INSERT INTO
                homologacao_aula52.indicadores_integracao
                (codigo_pais, ano, pib_usd)
                VALUES (%s, %s, %s)
                """,
                DADOS_TESTE,
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM
                homologacao_aula52.indicadores_integracao
                WHERE ano = %s
                  AND codigo_pais IN (%s, %s, %s)
                """,
                (2023, "BRA", "ARG", "CHL"),
            )

            total = cursor.fetchone()[0]

            if total != len(DADOS_TESTE):
                raise AssertionError(
                    "Quantidade incorreta."
                )

    return total


def testar_rollback(conexao):
    codigo = "ROLLBACK_TESTE"
    ano = 2023

    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                homologacao_aula52.indicadores_integracao
                WHERE codigo_pais = %s
                  AND ano = %s
                """,
                (codigo, ano),
            )

    try:
        with conexao.transaction():
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO
                    homologacao_aula52.indicadores_integracao
                    (codigo_pais, ano, pib_usd)
                    VALUES (%s, %s, %s)
                    """,
                    (codigo, ano, 100),
                )

                cursor.execute(
                    """
                    INSERT INTO
                    homologacao_aula52.indicadores_integracao
                    (codigo_pais, ano, pib_usd)
                    VALUES (%s, %s, %s)
                    """,
                    (codigo, ano, 200),
                )

    except errors.UniqueViolation:
        pass

    else:
        raise AssertionError(
            "A duplicidade deveria causar erro."
        )

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM
            homologacao_aula52.indicadores_integracao
            WHERE codigo_pais = %s
              AND ano = %s
            """,
            (codigo, ano),
        )

        total = cursor.fetchone()[0]

    if total != 0:
        raise AssertionError(
            "Rollback nao removeu os dados."
        )

    return True


def executar():
    validar_dados(DADOS_TESTE)

    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        criar_tabela(conexao)

        total = testar_carga(conexao)

        rollback_ok = testar_rollback(
            conexao
        )

    resultado = {
        "ambiente": "staging",
        "teste": "integracao_etl_postgres",
        "registros_validados": total,
        "rollback_aprovado": rollback_ok,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "integracao/resultados/"
        "relatorio_integracao.json"
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
