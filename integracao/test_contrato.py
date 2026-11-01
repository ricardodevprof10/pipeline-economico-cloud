
from contrato import (
    validar_registro,
    validar_resposta,
)


def exemplo():
    return {
        "codigo_pais": "BRA",
        "nome_pais": "Brasil",
        "ano": 2023,
        "pib_usd": 2_000_000_000_000.0,
        "pib_bilhoes_usd": 2000.0,
    }


def test_registro_valido():
    assert validar_registro(exemplo()) == []


def test_campo_ausente():
    dado = exemplo()
    del dado["pib_usd"]

    assert validar_registro(dado)


def test_pib_negativo():
    dado = exemplo()
    dado["pib_usd"] = -100

    assert validar_registro(dado)


def test_conversao_incorreta():
    dado = exemplo()
    dado["pib_bilhoes_usd"] = 100

    assert validar_registro(dado)


def test_duplicidade():
    dado = exemplo()

    erros = validar_resposta([
        dado,
        dado.copy(),
    ])

    assert any(
        "Duplicidade" in erro
        for erro in erros
    )


def test_lista_valida():
    assert validar_resposta([exemplo()]) == []
