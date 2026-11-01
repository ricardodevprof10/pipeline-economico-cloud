
import pytest

from auditor import AuditorPipeline


def test_execucao_sucesso():
    auditor = AuditorPipeline("teste")

    resultado = auditor.executar_etapa(
        "extracao",
        lambda: [1, 2, 3],
    )

    assert resultado == [1, 2, 3]

    relatorio = auditor.gerar_relatorio()

    assert relatorio["status"] == "sucesso"
    assert relatorio["total_etapas"] == 1


def test_registro_de_falha():
    auditor = AuditorPipeline("teste")

    def operacao_com_erro():
        raise ValueError("Falha simulada")

    with pytest.raises(ValueError):
        auditor.executar_etapa(
            "transformacao",
            operacao_com_erro,
        )

    relatorio = auditor.gerar_relatorio()

    assert relatorio["status"] == "falha"
    assert relatorio["total_falhas"] == 1
    assert relatorio["etapas"][0]["erro"]


def test_identificadores_unicos():
    primeiro = AuditorPipeline("teste")
    segundo = AuditorPipeline("teste")

    assert (
        primeiro.execucao_id
        != segundo.execucao_id
    )


def test_duracao_registrada():
    auditor = AuditorPipeline("teste")

    auditor.executar_etapa(
        "verificacao",
        lambda: True,
    )

    etapa = auditor.gerar_relatorio()["etapas"][0]

    assert etapa["duracao_segundos"] >= 0
    assert etapa["fim"] is not None
