# src/astroflow/asteroides/gold/gold_fact_aprox_cad.py
# Carga da gold.fact_aprox_cad a partir da silver.cad_aproximacao.
# Política: full refresh (TRUNCATE + INSERT na mesma transação).
# Pré-requisito: gold.dim_asteroide já carregada (precisamos da asteroide_sk).
from astroflow.config import get_connection

# RESTART IDENTITY zera o contador da chave aprox_cad_sk a cada carga
SQL_LIMPAR = "TRUNCATE gold.fact_aprox_cad RESTART IDENTITY;"

SQL_CARGA = """
INSERT INTO gold.fact_aprox_cad (
    asteroide_sk, data_hora, jd, orbit_id,
    dist, dist_min, dist_max, v_rel, v_inf,
    t_sigma_f, h, diameter, diameter_sigma, bronze_id
)
SELECT
    d.asteroide_sk,          -- troca o texto "des" pela chave numérica da dimensão
    c.cd,                    -- vira data_hora
    c.jd, c.orbit_id,
    c.dist, c.dist_min, c.dist_max, c.v_rel, c.v_inf,
    c.t_sigma_f, c.h, c.diameter, c.diameter_sigma, c.bronze_id
FROM silver.cad_aproximacao c
JOIN gold.dim_asteroide d ON d.des = c.des
ORDER BY c.cd, c.des;       -- ordem fixa: a carga sempre gera as mesmas chaves
"""

SQL_CONTAGEM = """
SELECT
    (SELECT COUNT(*) FROM silver.cad_aproximacao),
    (SELECT COUNT(*) FROM gold.fact_aprox_cad);
"""


def main():
    # "with" faz commit no final; se der erro no meio, desfaz tudo (inclusive o TRUNCATE)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_LIMPAR)
            cur.execute(SQL_CARGA)

            cur.execute(SQL_CONTAGEM)
            qtd_silver, qtd_gold = cur.fetchone()
            print(f"fact_aprox_cad: silver={qtd_silver} gold={qtd_gold}")

            # nenhuma linha pode se perder no JOIN com a dimensão
            assert qtd_silver == qtd_gold, (
                f"perdeu linhas no JOIN: silver={qtd_silver}, gold={qtd_gold}"
            )


if __name__ == "__main__":
    main()