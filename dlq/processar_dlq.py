
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula57"

EVENTOS = [
    (5701, "INSERT", "BRA", 2023, Decimal("2000")),
    (5702, "UPDATE", "BRA", 2023, Decimal("2100")),
    (5703, "INSERT", "ARG", 2023, Decimal("-50")),
    (5704, "DESCONHECIDO", "CHL", 2023, Decimal("330")),
    (5705, "INSERT", "URY", 2023, Decimal("80")),
]


class EventoInvalido(Exception):
    pass


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

    if parsed.scheme not in ("postgresql", "postgres"):
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
                homologacao_aula57
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula57.eventos (
                    id BIGINT PRIMARY KEY,
                    operacao TEXT NOT NULL,
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula57.indicadores (
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC NOT NULL
                        CHECK (pib_usd >= 0),
                    PRIMARY KEY (codigo_pais, ano)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula57.eventos_processados (
                    evento_id BIGINT PRIMARY KEY,
                    processado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula57.dead_letter_queue (
                    evento_id BIGINT PRIMARY KEY,
                    motivo TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'pendente',
                    registrado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.executemany(
                """
                INSERT INTO homologacao_aula57.eventos
                (id, operacao, codigo_pais, ano, pib_usd)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                EVENTOS,
            )


def validar_evento(evento):
    evento_id, operacao, codigo, ano, pib = evento

    if operacao not in ("INSERT", "UPDATE", "DELETE"):
        raise EventoInvalido(
            f"Operacao desconhecida: {operacao}"
        )

    if not codigo or ano < 1960:
        raise EventoInvalido(
            "Pais ou ano invalido."
        )

    if operacao != "DELETE":
        if (
            pib is None
            or not pib.is_finite()
            or pib < 0
        ):
            raise EventoInvalido(
                "Valor de PIB invalido."
            )


def aplicar_evento(cursor, evento):
    evento_id, operacao, codigo, ano, pib = evento

    if operacao in ("INSERT", "UPDATE"):
        cursor.execute(
            """
            INSERT INTO homologacao_aula57.indicadores
            (codigo_pais, ano, pib_usd)
            VALUES (%s, %s, %s)
            ON CONFLICT (codigo_pais, ano)
            DO UPDATE SET
                pib_usd = EXCLUDED.pib_usd
            """,
            (codigo, ano, pib),
        )

    elif operacao == "DELETE":
        cursor.execute(
            """
            DELETE FROM homologacao_aula57.indicadores
            WHERE codigo_pais = %s
              AND ano = %s
            """,
            (codigo, ano),
        )

    cursor.execute(
        """
        INSERT INTO homologacao_aula57.eventos_processados
        (evento_id)
        VALUES (%s)
        """,
        (evento_id,),
    )


def processar_eventos(conexao):
    metricas = {
        "processados": 0,
        "enviados_dlq": 0,
        "ignorados": 0,
    }

    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_advisory_xact_lock(%s, %s)
                """,
                (57, 1),
            )

            cursor.execute(
                """
                SELECT id, operacao, codigo_pais, ano, pib_usd
                FROM homologacao_aula57.eventos
                ORDER BY id
                """
            )

            eventos = cursor.fetchall()

            for evento in eventos:
                evento_id = evento[0]

                cursor.execute(
                    """
                    SELECT 1
                    FROM homologacao_aula57.eventos_processados
                    WHERE evento_id = %s
                    """,
                    (evento_id,),
                )

                if cursor.fetchone() is not None:
                    metricas["ignorados"] += 1
                    continue

                cursor.execute(
                    """
                    SELECT 1
                    FROM homologacao_aula57.dead_letter_queue
                    WHERE evento_id = %s
                    """,
                    (evento_id,),
                )

                if cursor.fetchone() is not None:
                    metricas["ignorados"] += 1
                    continue

                try:
                    validar_evento(evento)

                except EventoInvalido as erro:
                    cursor.execute(
                        """
                        INSERT INTO
                        homologacao_aula57.dead_letter_queue
                        (evento_id, motivo)
                        VALUES (%s, %s)
                        """,
                        (evento_id, str(erro)),
                    )

                    metricas["enviados_dlq"] += 1
                    continue

                aplicar_evento(cursor, evento)
                metricas["processados"] += 1

    return metricas


def consultar_resultados(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT evento_id, motivo, estado
            FROM homologacao_aula57.dead_letter_queue
            ORDER BY evento_id
            """
        )

        dlq = [
            {
                "evento_id": linha[0],
                "motivo": linha[1],
                "estado": linha[2],
            }
            for linha in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT codigo_pais, ano, pib_usd
            FROM homologacao_aula57.indicadores
            ORDER BY codigo_pais
            """
        )

        indicadores = [
            {
                "pais": linha[0],
                "ano": linha[1],
                "pib": str(linha[2]),
            }
            for linha in cursor.fetchall()
        ]

    return dlq, indicadores


def executar():
    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        criar_estrutura(conexao)

        primeira = processar_eventos(conexao)
        segunda = processar_eventos(conexao)

        dlq, indicadores = consultar_resultados(
            conexao
        )

    if segunda["processados"] != 0:
        raise AssertionError(
            "Falha na idempotencia."
        )

    if segunda["enviados_dlq"] != 0:
        raise AssertionError(
            "Eventos duplicados na DLQ."
        )

    ids_dlq = {
        evento["evento_id"] for evento in dlq
    }

    if not {5703, 5704}.issubset(ids_dlq):
        raise AssertionError(
            "Eventos invalidos nao encontrados na DLQ."
        )

    resultado = {
        "ambiente": "staging",
        "laboratorio": "dead_letter_queue",
        "primeira_execucao": primeira,
        "segunda_execucao": segunda,
        "total_dlq": len(dlq),
        "eventos_dlq": dlq,
        "indicadores": indicadores,
        "idempotencia_aprovada": True,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "dlq/resultados/relatorio_dlq.json"
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
