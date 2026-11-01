
import math
from datetime import datetime, timezone


CAMPOS_OBRIGATORIOS = {
    "codigo_pais",
    "nome_pais",
    "ano",
    "pib_usd",
    "pib_bilhoes_usd",
}


def validar_registro(registro):
    erros = []

    if not isinstance(registro, dict):
        return ["Registro não é um objeto JSON."]

    ausentes = CAMPOS_OBRIGATORIOS - registro.keys()

    if ausentes:
        return [
            f"Campos ausentes: {sorted(ausentes)}"
        ]

    codigo = registro["codigo_pais"]
    nome = registro["nome_pais"]
    ano = registro["ano"]
    pib = registro["pib_usd"]
    pib_bilhoes = registro["pib_bilhoes_usd"]

    if (
        not isinstance(codigo, str)
        or len(codigo) != 3
        or not codigo.isalpha()
    ):
        erros.append("Código de país inválido.")

    if not isinstance(nome, str) or not nome.strip():
        erros.append("Nome de país inválido.")

    ano_maximo = datetime.now(timezone.utc).year

    if (
        isinstance(ano, bool)
        or not isinstance(ano, int)
        or not 1960 <= ano <= ano_maximo
    ):
        erros.append("Ano inválido.")

    for campo, valor in [
        ("pib_usd", pib),
        ("pib_bilhoes_usd", pib_bilhoes),
    ]:
        if (
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(valor)
            or valor < 0
        ):
            erros.append(f"{campo} inválido.")

    if not erros:
        esperado = pib / 1_000_000_000

        if not math.isclose(
            pib_bilhoes,
            esperado,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            erros.append(
                "PIB em bilhões não corresponde "
                "ao PIB em dólares."
            )

    return erros


def validar_resposta(dados):
    if not isinstance(dados, list):
        return ["A resposta não é uma lista JSON."]

    if not dados:
        return ["A API retornou uma lista vazia."]

    erros = []
    chaves = set()

    for indice, registro in enumerate(dados, start=1):
        erros_registro = validar_registro(registro)

        for erro in erros_registro:
            erros.append(
                f"Registro {indice}: {erro}"
            )

        if not erros_registro:
            chave = (
                registro["codigo_pais"],
                registro["ano"],
            )

            if chave in chaves:
                erros.append(
                    f"Duplicidade: {chave}"
                )

            chaves.add(chave)

    return erros
