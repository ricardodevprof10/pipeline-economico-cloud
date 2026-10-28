
from validar_dados import validar_dados


def registro(
    codigo="BRA",
    ano=2023,
    pib=2_000_000_000_000
):
    return {
        "codigo_pais": codigo,
        "nome_pais": "Brasil",
        "ano": ano,
        "pib_usd": pib
    }


def test_registro_valido():
    resultado = validar_dados([
        registro()
    ])

    assert resultado["aprovado"] is True
    assert resultado["total_erros"] == 0


def test_lista_vazia():
    resultado = validar_dados([])

    assert resultado["aprovado"] is False


def test_duplicidade():
    resultado = validar_dados([
        registro(),
        registro()
    ])

    assert resultado["aprovado"] is False
    assert resultado["total_erros"] >= 1


def test_pib_negativo():
    resultado = validar_dados([
        registro(pib=-100)
    ])

    assert resultado["aprovado"] is False


def test_variacao_elevada():
    resultado = validar_dados([
        registro(ano=2022, pib=100),
        registro(ano=2023, pib=150)
    ])

    assert resultado["aprovado"] is True
    assert resultado["total_alertas"] == 1
