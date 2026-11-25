# src/astroflow/gold/gold_dim_asteroide.py
# Carga da gold.dim_asteroide a partir da silver.
# Política: UPSERT por des (ON CONFLICT DO UPDATE). A asteroide_sk de um objeto
# que já existe nunca muda; objetos novos ganham uma SK nova.
from astroflow.config import get_connection

SQL_UPSERT = """
WITH base AS (
    -- 1 linha por objeto: parte da silver.asteroide e junta as outras (LEFT JOIN)
    SELECT
        a.des,
        a.fullname,
        n.neows_id,
        n.name                                   AS nome_neows,
        s.id_sentry,
        COALESCE(n.absolute_magnitude_h, s.h)    AS h_mag,   -- NeoWs primeiro, Sentry como reserva
        n.diameter_km_min                        AS diametro_km_min,
        n.diameter_km_max                        AS diametro_km_max,
        s.diameter                               AS diametro_sentry,
        n.is_pha,
        s.ip, s.ps_cum, s.ps_max, s.ts_max, s.n_imp, s.ano_min, s.ano_max,
        -- indicadores: o objeto aparece em cada tabela da silver?
        (s.des IS NOT NULL)                      AS em_sentry,
        EXISTS (SELECT 1 FROM silver.sentry_removido r
                WHERE r.des = a.des)             AS em_sentry_removido,
        EXISTS (SELECT 1 FROM silver.sentry_impacto_virtual v
                WHERE v.des = a.des)             AS tem_impacto_virtual,
        EXISTS (SELECT 1 FROM silver.cad_aproximacao c
                WHERE c.des = a.des)             AS em_cad,
        (n.des IS NOT NULL)                      AS em_neows
    FROM silver.asteroide a
    LEFT JOIN silver.sentry_resumo   s ON s.des = a.des
    LEFT JOIN silver.neows_asteroide n ON n.des = a.des
)
INSERT INTO gold.dim_asteroide (
    des, fullname, neows_id, nome_neows, id_sentry,
    h_mag, diametro_km_min, diametro_km_max, diametro_sentry, is_pha,
    ip, ps_cum, ps_max, ts_max, n_imp, ano_min, ano_max,
    em_sentry, em_sentry_removido, tem_impacto_virtual, em_cad, em_neows,
    qtd_fontes
)
SELECT
    des, fullname, neows_id, nome_neows, id_sentry,
    h_mag, diametro_km_min, diametro_km_max, diametro_sentry, is_pha,
    ip, ps_cum, ps_max, ts_max, n_imp, ano_min, ano_max,
    em_sentry, em_sentry_removido, tem_impacto_virtual, em_cad, em_neows,
    -- qtd_fontes = em quantas APIs o objeto aparece (Sentry, CAD, NeoWs): de 1 a 3
    ((em_sentry OR em_sentry_removido OR tem_impacto_virtual)::int
     + em_cad::int + em_neows::int)::smallint
FROM base
ORDER BY des            -- ordem fixa: a primeira carga sempre gera as mesmas SKs
ON CONFLICT (des) DO UPDATE SET
    fullname            = EXCLUDED.fullname,
    neows_id            = EXCLUDED.neows_id,
    nome_neows          = EXCLUDED.nome_neows,
    id_sentry           = EXCLUDED.id_sentry,
    h_mag               = EXCLUDED.h_mag,
    diametro_km_min     = EXCLUDED.diametro_km_min,
    diametro_km_max     = EXCLUDED.diametro_km_max,
    diametro_sentry     = EXCLUDED.diametro_sentry,
    is_pha              = EXCLUDED.is_pha,
    ip                  = EXCLUDED.ip,
    ps_cum              = EXCLUDED.ps_cum,
    ps_max              = EXCLUDED.ps_max,
    ts_max              = EXCLUDED.ts_max,
    n_imp               = EXCLUDED.n_imp,
    ano_min             = EXCLUDED.ano_min,
    ano_max             = EXCLUDED.ano_max,
    em_sentry           = EXCLUDED.em_sentry,
    em_sentry_removido  = EXCLUDED.em_sentry_removido,
    tem_impacto_virtual = EXCLUDED.tem_impacto_virtual,
    em_cad              = EXCLUDED.em_cad,
    em_neows            = EXCLUDED.em_neows,
    qtd_fontes          = EXCLUDED.qtd_fontes,
    carregado_em        = now();
"""

# Todo objeto da silver.asteroide precisa estar na dimensão
SQL_FALTANDO = """
SELECT COUNT(*)
FROM silver.asteroide a
LEFT JOIN gold.dim_asteroide d ON d.des = a.des
WHERE d.des IS NULL;
"""


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_UPSERT)
            print(f"dim_asteroide: {cur.rowcount} linhas inseridas/atualizadas")

            cur.execute(SQL_FALTANDO)
            faltando = cur.fetchone()[0]
            # se der erro aqui, nada é gravado (a transação é desfeita)
            assert faltando == 0, f"{faltando} objetos da silver ficaram fora da dimensão"


if __name__ == "__main__":
    main()
