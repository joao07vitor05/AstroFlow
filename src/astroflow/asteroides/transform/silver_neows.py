# Carga das tabelas silver da NeoWs (fonte: bronze.neows_lookup_raw).
# Por enquanto só neows_asteroide; neows_orbita e neows_aproximacao entram depois.
from datetime import datetime

from astroflow.config import get_connection
from astroflow.comum.conversores import (
    para_data,
    para_datahora,
    para_float,
    para_int,
)

# Chaves que cada payload do lookup precisa ter
CHAVES_ESPERADAS = {
    "id",
    "designation",
    "name",
    "neo_reference_id",
    "nasa_jpl_url",
    "absolute_magnitude_h",
    "estimated_diameter",
    "is_potentially_hazardous_asteroid",
    "is_sentry_object",
}

# Colunas da silver na ordem do INSERT (menos bronze_id)
COLUNAS_ASTEROIDE = [
    "neows_id",
    "des",
    "name",
    "neo_reference_id",
    "nasa_jpl_url",
    "absolute_magnitude_h",
    "is_pha",
    "is_sentry_object",
    "diameter_km_min",
    "diameter_km_max",
]


def extrair_bruto(p: dict) -> dict:
    """Pega do payload os valores crus, com os nomes das colunas da silver."""
    km = p["estimated_diameter"]["kilometers"]  # só km (as outras unidades são redundantes)
    return {
        "neows_id": p["id"],
        "des": p["designation"],
        "name": p["name"],
        "neo_reference_id": p["neo_reference_id"],
        "nasa_jpl_url": p["nasa_jpl_url"],
        "absolute_magnitude_h": p["absolute_magnitude_h"],
        "is_pha": p["is_potentially_hazardous_asteroid"],
        "is_sentry_object": p["is_sentry_object"],
        "diameter_km_min": km["estimated_diameter_min"],
        "diameter_km_max": km["estimated_diameter_max"],
    }


def limpar_asteroide(b: dict) -> dict:
    """Converte os tipos (os campos de texto ficam como estão)."""
    l = dict(b)
    for col in ("absolute_magnitude_h", "diameter_km_min", "diameter_km_max"):
        l[col] = para_float(b[col])
    return l


def ler_lookup(cur):
    """Uma linha por asteroide (a mais recente de cada id): [(bronze_id, payload), ...]"""
    cur.execute(
        """
        SELECT DISTINCT ON (payload->>'id') id, payload
        FROM bronze.neows_lookup_raw
        ORDER BY payload->>'id', id DESC
        """
    )
    return cur.fetchall()


def carregar_neows_asteroide(cur) -> None:
    # 1) Uma linha por asteroide (a mais recente de cada id)
    registros = ler_lookup(cur)

    # 2) Confere as chaves do JSON em todos os payloads
    for _, p in registros:
        faltando = CHAVES_ESPERADAS - set(p.keys())
        assert not faltando, f"Chaves faltando no asteroide {p.get('id')}: {faltando}"

    # 3) Extrai e limpa
    brutos = [(bid, extrair_bruto(p)) for bid, p in registros]
    limpos = [(bid, limpar_asteroide(b)) for bid, b in brutos]

    # 4) Obrigatórios e tipo dos booleanos
    assert all(l["neows_id"] and l["des"] for _, l in limpos), "neows_id/des nulo"
    for col in ("is_pha", "is_sentry_object"):
        assert all(
            isinstance(l[col], bool) or l[col] is None for _, l in limpos
        ), f"{col}: valor que não é booleano"

    # 5) Regra do projeto: a conversão não pode criar nulos
    for col in COLUNAS_ASTEROIDE:
        antes = sum(1 for _, b in brutos if b[col] in (None, "", "NaN"))
        depois = sum(1 for _, l in limpos if l[col] is None)
        assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

    # 6) Grava: se o asteroide já existe, atualiza as colunas
    linhas = [tuple(l[c] for c in COLUNAS_ASTEROIDE) + (bid,) for bid, l in limpos]
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS_ASTEROIDE[1:] + ["bronze_id"])
    cur.executemany(
        f"""
        INSERT INTO silver.neows_asteroide (
            neows_id, des, name, neo_reference_id, nasa_jpl_url,
            absolute_magnitude_h, is_pha, is_sentry_object,
            diameter_km_min, diameter_km_max, bronze_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (neows_id) DO UPDATE SET {sets}
        """,
        linhas,
    )
    print(f"neows_asteroide: {len(registros)} asteroides lidos da bronze")


# ---------------------- neows_orbita ----------------------

# Colunas que são chaves diretas de orbital_data
ORBITA_TEXTO = ["orbit_id", "orbit_uncertainty", "equinox"]
ORBITA_INT = ["data_arc_in_days", "observations_used"]
ORBITA_FLOAT = [
    "minimum_orbit_intersection",
    "jupiter_tisserand_invariant",
    "epoch_osculation",
    "eccentricity",
    "semi_major_axis",
    "inclination",
    "ascending_node_longitude",
    "orbital_period",
    "perihelion_distance",
    "perihelion_argument",
    "aphelion_distance",
    "perihelion_time",
    "mean_anomaly",
    "mean_motion",
]
ORBITA_DATAS = ["first_observation_date", "last_observation_date"]
ORBITA_DIRETAS = (
    ORBITA_TEXTO + ORBITA_INT + ORBITA_FLOAT + ORBITA_DATAS + ["orbit_determination_date"]
)
# Estas vêm de orbital_data -> orbit_class
ORBITA_CLASSE = ["orbit_class_type", "orbit_class_range", "orbit_class_description"]

# Ordem das colunas no INSERT (menos neows_id e bronze_id)
COLUNAS_ORBITA = ORBITA_DIRETAS + ORBITA_CLASSE


def extrair_bruto_orbita(p: dict) -> dict:
    """Valores crus de orbital_data, com os nomes das colunas da silver."""
    od = p["orbital_data"]
    oc = od["orbit_class"]
    bruto = {col: od[col] for col in ORBITA_DIRETAS}
    for col in ORBITA_CLASSE:
        bruto[col] = oc[col]  # as chaves de orbit_class têm o mesmo nome da coluna
    return bruto


def limpar_orbita(b: dict) -> dict:
    """Converte os tipos (texto fica como está)."""
    l = dict(b)
    for col in ORBITA_INT:
        l[col] = para_int(b[col])
    for col in ORBITA_FLOAT:
        l[col] = para_float(b[col])
    for col in ORBITA_DATAS:
        l[col] = para_data(b[col])
    l["orbit_determination_date"] = para_datahora(b["orbit_determination_date"])
    return l


def carregar_neows_orbita(cur) -> None:
    registros = ler_lookup(cur)

    # 1) Confere as chaves do JSON em todos os payloads
    for _, p in registros:
        assert "orbital_data" in p, f"Sem orbital_data no asteroide {p.get('id')}"
        od = p["orbital_data"]
        faltando = set(ORBITA_DIRETAS) - set(od.keys())
        assert not faltando, f"Chaves faltando em orbital_data ({p['id']}): {faltando}"
        assert "orbit_class" in od, f"Sem orbit_class no asteroide {p['id']}"
        faltando = set(ORBITA_CLASSE) - set(od["orbit_class"].keys())
        assert not faltando, f"Chaves faltando em orbit_class ({p['id']}): {faltando}"

    # 2) Extrai e limpa (guarda o neows_id e o bronze_id de cada linha)
    brutos = [(bid, p["id"], extrair_bruto_orbita(p)) for bid, p in registros]
    limpos = [(bid, nid, limpar_orbita(b)) for bid, nid, b in brutos]

    # 3) Regra do projeto: a conversão não pode criar nulos
    for col in COLUNAS_ORBITA:
        antes = sum(1 for _, _, b in brutos if b[col] in (None, "", "NaN"))
        depois = sum(1 for _, _, l in limpos if l[col] is None)
        assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

    # 4) Grava: se a órbita já existe, atualiza as colunas
    linhas = [(nid, *[l[c] for c in COLUNAS_ORBITA], bid) for bid, nid, l in limpos]
    colunas_sql = ", ".join(["neows_id"] + COLUNAS_ORBITA + ["bronze_id"])
    placeholders = ", ".join(["%s"] * (len(COLUNAS_ORBITA) + 2))
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS_ORBITA + ["bronze_id"])
    cur.executemany(
        f"""
        INSERT INTO silver.neows_orbita ({colunas_sql})
        VALUES ({placeholders})
        ON CONFLICT (neows_id) DO UPDATE SET {sets}
        """,
        linhas,
    )
    print(f"neows_orbita: {len(registros)} órbitas lidas da bronze")


# -------------------- neows_aproximacao --------------------

# Chaves que cada item de close_approach_data precisa ter
APROX_CHAVES = {
    "close_approach_date",
    "epoch_date_close_approach",
    "orbiting_body",
    "miss_distance",
    "relative_velocity",
}

# Ordem das colunas no INSERT (menos neows_id e bronze_id)
COLUNAS_APROX = [
    "corpo",
    "data_aproximacao",
    "data_hora",
    "epoch_ms",
    "dist_km",
    "dist_au",
    "dist_lunar",
    "v_rel_km_s",
]


def para_data_hora_neows(valor):
    """'1900-Dec-27 01:30' -> datetime. O mês vem abreviado em inglês."""
    if valor is None or str(valor).strip() == "":
        return None
    return datetime.strptime(valor, "%Y-%b-%d %H:%M")


def extrair_bruto_aprox(a: dict) -> dict:
    """Valores crus de uma aproximação, com os nomes das colunas da silver."""
    return {
        "corpo": a["orbiting_body"],
        "data_aproximacao": a["close_approach_date"],
        "data_hora": a.get("close_approach_date_full"),  # pode faltar
        "epoch_ms": a["epoch_date_close_approach"],
        "dist_km": a["miss_distance"]["kilometers"],
        "dist_au": a["miss_distance"]["astronomical"],
        "dist_lunar": a["miss_distance"]["lunar"],
        "v_rel_km_s": a["relative_velocity"]["kilometers_per_second"],
    }


def limpar_aprox(b: dict) -> dict:
    """Converte os tipos (corpo fica texto)."""
    l = dict(b)
    l["data_aproximacao"] = para_data(b["data_aproximacao"])
    l["data_hora"] = para_data_hora_neows(b["data_hora"])
    l["epoch_ms"] = para_int(b["epoch_ms"])
    for col in ("dist_km", "dist_au", "dist_lunar", "v_rel_km_s"):
        l[col] = para_float(b[col])
    return l


def carregar_neows_aproximacao(cur) -> None:
    registros = ler_lookup(cur)

    # 1) Junta as aproximações de todos os asteroides: (bronze_id, neows_id, bruto)
    brutos = []
    for bid, p in registros:
        assert "close_approach_data" in p, f"Sem close_approach_data em {p.get('id')}"
        for a in p["close_approach_data"]:
            faltando = APROX_CHAVES - set(a.keys())
            assert not faltando, f"Chaves faltando em {p['id']}: {faltando}"
            brutos.append((bid, p["id"], extrair_bruto_aprox(a)))

    # 2) Limpa
    limpos = [(bid, nid, limpar_aprox(b)) for bid, nid, b in brutos]

    # 3) Obrigatórios: corpo e epoch_ms (epoch_ms faz parte da chave única)
    assert all(
        l["corpo"] and l["epoch_ms"] is not None for _, _, l in limpos
    ), "Aproximação sem corpo ou sem epoch_ms"

    # 4) A chave única não pode ter repetição (senão o ON CONFLICT esconderia linhas)
    chaves = {(nid, l["corpo"], l["epoch_ms"]) for _, nid, l in limpos}
    assert len(chaves) == len(
        limpos
    ), f"Há {len(limpos) - len(chaves)} aproximações repetidas por (neows_id, corpo, epoch_ms)"

    # 5) Regra do projeto: a conversão não pode criar nulos
    for col in COLUNAS_APROX:
        antes = sum(1 for _, _, b in brutos if b[col] in (None, "", "NaN"))
        depois = sum(1 for _, _, l in limpos if l[col] is None)
        assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

    # 6) Grava: se a aproximação já existe, atualiza as colunas
    linhas = [(nid, *[l[c] for c in COLUNAS_APROX], bid) for bid, nid, l in limpos]
    sets = (
        ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS_APROX if c not in ("corpo", "epoch_ms"))
        + ", bronze_id = EXCLUDED.bronze_id"
    )
    cur.executemany(
        f"""
        INSERT INTO silver.neows_aproximacao (
            neows_id, corpo, data_aproximacao, data_hora, epoch_ms,
            dist_km, dist_au, dist_lunar, v_rel_km_s, bronze_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (neows_id, corpo, epoch_ms) DO UPDATE SET {sets}
        """,
        linhas,
    )
    print(f"neows_aproximacao: {len(limpos)} aproximações lidas da bronze")


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            carregar_neows_asteroide(cur)  # primeiro: as outras referenciam esta tabela
            carregar_neows_orbita(cur)
            carregar_neows_aproximacao(cur)
        conn.commit()


if __name__ == "__main__":
    main()
