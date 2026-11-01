
import json
from auditor import AuditorPipeline


def extrair():
    return [
        {
            "pais": "BRA",
            "ano": 2023,
            "pib_usd": 2000000000000,
        },
        {
            "pais": "ARG",
            "ano": 2023,
            "pib_usd": 600000000000,
        },
    ]


def transformar(registros):
    return [
        {
            **registro,
            "pib_bilhoes_usd": (
                registro["pib_usd"] / 1_000_000_000
            ),
        }
        for registro in registros
    ]


def carregar_simulado(registros):
    return {
        "registros_processados": len(registros),
        "destino": "simulacao",
    }


def executar():
    auditor = AuditorPipeline(
        "pipeline_economico_demo"
    )

    try:
        dados = auditor.executar_etapa(
            "extracao",
            extrair,
        )

        transformados = auditor.executar_etapa(
            "transformacao",
            lambda: transformar(dados),
        )

        auditor.executar_etapa(
            "carga_simulada",
            lambda: carregar_simulado(
                transformados
            ),
        )

    finally:
        relatorio = auditor.salvar(
            "auditoria/resultados/"
            "relatorio_auditoria.json"
        )

        print(
            json.dumps(
                relatorio,
                indent=4,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    executar()
