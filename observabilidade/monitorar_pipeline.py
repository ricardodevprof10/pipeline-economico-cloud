
import json
import os
import sys
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg


SCHEMA = "homologacao_aula58"
LIMITE_TAXA_SUCESSO = 90.0


def log_json(nivel, evento, **detalhes):
    registro = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "nivel": nivel,
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
                homologacao_aula58
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                homologacao_aula58.historico_monitoramento (
                    execucao_id TEXT PRIMARY KEY,
                    eventos_recebidos INTEGER NOT NULL,
                    eventos_processados INTEGER NOT NULL,
                    eventos_dlq INTEGER NOT NULL,
                    taxa_sucesso NUMERIC NOT NULL,
                    duracao_segundos NUMERIC NOT NULL,
                    alerta_ativo BOOLEAN NOT NULL,
                    executado_em TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )

            tabelas = [
                "homologacao_aula57.eventos",
                "homologacao_aula57.eventos_processados",
                "homologacao_aula57.dead_letter_queue",
            ]

            for tabela in tabelas:
                cursor.execute(
                    "SELECT to_regclass(%s)",
                    (tabela,),
                )

                if cursor.fetchone()[0] is None:
                    raise RuntimeError(
                        f"Tabela nao encontrada: {tabela}"
                    )


def coletar_metricas(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula57.eventos
            """
        )
        recebidos = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula57.eventos_processados
            """
        )
        processados = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM homologacao_aula57.dead_letter_queue
            """
        )
        dlq = cursor.fetchone()[0]

    taxa = (
        round(
            (processados / recebidos) * 100,
            2,
        )
        if recebidos > 0
        else 0.0
    )

    return {
        "eventos_recebidos": recebidos,
        "eventos_processados": processados,
        "eventos_dlq": dlq,
        "taxa_sucesso": taxa,
    }


def registrar_historico(
    conexao,
    execucao_id,
    metricas,
    duracao,
    alerta,
):
    with conexao.transaction():
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO
                homologacao_aula58.historico_monitoramento
                (
                    execucao_id,
                    eventos_recebidos,
                    eventos_processados,
                    eventos_dlq,
                    taxa_sucesso,
                    duracao_segundos,
                    alerta_ativo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    execucao_id,
                    metricas["eventos_recebidos"],
                    metricas["eventos_processados"],
                    metricas["eventos_dlq"],
                    metricas["taxa_sucesso"],
                    duracao,
                    alerta,
                ),
            )


def executar():
    inicio = time.perf_counter()
    execucao_id = uuid.uuid4().hex
    url = validar_ambiente()

    log_json(
        "INFO",
        "monitoramento_iniciado",
        execucao_id=execucao_id,
        ambiente="staging",
    )

    with psycopg.connect(
        url,
        connect_timeout=15,
        autocommit=True,
    ) as conexao:

        criar_estrutura(conexao)

        metricas = coletar_metricas(conexao)

        alerta = (
            metricas["eventos_recebidos"] > 0
            and metricas["taxa_sucesso"]
            < LIMITE_TAXA_SUCESSO
        )

        duracao = round(
            time.perf_counter() - inicio,
            4,
        )

        registrar_historico(
            conexao,
            execucao_id,
            metricas,
            duracao,
            alerta,
        )

    nivel = "WARNING" if alerta else "INFO"

    log_json(
        nivel,
        "metricas_coletadas",
        execucao_id=execucao_id,
        **metricas,
        alerta_ativo=alerta,
    )

    if alerta:
        log_json(
            "WARNING",
            "limite_taxa_sucesso_atingido",
            execucao_id=execucao_id,
            limite=LIMITE_TAXA_SUCESSO,
            taxa_atual=metricas["taxa_sucesso"],
        )

    resultado = {
        "ambiente": "staging",
        "execucao_id": execucao_id,
        **metricas,
        "duracao_segundos": duracao,
        "limite_taxa_sucesso": LIMITE_TAXA_SUCESSO,
        "alerta_ativo": alerta,
        "status": (
            "atencao" if alerta else "sucesso"
        ),
        "executado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    destino = Path(
        "observabilidade/resultados/"
        "relatorio_monitoramento.json"
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

    log_json(
        "INFO",
        "monitoramento_finalizado",
        execucao_id=execucao_id,
        status=resultado["status"],
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
        log_json(
            "ERROR",
            "monitoramento_falhou",
            tipo_erro=type(erro).__name__,
            mensagem=str(erro),
        )
        sys.exit(1)
