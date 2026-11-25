# src/astroflow/asteroides/gold/gold_fact_impacto_virtual.py
# Carga da gold.fact_impacto_virtual a partir da silver.sentry_impacto_virtual.
# Política: full refresh (TRUNCATE + INSERT na mesma transação).
# Pré-requisito: gold.dim_asteroide já carregada (precisamos da asteroide_sk).
from astroflow.config import get_connection

SQL_LIMPAR = "TRUNCATE gold.fact_impacto_virtual RESTART IDENTITY;"

SQL_CARGA = """
INSERT INTO gold.fact_impacto_virtual (
    asteroide_sk, posicao, data_impacto, ip, ps, ts, energy,
    metodo, sigma_vi, sigma_mc, bronze_id
)
SELECT
    d.asteroide_sk,         -- troca o texto "des" pela chave numérica da dimensão
    v.posicao, v.data_impacto, v.ip, v.ps, v.ts, v.energy,
    v.metodo, v.sigma_vi, v.sigma_mc, v.bronze_id
FROM silver.sentry_impacto_virtual v
JOIN gold.dim_asteroide d ON d.des = v.des
ORDER BY v.des, v.posicao;  -- ordem fixa: mesmas chaves a cada carga
"""

SQL_CONTAGEM = """
SELECT
    (SELECT COUNT(*) FROM silver.sentry_impacto_virtual),
    (SELECT COUNT(*) FROM gold.fact_impacto_virtual);
"""


def main():
    # commit no final; se algo falhar, desfaz tudo (inclusive o TRUNCATE)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_LIMPAR)
            cur.execute(SQL_CARGA)

            cur.execute(SQL_CONTAGEM)
            qtd_silver, qtd_gold = cur.fetchone()
            print(f"fact_impacto_virtual: silver={qtd_silver} gold={qtd_gold}")

            # nenhuma linha pode se perder no JOIN com a dimensão
            assert qtd_silver == qtd_gold, (
                f"perdeu linhas no JOIN: silver={qtd_silver}, gold={qtd_gold}. "
                "A dim_asteroide foi carregada antes?"
            )


if __name__ == "__main__":
    main()