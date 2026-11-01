
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def horario_utc():
    return datetime.now(timezone.utc).isoformat()


class AuditorPipeline:
    def __init__(self, nome_pipeline):
        self.nome_pipeline = nome_pipeline
        self.execucao_id = str(uuid.uuid4())
        self.inicio = horario_utc()
        self.versao_codigo = os.getenv(
            "GITHUB_SHA", "execucao_local"
        )
        self.etapas = []

    def executar_etapa(self, nome, funcao):
        inicio = horario_utc()
        cronometro = time.perf_counter()

        registro = {
            "etapa": nome,
            "inicio": inicio,
            "fim": None,
            "duracao_segundos": None,
            "status": "executando",
            "erro": None,
        }

        try:
            resultado = funcao()
            registro["status"] = "sucesso"
            return resultado

        except Exception as erro:
            registro["status"] = "falha"
            registro["erro"] = (
                f"{type(erro).__name__}: {erro}"
            )
            raise

        finally:
            registro["fim"] = horario_utc()
            registro["duracao_segundos"] = round(
                time.perf_counter() - cronometro,
                4,
            )
            self.etapas.append(registro)

    def gerar_relatorio(self):
        falhas = sum(
            etapa["status"] == "falha"
            for etapa in self.etapas
        )

        return {
            "pipeline": self.nome_pipeline,
            "execucao_id": self.execucao_id,
            "inicio": self.inicio,
            "fim": horario_utc(),
            "versao_codigo": self.versao_codigo,
            "total_etapas": len(self.etapas),
            "total_falhas": falhas,
            "status": (
                "sucesso" if falhas == 0
                else "falha"
            ),
            "etapas": self.etapas,
        }

    def salvar(self, destino):
        caminho = Path(destino)
        caminho.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        relatorio = self.gerar_relatorio()

        caminho.write_text(
            json.dumps(
                relatorio,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return relatorio
