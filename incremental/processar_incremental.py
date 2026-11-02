
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula53"
TABELA = "indicadores_incrementais"

DADOS_INICIAIS = [
    ("BRA", 2023, Decimal("2000")),
    ("ARG", 2023, Decimal("650")),
    ("CHL", 2023, Decimal("330")),
]

DADOS_ATUALIZADOS = [
    ("BRA", 2023, Decimal("2100")),
    ("ARG", 2023, Decimal("650")),
    ("CHL", 2023, Decimal("330")),
    ("URY", 2023, Decimal("80")),
]


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


def validar_registros(registros):
    if not registros:
        raise ValueError(
            "Nenhum registro recebido."
        )

    chaves = set()

    for codigo, ano, pib in registros:
        if (
            not isinstance(codigo, str)
            or not codigo.strip()
        ):
            raise ValueError(
                "Codigo de pais invalido."
            )

        if (
            type(ano) is not int
            or ano < 1960
        ):
            raise ValueError(
                "Ano invalido."
            )

        if (
            not isinstance(pib, Decimal)
            or not pib.is_finite()
            or pib < 0
        ):
            raise ValueError(
                "PIB invalido."
            )

        chave = (codigo, ano)

        if chave in chaves:
            raise ValueError(
                "Duplicidade na origem."
            )

        chaves.add(chave)


def criar_estrutura(conexao):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula53
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula53.indicadores_incrementais (
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL
                        CHECK (pib_usd >= 0),
                    atualizado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (codigo_pais, ano)
                )
                """
            )


def carregar_incremental(conexao, registros):
    validar_registros(registros)

    metricas = {
        "inseridos": 0,
        "atualizados": 0,
        "inalterados": 0,
    }

    with conexao.transaction():
        with conexao.cursor() as cursor:
            for codigo, ano, pib in registros:
                cursor.execute(
                    """
                    SELECT pib_usd
                    FROM homologacao_aula53.indicadores_incrementais
                    WHERE codigo_pais = %s
                      AND ano = %s
                    FOR UPDATE
                    """,
                    (codigo, ano),
                )

                anterior = cursor.fetchone()

                if anterior is None:
                    cursor.execute(
                        """
                        INSERT INTO
                        homologacao_aula53.indicadores_incrementais
                        (codigo_pais, ano, pib_usd)
                        VALUES (%s, %s, %s)
                        """,
                        (codigo, ano, pib),
                    )

                    metricas["inseridos"] += 1

                elif anterior[0] != pib:
                    cursor.execute(
                        """
                        UPDATE
                        homologacao_aula53.indicadores_incrementais
                        SET pib_usd = %s,
                            atualizado_em = NOW()
                        WHERE codigo_pais = %s
                          AND ano = %s
                        """,
                        (pib, codigo, ano),
                    )

                    metricas["atualizados"] += 1

                else:
                    metricas["inalterados"] += 1

    return metricas


def contar_registros(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula53.indicadores_incrementais
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

        primeira = carregar_incremental(
            conexao,
            DADOS_INICIAIS,
        )

        segunda = carregar_incremental(
            conexao,
            DADOS_ATUALIZADOS,
        )

        terceira = carregar_incremental(
            conexao,
            DADOS_ATUALIZADOS,
        )

        total = contar_registros(conexao)

    if segunda["atualizados"] != 1:
        raise AssertionError(
            "Atualizacao incremental incorreta."
        )

    if terceira != {
        "inseridos": 0,
        "atualizados": 0,
        "inalterados": 4,
    }:
        raise AssertionError(
            "Falha no teste de idempotencia."
        )

    if total != 4:
        raise AssertionError(
            "Quantidade final incorreta."
        )

    resultado = {
        "ambiente": "staging",
        "pipeline": "carga_incremental",
        "primeira_carga": primeira,
        "segunda_carga": segunda,
        "reprocessamento": terceira,
        "total_registros": total,
        "idempotencia_aprovada": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "incremental/resultados/"
        "relatorio_incremental.json"
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
