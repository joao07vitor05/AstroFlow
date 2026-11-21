from dotenv import load_dotenv

from astroflow.config import get_connection

load_dotenv()


DDL = """
CREATE SCHEMA IF NOT EXISTS silver;

-- Dimensão central: um registro por objeto (des vem de CAD, Sentry e NeoWs)
CREATE TABLE IF NOT EXISTS silver.asteroide (
    des        TEXT PRIMARY KEY,
    fullname   TEXT                      -- pode ser nulo (os removidos não trazem nome)
);

-- ===================== SENTRY =====================

-- Modo S: um registro por objeto atual da Sentry
CREATE TABLE IF NOT EXISTS silver.sentry_resumo (
    des          TEXT PRIMARY KEY REFERENCES silver.asteroide (des),
    id_sentry    TEXT        NOT NULL,
    h            DOUBLE PRECISION,
    diameter     DOUBLE PRECISION,
    ip           DOUBLE PRECISION NOT NULL,
    n_imp        INTEGER     NOT NULL,
    ps_cum       DOUBLE PRECISION,
    ps_max       DOUBLE PRECISION,
    ts_max       SMALLINT,               -- nulo quando o JPL não informa (não vira 0)
    v_inf        DOUBLE PRECISION,       -- nulo quando a API manda 'NaN'
    last_obs     DATE,
    last_obs_jd  DOUBLE PRECISION,
    ano_min      INTEGER,
    ano_max      INTEGER,
    bronze_id    BIGINT      NOT NULL REFERENCES bronze.sentry_raw (id)
);

-- Modo O: campos do summary que NÃO existem no resumo (modo S)
CREATE TABLE IF NOT EXISTS silver.sentry_detalhe (
    des         TEXT PRIMARY KEY REFERENCES silver.asteroide (des),
    metodo      TEXT,
    first_obs   DATE,
    darc_dias   DOUBLE PRECISION,        -- vem como '469.18 days'
    nobs        INTEGER,
    ndel        INTEGER,
    ndop        INTEGER,
    nsat        INTEGER,                 -- vem como texto
    mass        DOUBLE PRECISION,
    energy      DOUBLE PRECISION,
    v_imp       DOUBLE PRECISION,
    cdate       TIMESTAMP,
    pdate       TIMESTAMP,
    bronze_id   BIGINT      NOT NULL REFERENCES bronze.sentry_raw (id)
);

-- Modo V: um registro por cenário de impacto (sem chave natural)
CREATE TABLE IF NOT EXISTS silver.sentry_impacto_virtual (
    id            BIGSERIAL PRIMARY KEY,
    des           TEXT        NOT NULL REFERENCES silver.asteroide (des),
    posicao       INTEGER     NOT NULL,  -- posição do registro dentro do array "data"
    data_impacto  DATE,
    ip            DOUBLE PRECISION,
    ps            DOUBLE PRECISION,
    ts            SMALLINT,
    energy        DOUBLE PRECISION,
    metodo        TEXT,
    sigma_vi      DOUBLE PRECISION,      -- só nos registros IOBS
    sigma_mc      DOUBLE PRECISION,      -- só nos registros MC
    bronze_id     BIGINT      NOT NULL REFERENCES bronze.sentry_raw (id),
    UNIQUE (bronze_id, posicao)          -- chave artificial: snapshot + posição
);

-- Modo R: objetos removidos da Sentry
CREATE TABLE IF NOT EXISTS silver.sentry_removido (
    des          TEXT PRIMARY KEY REFERENCES silver.asteroide (des),
    removido_em  TIMESTAMP   NOT NULL,   -- em UTC
    bronze_id    BIGINT      NOT NULL REFERENCES bronze.sentry_raw (id)
);

-- ======================== CAD ========================

CREATE TABLE IF NOT EXISTS silver.cad_aproximacao (
    id              BIGSERIAL PRIMARY KEY,
    des             TEXT        NOT NULL REFERENCES silver.asteroide (des),
    orbit_id        INTEGER,
    jd              DOUBLE PRECISION NOT NULL,
    cd              TIMESTAMP,
    dist            DOUBLE PRECISION,
    dist_min        DOUBLE PRECISION,
    dist_max        DOUBLE PRECISION,
    v_rel           DOUBLE PRECISION,
    v_inf           DOUBLE PRECISION,
    t_sigma_f       TEXT,                -- texto como vem (ex.: '< 00:01')
    h               DOUBLE PRECISION,
    diameter        DOUBLE PRECISION,    -- nulo quando desconhecido
    diameter_sigma  DOUBLE PRECISION,
    bronze_id       BIGINT      NOT NULL REFERENCES bronze.cad_raw (id),
    UNIQUE (bronze_id, des, jd)
);

-- ======================= NEOWS =======================
-- Fonte: lookup (o feed é subconjunto do histórico do lookup)

CREATE TABLE IF NOT EXISTS silver.neows_asteroide (
    neows_id           TEXT PRIMARY KEY,
    des                TEXT        NOT NULL UNIQUE REFERENCES silver.asteroide (des),
    name               TEXT,
    neo_reference_id   TEXT,
    nasa_jpl_url       TEXT,
    absolute_magnitude_h  DOUBLE PRECISION,
    is_pha             BOOLEAN,          -- is_potentially_hazardous_asteroid
    is_sentry_object   BOOLEAN,
    diameter_km_min    DOUBLE PRECISION, -- só km (as outras unidades são redundantes)
    diameter_km_max    DOUBLE PRECISION,
    bronze_id          BIGINT      NOT NULL REFERENCES bronze.neows_lookup_raw (id)
);

CREATE TABLE IF NOT EXISTS silver.neows_orbita (
    neows_id                  TEXT PRIMARY KEY REFERENCES silver.neows_asteroide (neows_id),
    orbit_id                  TEXT,
    orbit_determination_date  TIMESTAMP,
    first_observation_date    DATE,
    last_observation_date     DATE,
    data_arc_in_days          INTEGER,
    observations_used         INTEGER,
    orbit_uncertainty         TEXT,
    minimum_orbit_intersection  DOUBLE PRECISION,
    jupiter_tisserand_invariant DOUBLE PRECISION,
    epoch_osculation          DOUBLE PRECISION,
    eccentricity              DOUBLE PRECISION,
    semi_major_axis           DOUBLE PRECISION,
    inclination               DOUBLE PRECISION,
    ascending_node_longitude  DOUBLE PRECISION,
    orbital_period            DOUBLE PRECISION,
    perihelion_distance       DOUBLE PRECISION,
    perihelion_argument       DOUBLE PRECISION,
    aphelion_distance         DOUBLE PRECISION,
    perihelion_time           DOUBLE PRECISION,
    mean_anomaly              DOUBLE PRECISION,
    mean_motion               DOUBLE PRECISION,
    equinox                   TEXT,
    orbit_class_type          TEXT,
    orbit_class_range         TEXT,
    orbit_class_description   TEXT,
    bronze_id                 BIGINT NOT NULL REFERENCES bronze.neows_lookup_raw (id)
);

CREATE TABLE IF NOT EXISTS silver.neows_aproximacao (
    id               BIGSERIAL PRIMARY KEY,
    neows_id         TEXT        NOT NULL REFERENCES silver.neows_asteroide (neows_id),
    corpo            TEXT        NOT NULL,   -- orbiting_body (Earth, Venus...)
    data_aproximacao DATE,
    data_hora        TIMESTAMP,              -- close_approach_date_full
    epoch_ms         BIGINT      NOT NULL,   -- epoch_date_close_approach
    dist_km          DOUBLE PRECISION,
    dist_au          DOUBLE PRECISION,
    dist_lunar       DOUBLE PRECISION,
    v_rel_km_s       DOUBLE PRECISION,
    bronze_id        BIGINT      NOT NULL REFERENCES bronze.neows_lookup_raw (id),
    UNIQUE (neows_id, corpo, epoch_ms)
);

CREATE INDEX IF NOT EXISTS ix_sentry_impacto_virtual_des ON silver.sentry_impacto_virtual (des);
CREATE INDEX IF NOT EXISTS ix_cad_aproximacao_des        ON silver.cad_aproximacao (des);
CREATE INDEX IF NOT EXISTS ix_cad_aproximacao_cd         ON silver.cad_aproximacao (cd);
CREATE INDEX IF NOT EXISTS ix_neows_aproximacao_data
 ON silver.neows_aproximacao (data_aproximacao);
"""


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Schema silver criado.")


if __name__ == "__main__":
    main()
