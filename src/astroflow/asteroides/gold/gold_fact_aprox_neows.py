# src/astroflow/asteroides/gold/gold_fact_aprox_neows.py
# Carga da gold.fact_aprox_neows a partir da silver.neows_aproximacao.
# Política: full refresh (TRUNCATE + INSERT na mesma transação).
# Pré-requisito: gold.dim_asteroide já carregada (a dimensão guarda o neows_id).
from astroflow.config import get_connection

SQL_LIMPAR = "TRUNCATE gold.fact_aprox_neows RESTART IDENTITY;"

SQL_CARGA = """
INSERT INTO gold.fact_aprox_neows (
    asteroide_sk, corpo, data_aproximacao, data_hora, epoch_ms,
    dist_km, dist_au, dist_lunar, v_rel_km_s, bronze_id
)
SELECT
    d.asteroide_sk,         -- troca o neows_id pela chave numérica da dimensão
    n.corpo, n.data_aproximacao, n.data_hora, n.epoch_ms,
    n.dist_km, n.dist_au, n.dist_lunar, n.v_rel_km_s, n.bronze_id
FROM silver.neows_aproximacao n
JOIN gold.dim_asteroide d ON d.neows_id = n.neows_id
ORDER BY n.neows_id, n.data_hora, n.corpo;   -- ordem fixa: mesmas chaves a cada carga
"""

SQL_CONTAGEM = """
SELECT
    (SELECT COUNT(*) FROM silver.neows_aproximacao),
    (SELECT COUNT(*) FROM gold.fact_aprox_neows);
"""


def main():
    # commit no final; se algo falhar, desfaz tudo (inclusive o TRUNCATE)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_LIMPAR)
            cur.execute(SQL_CARGA)

            cur.execute(SQL_CONTAGEM)
            qtd_silver, qtd_gold = cur.fetchone()
            print(f"fact_aprox_neows: silver={qtd_silver} gold={qtd_gold}")

            # nenhuma linha pode se perder no JOIN com a dimensão
            assert qtd_silver == qtd_gold, (
                f"perdeu linhas no JOIN: silver={qtd_silver}, gold={qtd_gold}. "
                "A dim_asteroide foi carregada antes?"
            )


if __name__ == "__main__":
    main()