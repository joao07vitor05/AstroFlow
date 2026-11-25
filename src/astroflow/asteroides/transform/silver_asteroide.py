# Carga da silver.asteroide: um registro por "des" (designação),
# juntando os des de CAD, Sentry (resumo + removidos) e NeoWs (lookup).
from astroflow.config import get_connection

# Cada SELECT devolve (des, fullname, prioridade).
# Se o mesmo des aparece em várias fontes, fica a linha de menor prioridade.
# O Sentry resumo vem primeiro porque é o único que traz fullname.
SQL_CARGA = """
INSERT INTO silver.asteroide (des, fullname)
SELECT DISTINCT ON (des) des, fullname
FROM (
    -- Sentry resumo (modo S): último snapshot; fullname com strip
    SELECT item->>'des' AS des,
           NULLIF(btrim(item->>'fullname'), '') AS fullname,
           1 AS prioridade
    FROM bronze.sentry_raw b,
         jsonb_array_elements(b.payload->'data') AS item
    WHERE b.source = 'sentry_resumo'
      AND b.id = (SELECT max(id) FROM bronze.sentry_raw WHERE source = 'sentry_resumo')

    UNION ALL

    -- Sentry removidos (modo R): sem nome
    SELECT item->>'des', NULL, 2
    FROM bronze.sentry_raw b,
         jsonb_array_elements(b.payload->'data') AS item
    WHERE b.source = 'sentry_removidos'
      AND b.id = (SELECT max(id) FROM bronze.sentry_raw WHERE source = 'sentry_removidos')

    UNION ALL

    -- CAD: data é lista de listas; o des é o 1º elemento de cada linha
    SELECT linha->>0, NULL, 3
    FROM bronze.cad_raw b,
         jsonb_array_elements(b.payload->'data') AS linha
    WHERE b.source = 'cad_terra'
      AND b.id = (SELECT max(id) FROM bronze.cad_raw WHERE source = 'cad_terra')

    UNION ALL

    -- NeoWs lookup: campo "designation" (uso todas as linhas; só importa o des)
    SELECT b.payload->>'designation', NULL, 4
    FROM bronze.neows_lookup_raw b
) AS todos
WHERE des IS NOT NULL
ORDER BY des, prioridade
ON CONFLICT (des) DO UPDATE
SET fullname = COALESCE(EXCLUDED.fullname, silver.asteroide.fullname);
"""


def carregar_silver_asteroide() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Conferência: o 1º campo do CAD precisa ser mesmo "des"
            cur.execute(
                """
                SELECT payload->'fields'->>0
                FROM bronze.cad_raw
                WHERE source = 'cad_terra'
                ORDER BY id DESC LIMIT 1
                """
            )
            assert cur.fetchone()[0] == "des", "CAD: 1º campo de fields não é 'des'"

            cur.execute(SQL_CARGA)
            print(f"Linhas inseridas em silver.asteroide: {cur.rowcount}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_asteroide()
