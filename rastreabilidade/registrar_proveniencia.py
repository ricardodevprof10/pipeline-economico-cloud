
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


API_URL = (
    "https://pipeline-economico-cloud.onrender.com"
    "/api/indicadores"
)


def gerar_hash(dados):
    conteudo = json.dumps(
        dados,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(conteudo).hexdigest()


def consultar_api():
    requisicao = Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Data-Lineage/1.0",
        },
    )

    with urlopen(requisicao, timeout=60) as resposta:
        if resposta.status != 200:
            raise RuntimeError(
                f"HTTP inesperado: {resposta.status}"
            )

        return json.loads(
            resposta.read().decode("utf-8")
        )


def criar_relatorio(dados, versao_codigo):
    if not isinstance(dados, list) or not dados:
        raise ValueError(
            "A API deve retornar uma lista não vazia."
        )

    return {
        "data_execucao": datetime.now(
            timezone.utc
        ).isoformat(),
        "fonte_consultada": API_URL,
        "sistema_origem": (
            "API do dashboard economico"
        ),
        "formato": "JSON",
        "quantidade_registros": len(dados),
        "versao_codigo": versao_codigo,
        "algoritmo_hash": "SHA-256",
        "hash_conteudo": gerar_hash(dados),
        "status": "registrado",
    }


def executar():
    dados = consultar_api()

    versao = os.getenv(
        "GITHUB_SHA",
        "execucao_manual",
    )

    relatorio = criar_relatorio(
        dados,
        versao,
    )

    pasta = Path("rastreabilidade/resultados")
    pasta.mkdir(parents=True, exist_ok=True)

    caminho = pasta / "proveniencia.json"

    caminho.write_text(
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
    try:
        executar()

    except Exception as erro:
        print(
            f"Erro: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        sys.exit(1)
