
import json
import subprocess
import sys
from pathlib import Path

# Diretórios do projeto
PROJETO = Path(__file__).resolve().parents[2]
PIPELINE = PROJETO / "pipeline_cloud"
DADOS = PIPELINE / "dados"
LOGS = DADOS / "logs"

# Importa a auditoria da aula anterior
sys.path.insert(0, str(PROJETO))

from auditoria.auditor import AuditorPipeline


def executar_comando(modulo):
    subprocess.run(
        [sys.executable, "-m", modulo],
        cwd=PIPELINE,
        check=True,
    )


def executar_etl():
    executar_comando("src.pipeline")

    caminho = LOGS / "relatorio.json"

    if not caminho.is_file():
        raise FileNotFoundError(
            "Relatório do ETL não encontrado."
        )

    with caminho.open(
        encoding="utf-8"
    ) as arquivo:
        relatorio = json.load(arquivo)

    if relatorio.get("status") != "SUCESSO":
        raise RuntimeError(
            "O ETL não informou sucesso."
        )

    return relatorio


def executar_carga():
    executar_comando("src.persistir_postgres")

    return {
        "status": "sucesso",
        "destino": "PostgreSQL",
    }


def main():
    auditor = AuditorPipeline(
        "pipeline_economico_producao"
    )

    relatorio_etl = None

    try:
        relatorio_etl = auditor.executar_etapa(
            "etl_bronze_silver_gold",
            executar_etl,
        )

        auditor.executar_etapa(
            "persistencia_postgresql",
            executar_carga,
        )

    finally:
        relatorio = auditor.salvar(
            LOGS / "auditoria_execucao.json"
        )

        if relatorio_etl is not None:
            relatorio["metricas_etl"] = {
                "registros_bronze":
                    relatorio_etl.get(
                        "registros_bronze"
                    ),
                "registros_silver":
                    relatorio_etl.get(
                        "registros_silver"
                    ),
                "registros_gold":
                    relatorio_etl.get(
                        "registros_gold"
                    ),
            }

            destino = (
                LOGS / "auditoria_execucao.json"
            )

            destino.write_text(
                json.dumps(
                    relatorio,
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        print(
            json.dumps(
                relatorio,
                indent=4,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
