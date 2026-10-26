import os
import csv
import logging
from pathlib import Path
from decimal import Decimal, InvalidOperation

import psycopg


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("postgres")


def preparar_registros(caminho_csv):
    registros = []
    chaves = set()

    with open(
        caminho_csv,
        newline="",
        encoding="utf-8"
    ) as arquivo:
        leitor = csv.DictReader(arquivo)

        obrigatorias = {"pais", "ano", "pib_usd"}

        if not obrigatorias.issubset(
            set(leitor.fieldnames or [])
        ):
            raise ValueError("Colunas obrigatórias ausentes.")

        for linha in leitor:
            pais = linha["pais"].strip()

            if not pais:
                raise ValueError("País vazio.")

            try:
                ano = int(linha["ano"])
                pib = Decimal(linha["pib_usd"])
            except (ValueError, InvalidOperation):
                raise ValueError("Ano ou PIB inválido.")

            if not pib.is_finite() or pib <= 0:
                raise ValueError("PIB inválido.")

            # O pipeline atual consulta apenas o Brasil.
            codigo = "BRA"

            chave = (codigo, ano)

            if chave in chaves:
                raise ValueError("País e ano duplicados.")

            chaves.add(chave)

            registros.append(
                (codigo, pais, ano, pib)
            )

    if not registros:
        raise ValueError("Arquivo Gold vazio.")

    return registros


def persistir(caminho_csv):
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não configurada."
        )

    registros = preparar_registros(caminho_csv)

    with psycopg.connect(
        database_url,
        connect_timeout=15
    ) as conexao:

        with conexao.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pib_paises (
                    codigo_pais VARCHAR(3) NOT NULL,
                    pais VARCHAR(150) NOT NULL,
                    ano INTEGER NOT NULL,
                    pib_usd NUMERIC(24, 2) NOT NULL,
                    atualizado_em TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    PRIMARY KEY (codigo_pais, ano),

                    CHECK (pib_usd > 0)
                )
            """)

            alteracoes = 0

            for registro in registros:
                cursor.execute("""
                    INSERT INTO pib_paises (
                        codigo_pais,
                        pais,
                        ano,
                        pib_usd
                    )
                    VALUES (%s, %s, %s, %s)

                    ON CONFLICT (codigo_pais, ano)
                    DO UPDATE SET
                        pais = EXCLUDED.pais,
                        pib_usd = EXCLUDED.pib_usd,
                        atualizado_em = CURRENT_TIMESTAMP

                    WHERE
                        pib_paises.pais IS DISTINCT FROM
                            EXCLUDED.pais
                        OR
                        pib_paises.pib_usd IS DISTINCT FROM
                            EXCLUDED.pib_usd
                """, registro)

                alteracoes += cursor.rowcount

        conexao.commit()

    logger.info(
        "Registros recebidos: %s",
        len(registros)
    )

    logger.info(
        "Registros inseridos ou atualizados: %s",
        alteracoes
    )


if __name__ == "__main__":
    caminho = (
        Path(__file__).resolve().parents[1]
        / "dados"
        / "gold"
        / "pib.csv"
    )

    persistir(caminho)
