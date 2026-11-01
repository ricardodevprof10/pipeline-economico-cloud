
import json
import sys
from pathlib import Path


ARQUIVO = Path(__file__).with_name(
    "ambientes.json"
)

AMBIENTES = {
    "development",
    "staging",
    "production",
}


def validar(configuracao):
    erros = []

    if not isinstance(configuracao, dict):
        return ["Configuracao deve ser um objeto JSON."]

    encontrados = set(configuracao)

    if encontrados != AMBIENTES:
        erros.append(
            "Ambientes esperados: "
            "development, staging e production."
        )

    for nome in AMBIENTES:
        ambiente = configuracao.get(nome)

        if not isinstance(ambiente, dict):
            erros.append(
                f"{nome}: configuracao ausente."
            )
            continue

        for campo in [
            "descricao",
            "dados",
        ]:
            valor = ambiente.get(campo)

            if (
                not isinstance(valor, str)
                or not valor.strip()
            ):
                erros.append(
                    f"{nome}: campo {campo} invalido."
                )

        for campo in [
            "permite_carga_producao",
            "auditoria",
        ]:
            if not isinstance(
                ambiente.get(campo),
                bool,
            ):
                erros.append(
                    f"{nome}: campo {campo} "
                    "deve ser booleano."
                )

    for nome in [
        "development",
        "staging",
    ]:
        ambiente = configuracao.get(nome, {})

        if (
            isinstance(ambiente, dict)
            and ambiente.get(
                "permite_carga_producao"
            ) is not False
        ):
            erros.append(
                f"{nome}: carga em producao proibida."
            )

    producao = configuracao.get(
        "production",
        {},
    )

    if (
        isinstance(producao, dict)
        and producao.get(
            "permite_carga_producao"
        ) is not True
    ):
        erros.append(
            "production: carga em producao "
            "deve estar explicitamente autorizada."
        )

    return erros


def executar():
    with ARQUIVO.open(
        encoding="utf-8"
    ) as arquivo:
        configuracao = json.load(arquivo)

    erros = validar(configuracao)

    if erros:
        print("Configuracao reprovada.")

        for erro in erros:
            print(f"- {erro}")

        return 1

    print("Configuracao dos ambientes aprovada.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(executar())

    except Exception as erro:
        print(
            f"Falha: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        sys.exit(1)
