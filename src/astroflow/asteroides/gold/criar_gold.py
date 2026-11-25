# src/astroflow/gold/criar_gold.py
# Cria o schema gold: 1 dimensão + 3 fatos (CREATE IF NOT EXISTS: pode rodar várias vezes).
# Ordem importa: a dimensão vem primeiro, porque as fatos referenciam ela.
from astroflow.config import get_connection

DDL = """
CREATE SCHEMA IF NOT EXISTS gold;

-- ============ DIMENSÃO ============
CREATE TABLE IF NOT EXISTS gold.dim_asteroide (
    asteroide_sk        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    des                 TEXT NOT NULL UNIQUE,

    fullname            TEXT,
    neows_id            TEXT,
    nome_neows          TEXT,
    id_sentry           TEXT,

    h_mag               DOUBLE PRECISION,
    diametro_km_min     DOUBLE PRECISION,
    diametro_km_max     DOUBLE PRECISION,
    diametro_sentry     DOUBLE PRECISION,
    is_pha              BOOLEAN,

    ip                  DOUBLE PRECISION,
    ps_cum              DOUBLE PRECISION,
    ps_max              DOUBLE PRECISION,
    ts_max              SMALLINT,
    n_imp               INTEGER,
    ano_min             INTEGER,
    ano_max             INTEGER,

    em_sentry           BOOLEAN NOT NULL,
    em_sentry_removido  BOOLEAN NOT NULL,
    tem_impacto_virtual BOOLEAN NOT NULL,
    em_cad              BOOLEAN NOT NULL,
    em_neows            BOOLEAN NOT NULL,
    qtd_fontes          SMALLINT NOT NULL,

    carregado_em        TIMESTAMP NOT NULL DEFAULT now()
);

-- ============ FATO 1: aproximações do CAD ============
CREATE TABLE IF NOT EXISTS gold.fact_aprox_cad (
    aprox_cad_sk    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asteroide_sk    BIGINT NOT NULL REFERENCES gold.dim_asteroide (asteroide_sk),

    data_hora       TIMESTAMP,            -- vem do cd da silver
    jd              DOUBLE PRECISION,
    orbit_id        INTEGER,
    dist            DOUBLE PRECISION,
    dist_min        DOUBLE PRECISION,
    dist_max        DOUBLE PRECISION,
    v_rel           DOUBLE PRECISION,
    v_inf           DOUBLE PRECISION,
    t_sigma_f       TEXT,
    h               DOUBLE PRECISION,
    diameter        DOUBLE PRECISION,
    diameter_sigma  DOUBLE PRECISION,

    bronze_id       BIGINT,
    carregado_em    TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fact_aprox_cad_ast ON gold.fact_aprox_cad (asteroide_sk);

-- ============ FATO 2: aproximações da NeoWs ============
CREATE TABLE IF NOT EXISTS gold.fact_aprox_neows (
    aprox_neows_sk    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asteroide_sk      BIGINT NOT NULL REFERENCES gold.dim_asteroide (asteroide_sk),

    corpo             TEXT,
    data_aproximacao  DATE,
    data_hora         TIMESTAMP,
    epoch_ms          BIGINT,
    dist_km           DOUBLE PRECISION,
    dist_au           DOUBLE PRECISION,
    dist_lunar        DOUBLE PRECISION,
    v_rel_km_s        DOUBLE PRECISION,

    bronze_id         BIGINT,
    carregado_em      TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fact_aprox_neows_ast ON gold.fact_aprox_neows (asteroide_sk);

-- ============ FATO 3: impactos virtuais do Sentry ============
CREATE TABLE IF NOT EXISTS gold.fact_impacto_virtual (
    impacto_virtual_sk  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asteroide_sk        BIGINT NOT NULL REFERENCES gold.dim_asteroide (asteroide_sk),

    posicao             INTEGER,
    data_impacto        DATE,
    ip                  DOUBLE PRECISION,
    ps                  DOUBLE PRECISION,
    ts                  SMALLINT,
    energy              DOUBLE PRECISION,
    metodo              TEXT,
    sigma_vi            DOUBLE PRECISION,
    sigma_mc            DOUBLE PRECISION,

    bronze_id           BIGINT,
    carregado_em        TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fact_impacto_virtual_ast ON gold.fact_impacto_virtual (asteroide_sk);
"""


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
    print("gold criada: dim_asteroide + 3 fatos (ou já existiam).")


if __name__ == "__main__":
    main()
