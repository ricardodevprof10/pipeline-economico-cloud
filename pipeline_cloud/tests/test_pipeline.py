
from src.pipeline import transformar, gerar_gold


def test_transformacao():
    registros = [{
        "country": {"value": "Brazil"},
        "date": "2024",
        "value": 2000000000000
    }]

    resultado = transformar(registros)

    assert len(resultado) == 1
    assert resultado.iloc[0]["ano"] == 2024


def test_valor_nulo():
    registros = [{
        "country": {"value": "Brazil"},
        "date": "2024",
        "value": None
    }]

    resultado = transformar(registros)

    assert resultado.empty


def test_gold():
    registros = [{
        "country": {"value": "Brazil"},
        "date": "2024",
        "value": 2000000000000
    }]

    silver = transformar(registros)
    gold = gerar_gold(silver)

    assert gold.iloc[0]["pib_bilhoes_usd"] == 2000
