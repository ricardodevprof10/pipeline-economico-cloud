
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = (
    "https://pipeline-economico-cloud.onrender.com"
)

RESULTADO = {
    "data_verificacao": datetime.now(
        timezone.utc
    ).isoformat(),
    "servico": BASE_URL,
    "verificacoes": []
}


def verificar_endpoint(caminho, validar_dados=False):
    url = BASE_URL + caminho
    inicio = time.perf_counter()

    registro = {
        "endpoint": caminho,
        "status_http": None,
        "latencia_ms": None,
        "sucesso": False,
        "erro": None
    }

    try:
        requisicao = Request(
            url,
            headers={
                "User-Agent": "Monitor-Economico/1.0"
            }
        )

        with urlopen(
            requisicao,
            timeout=60
        ) as resposta:

            status = resposta.status
            conteudo = resposta.read()

        registro["status_http"] = status

        if status != 200:
            raise ValueError(
                f"Status HTTP inesperado: {status}"
            )

        dados = json.loads(
            conteudo.decode("utf-8")
        )

        if validar_dados:
            if not isinstance(dados, list):
                raise ValueError(
                    "A API não retornou uma lista."
                )

            if not dados:
                raise ValueError(
                    "A API retornou uma lista vazia."
                )

            registro["total_registros"] = len(dados)

        else:
            if dados.get("status") != "ok":
                raise ValueError(
                    "Health check inválido."
                )

        registro["sucesso"] = True

    except HTTPError as erro:
        registro["status_http"] = erro.code
        registro["erro"] = str(erro)

    except (
        URLError,
        TimeoutError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError
    ) as erro:
        registro["erro"] = str(erro)

    except Exception as erro:
        registro["erro"] = (
            f"{type(erro).__name__}: {erro}"
        )

    finally:
        registro["latencia_ms"] = round(
            (time.perf_counter() - inicio) * 1000,
            2
        )

    return registro


verificacoes = [
    verificar_endpoint("/health"),
    verificar_endpoint(
        "/api/indicadores",
        validar_dados=True
    )
]

RESULTADO["verificacoes"] = verificacoes
RESULTADO["sucesso_geral"] = all(
    item["sucesso"] for item in verificacoes
)

pasta = Path("monitoramento/resultados")
pasta.mkdir(parents=True, exist_ok=True)

arquivo = pasta / "ultima_verificacao.json"

arquivo.write_text(
    json.dumps(
        RESULTADO,
        indent=4,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

for item in verificacoes:
    situacao = (
        "OK" if item["sucesso"] else "FALHA"
    )

    print(
        f"{situacao} | "
        f"{item['endpoint']} | "
        f"HTTP {item['status_http']} | "
        f"{item['latencia_ms']} ms"
    )

    if item["erro"]:
        print("Erro:", item["erro"])

print(
    "Resultado geral:",
    "SUCESSO" if RESULTADO["sucesso_geral"]
    else "FALHA"
)

sys.exit(
    0 if RESULTADO["sucesso_geral"] else 1
)
