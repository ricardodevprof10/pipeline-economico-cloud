
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula56"
CONSUMIDOR = "consumidor_lotes_v1"
TAMANHO_LOTE = 100


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
                SELECT to_regclass(
                    'homologacao_aula54.eventos_cdc'
                )
                """
            )

            if cursor.fetchone()[0] is None:
                raise RuntimeError(
                    "Tabela CDC da aula 54 nao encontrada."
                )

            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS
                homologacao_aula56
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula56.indicadores_projetados (
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
                homologacao_aula56.checkpoints (
                    consumidor TEXT PRIMARY KEY,
                    ultimo_evento_id BIGINT NOT NULL
                        DEFAULT 0,
                    atualizado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO homologacao_aula56.checkpoints
                (consumidor, ultimo_evento_id)
                VALUES (%s, 0)
                ON CONFLICT (consumidor) DO NOTHING
                """,
                (CONSUMIDOR,),
            )


def obter_checkpoint(cursor):
    cursor.execute(
        """
        SELECT ultimo_evento_id
        FROM homologacao_aula56.checkpoints
        WHERE consumidor = %s
        FOR UPDATE
        """,
        (CONSUMIDOR,),
    )

    resultado = cursor.fetchone()

    if resultado is None:
        raise RuntimeError(
            "Checkpoint nao encontrado."
        )

    return resultado[0]


def aplicar_evento(cursor, evento):
    (
        evento_id,
        operacao,
        codigo,
        ano,
        valor_novo,
    ) = evento

    if operacao in ("INSERT", "UPDATE"):
        if valor_novo is None:
            raise ValueError(
                f"Evento {evento_id} sem valor novo."
            )

        cursor.execute(
            """
            INSERT INTO
            homologacao_aula56.indicadores_projetados
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
            homologacao_aula56.indicadores_projetados
            WHERE codigo_pais = %s
              AND ano = %s
            """,
            (codigo, ano),
        )

    else:
        raise ValueError(
            f"Operacao desconhecida: {operacao}"
        )


def processar_lote(conexao, simular_falha=False):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            checkpoint = obter_checkpoint(cursor)

            cursor.execute(
                """
                SELECT
                    id,
                    operacao,
                    codigo_pais,
                    ano,
                    valor_novo
                FROM homologacao_aula54.eventos_cdc
                WHERE id > %s
                ORDER BY id
                LIMIT %s
                """,
                (checkpoint, TAMANHO_LOTE),
            )

            eventos = cursor.fetchall()

            if not eventos:
                return {
                    "processados": 0,
                    "checkpoint": checkpoint,
                }

            for indice, evento in enumerate(
                eventos, start=1
            ):
                aplicar_evento(cursor, evento)

                if simular_falha and indice == 1:
                    raise RuntimeError(
                        "Falha simulada para testar rollback."
                    )

            ultimo_id = eventos[-1][0]

            cursor.execute(
                """
                UPDATE homologacao_aula56.checkpoints
                SET ultimo_evento_id = %s,
                    atualizado_em = NOW()
                WHERE consumidor = %s
                """,
                (ultimo_id, CONSUMIDOR),
            )

            return {
                "processados": len(eventos),
                "checkpoint": ultimo_id,
            }


def contar_pendentes(conexao, checkpoint):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula54.eventos_cdc
            WHERE id > %s
            """,
            (checkpoint,),
        )

        return cursor.fetchone()[0]


def ler_checkpoint(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT ultimo_evento_id
            FROM homologacao_aula56.checkpoints
            WHERE consumidor = %s
            """,
            (CONSUMIDOR,),
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

        checkpoint_inicial = ler_checkpoint(
            conexao
        )

        pendentes_iniciais = contar_pendentes(
            conexao,
            checkpoint_inicial,
        )

        rollback_aprovado = None

        if pendentes_iniciais > 0:
            try:
                processar_lote(
                    conexao,
                    simular_falha=True,
                )

            except RuntimeError as erro:
                if str(erro) != (
                    "Falha simulada para testar rollback."
                ):
                    raise

                checkpoint_apos_falha = (
                    ler_checkpoint(conexao)
                )

                rollback_aprovado = (
                    checkpoint_apos_falha
                    == checkpoint_inicial
                )

                if not rollback_aprovado:
                    raise AssertionError(
                        "Checkpoint alterado apos falha."
                    )

            else:
                raise AssertionError(
                    "A falha simulada nao ocorreu."
                )

        lotes = []
        total_processados = 0

        while True:
            resultado = processar_lote(conexao)

            if resultado["processados"] == 0:
                break

            lotes.append(resultado)
            total_processados += resultado[
                "processados"
            ]

        checkpoint_final = ler_checkpoint(
            conexao
        )

        pendentes_finais = contar_pendentes(
            conexao,
            checkpoint_final,
        )

    if pendentes_finais != 0:
        raise AssertionError(
            "Existem eventos pendentes."
        )

    resultado = {
        "ambiente": "staging",
        "consumidor": CONSUMIDOR,
        "tamanho_lote": TAMANHO_LOTE,
        "checkpoint_inicial": checkpoint_inicial,
        "checkpoint_final": checkpoint_final,
        "pendentes_iniciais": pendentes_iniciais,
        "eventos_processados": total_processados,
        "lotes_processados": len(lotes),
        "rollback_aprovado": rollback_aprovado,
        "pendentes_finais": pendentes_finais,
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "checkpoints/resultados/"
        "relatorio_lotes.json"
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
