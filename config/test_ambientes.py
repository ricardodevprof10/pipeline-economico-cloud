
from validar_ambientes import validar


def configuracao_valida():
    return {
        "development": {
            "descricao": "Desenvolvimento",
            "dados": "ficticios",
            "permite_carga_producao": False,
            "auditoria": True,
        },
        "staging": {
            "descricao": "Homologacao",
            "dados": "controlados",
            "permite_carga_producao": False,
            "auditoria": True,
        },
        "production": {
            "descricao": "Producao",
            "dados": "oficiais",
            "permite_carga_producao": True,
            "auditoria": True,
        },
    }


def test_configuracao_valida():
    assert validar(configuracao_valida()) == []


def test_bloquear_carga_desenvolvimento():
    config = configuracao_valida()

    config["development"][
        "permite_carga_producao"
    ] = True

    assert validar(config)


def test_bloquear_carga_homologacao():
    config = configuracao_valida()

    config["staging"][
        "permite_carga_producao"
    ] = True

    assert validar(config)


def test_ambiente_ausente():
    config = configuracao_valida()
    del config["staging"]

    assert validar(config)


def test_tipo_incorreto():
    config = configuracao_valida()

    config["production"]["auditoria"] = "sim"

    assert validar(config)
