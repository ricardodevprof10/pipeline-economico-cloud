
import json
import os
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula54"


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
                homologacao_aula54
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula54.indicadores (
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
                homologacao_aula54.eventos_cdc (
                    id BIGINT GENERATED ALWAYS
                        AS IDENTITY PRIMARY KEY,
                    operacao TEXT NOT NULL,
                    codigo_pais TEXT NOT NULL,
                    ano INTEGER NOT NULL,
                    valor_anterior NUMERIC,
                    valor_novo NUMERIC,
                    registrado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION
                homologacao_aula54.registrar_evento()
                RETURNS TRIGGER
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        INSERT INTO
                        homologacao_aula54.eventos_cdc
                        (
                            operacao,
                            codigo_pais,
                            ano,
                            valor_anterior,
                            valor_novo
                        )
                        VALUES (
                            'INSERT',
                            NEW.codigo_pais,
                            NEW.ano,
                            NULL,
                            NEW.pib_usd
                        );

                        RETURN NEW;

                    ELSIF TG_OP = 'UPDATE' THEN
                        INSERT INTO
                        homologacao_aula54.eventos_cdc
                        (
                            operacao,
                            codigo_pais,
                            ano,
                            valor_anterior,
                            valor_novo
                        )
                        VALUES (
                            'UPDATE',
                            NEW.codigo_pais,
                            NEW.ano,
                            OLD.pib_usd,
                            NEW.pib_usd
                        );

                        RETURN NEW;

                    ELSIF TG_OP = 'DELETE' THEN
                        INSERT INTO
                        homologacao_aula54.eventos_cdc
                        (
                            operacao,
                            codigo_pais,
                            ano,
                            valor_anterior,
                            valor_novo
                        )
                        VALUES (
                            'DELETE',
                            OLD.codigo_pais,
                            OLD.ano,
                            OLD.pib_usd,
                            NULL
                        );

                        RETURN OLD;
                    END IF;

                    RETURN NULL;
                END;
                $$
                """
            )

            cursor.execute(
                """
                DROP TRIGGER IF EXISTS
                trigger_registrar_cdc
                ON homologacao_aula54.indicadores
                """
            )

            cursor.execute(
                """
                CREATE TRIGGER trigger_registrar_cdc
                AFTER INSERT OR UPDATE OR DELETE
                ON homologacao_aula54.indicadores
                FOR EACH ROW
                EXECUTE FUNCTION
                homologacao_aula54.registrar_evento()
                """
            )


def executar_teste(conexao):
    codigo = "TESTE_" + uuid.uuid4().hex[:12].upper()
    ano = 2023

    with conexao.transaction():
        with conexao.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO
                homologacao_aula54.indicadores
                (codigo_pais, ano, pib_usd)
                VALUES (%s, %s, %s)
                """,
                (codigo, ano, 2000),
            )

            cursor.execute(
                """
                UPDATE homologacao_aula54.indicadores
                SET pib_usd = %s
                WHERE codigo_pais = %s
                  AND ano = %s
                """,
                (2100, codigo, ano),
            )

            cursor.execute(
                """
                DELETE FROM
                homologacao_aula54.indicadores
                WHERE codigo_pais = %s
                  AND ano = %s
                """,
                (codigo, ano),
            )

            cursor.execute(
                """
                SELECT
                    operacao,
                    valor_anterior,
                    valor_novo
                FROM homologacao_aula54.eventos_cdc
                WHERE codigo_pais = %s
                  AND ano = %s
                ORDER BY id
                """,
                (codigo, ano),
            )

            eventos = cursor.fetchall()

    esperado = [
        ("INSERT", None, 2000),
        ("UPDATE", 2000, 2100),
        ("DELETE", 2100, None),
    ]

    if eventos != esperado:
        raise AssertionError(
            f"Eventos CDC inesperados: {eventos}"
        )

    return {
        "codigo_teste": codigo,
        "eventos": [
            {
                "operacao": operacao,
                "valor_anterior": (
                    float(anterior)
                    if anterior is not None
                    else None
                ),
                "valor_novo": (
                    float(novo)
                    if novo is not None
                    else None
                ),
            }
            for operacao, anterior, novo in eventos
        ],
    }


def executar():
    url = validar_ambiente()

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        criar_estrutura(conexao)
        teste = executar_teste(conexao)

    resultado = {
        "ambiente": "staging",
        "tipo": "cdc_por_triggers",
        "eventos_capturados": len(
            teste["eventos"]
        ),
        "eventos": teste["eventos"],
        "status": "sucesso",
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "cdc/resultados/relatorio_cdc.json"
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
