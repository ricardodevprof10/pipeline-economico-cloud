
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from contrato import validar_resposta


BASE_URL = (
    "https://pipeline-economico-cloud.onrender.com"
)

CAMINHO = "/api/indicadores"
MAX_TENTATIVAS = 3


def consultar_api():
    url = BASE_URL + CAMINHO

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            requisicao = Request(
                url,
                headers={
                    "User-Agent": "Integracao-Economica/1.0",
                    "Accept": "application/json",
                },
            )

            with urlopen(
                requisicao,
                timeout=60,
            ) as resposta:
                conteudo = resposta.read()
                status = resposta.status

            if status != 200:
                raise RuntimeError(
                    f"Status HTTP inesperado: {status}"
                )

            return json.loads(
                conteudo.decode("utf-8")
            )

        except HTTPError as erro:
            recuperavel = (
                erro.code == 429
                or 500 <= erro.code <= 599
            )

            if not recuperavel:
                raise

            if tentativa == MAX_TENTATIVAS:
                raise

        except (URLError, TimeoutError):
            if tentativa == MAX_TENTATIVAS:
                raise

        espera = 2 ** (tentativa - 1)

        print(
            f"Tentativa {tentativa} falhou. "
            f"Nova tentativa em {espera}s."
        )

        time.sleep(espera)


def executar():
    dados = consultar_api()
    erros = validar_resposta(dados)

    relatorio = {
        "data_verificacao": datetime.now(
            timezone.utc
        ).isoformat(),
        "endpoint": BASE_URL + CAMINHO,
        "total_registros": (
            len(dados)
            if isinstance(dados, list)
            else 0
        ),
        "total_erros": len(erros),
        "erros": erros,
        "aprovado": len(erros) == 0,
    }

    pasta = Path("integracao/resultados")
    pasta.mkdir(
        parents=True,
        exist_ok=True,
    )

    destino = pasta / "relatorio_integracao.json"

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

    return 0 if relatorio["aprovado"] else 1


if __name__ == "__main__":
    try:
        sys.exit(executar())

    except Exception as erro:
        print(
            f"Falha na integração: "
            f"{type(erro).__name__}: {erro}",
            file=sys.stderr,
        )

        sys.exit(1)
