
import os
from decimal import Decimal

import psycopg
from flask import Flask, jsonify, render_template

app = Flask(__name__)


def consultar_indicadores():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não configurada."
        )

    sql = """
        SELECT
            codigo_pais,
            nome_pais,
            ano,
            pib_usd
        FROM dw.vw_pib_anual
        ORDER BY nome_pais, ano
    """

    with psycopg.connect(
        database_url,
        connect_timeout=10
    ) as conexao:

        with conexao.cursor() as cursor:
            cursor.execute(sql)
            registros = cursor.fetchall()

    dados = []

    for codigo, pais, ano, pib in registros:
        dados.append({
            "codigo_pais": codigo,
            "nome_pais": pais,
            "ano": int(ano),
            "pib_usd": float(pib),
            "pib_bilhoes_usd": float(
                Decimal(pib) / Decimal("1000000000")
            )
        })

    return dados


@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/indicadores")
def indicadores():
    try:
        dados = consultar_indicadores()
        return jsonify(dados)

    except Exception:
        app.logger.exception(
            "Falha ao consultar indicadores."
        )

        return jsonify({
            "erro": "Não foi possível consultar os dados."
        }), 503


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "servico": "dashboard-economico"
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
