
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

COLUNAS = {
    "codigo_pais",
    "nome_pais",
    "ano",
    "pib_usd"
}


def validar_dados(registros):
    erros = []
    alertas = []
    chaves = set()
    series = defaultdict(list)

    if not isinstance(registros, list):
        raise TypeError(
            "Os dados devem ser uma lista."
        )

    if not registros:
        erros.append("Nenhum registro encontrado.")

    for posicao, registro in enumerate(
        registros, start=1
    ):
        if not isinstance(registro, dict):
            erros.append(
                f"Registro {posicao}: formato inválido."
            )
            continue

        ausentes = COLUNAS - registro.keys()

        if ausentes:
            erros.append(
                f"Registro {posicao}: colunas ausentes "
                f"{sorted(ausentes)}"
            )
            continue

        codigo = registro["codigo_pais"]
        nome = registro["nome_pais"]
        ano = registro["ano"]
        pib = registro["pib_usd"]

        if (
            not isinstance(codigo, str)
            or not codigo.strip()
            or not isinstance(nome, str)
            or not nome.strip()
        ):
            erros.append(
                f"Registro {posicao}: país inválido."
            )
            continue

        if (
            isinstance(ano, bool)
            or not isinstance(ano, int)
            or ano < 1960
            or ano > datetime.now().year
        ):
            erros.append(
                f"Registro {posicao}: ano inválido."
            )
            continue

        chave = (codigo, ano)

        if chave in chaves:
            erros.append(
                f"Duplicidade: {codigo}, {ano}"
            )

        chaves.add(chave)

        if (
            pib is None
            or isinstance(pib, bool)
            or not isinstance(pib, (int, float))
        ):
            erros.append(
                f"Registro {posicao}: PIB inválido."
            )
            continue

        import math

        if not math.isfinite(pib) or pib < 0:
            erros.append(
                f"Registro {posicao}: PIB fora "
                "do intervalo permitido."
            )
            continue

        series[codigo].append((ano, pib))

    for codigo, valores in series.items():
        valores.sort()

        for anterior, atual in zip(
            valores, valores[1:]
        ):
            ano_anterior, pib_anterior = anterior
            ano_atual, pib_atual = atual

            if ano_atual != ano_anterior + 1:
                continue

            if pib_anterior <= 0:
                continue

            variacao = (
                pib_atual / pib_anterior - 1
            ) * 100

            if abs(variacao) > 30:
                alertas.append({
                    "pais": codigo,
                    "ano": ano_atual,
                    "variacao_percentual": round(
                        variacao, 2
                    ),
                    "mensagem": (
                        "Variação nominal elevada; "
                        "requer investigação."
                    )
                })

    return {
        "total_registros": len(registros),
        "total_erros": len(erros),
        "total_alertas": len(alertas),
        "erros": erros,
        "alertas": alertas,
        "aprovado": len(erros) == 0
    }


def carregar_dados():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não configurada."
        )

    import psycopg

    consulta = """
        SELECT
            codigo_pais,
            nome_pais,
            ano,
            pib_usd
        FROM dw.vw_pib_anual
        ORDER BY codigo_pais, ano
    """

    with psycopg.connect(
        database_url,
        connect_timeout=10
    ) as conexao:

        with conexao.cursor() as cursor:
            cursor.execute(consulta)
            linhas = cursor.fetchall()

    return [
        {
            "codigo_pais": codigo,
            "nome_pais": nome,
            "ano": int(ano),
            "pib_usd": float(pib)
                if pib is not None else None
        }
        for codigo, nome, ano, pib in linhas
    ]


def executar():
    registros = carregar_dados()
    relatorio = validar_dados(registros)

    relatorio["data_verificacao"] = (
        datetime.now(timezone.utc).isoformat()
    )

    pasta = Path("qualidade/resultados")
    pasta.mkdir(parents=True, exist_ok=True)

    destino = pasta / "relatorio_qualidade.json"

    destino.write_text(
        json.dumps(
            relatorio,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        json.dumps(
            relatorio,
            indent=4,
            ensure_ascii=False
        )
    )

    return 0 if relatorio["aprovado"] else 1


if __name__ == "__main__":
    try:
        sys.exit(executar())
    except Exception as erro:
        print(
            f"Falha na validação: "
            f"{type(erro).__name__}: {erro}",
            file=sys.stderr
        )
        sys.exit(1)
