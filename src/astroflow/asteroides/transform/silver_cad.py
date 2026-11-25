# Carga da silver.cad_aproximacao (JPL CAD).
# Lê o ÚLTIMO snapshot de 'cad_terra' na bronze (só um, para não duplicar).
from datetime import datetime

from astroflow.config import get_connection
from astroflow.comum.conversores import para_float, para_int

# Campos do JSON que vão para a silver (fullname é ignorado)
CAMPOS_ESPERADOS = {
    "des",
    "orbit_id",
    "jd",
    "cd",
    "dist",
    "dist_min",
    "dist_max",
    "v_rel",
    "v_inf",
    "t_sigma_f",
    "h",
    "diameter",
    "diameter_sigma",
}

# Colunas da silver na ordem do INSERT (menos bronze_id)
COLUNAS = [
    "des",
    "orbit_id",
    "jd",
    "cd",
    "dist",
    "dist_min",
    "dist_max",
    "v_rel",
    "v_inf",
    "t_sigma_f",
    "h",
    "diameter",
    "diameter_sigma",
]


def para_cd(valor):
    """'2026-Nov-18 12:34' -> datetime (TDB). O mês vem abreviado em inglês."""
    if valor is None or str(valor).strip() == "":
        return None
    return datetime.strptime(valor, "%Y-%b-%d %H:%M")


def limpar(r: dict) -> dict:
    """Converte uma aproximação (dict campo -> texto) para os tipos da silver."""
    return {
        "des": r["des"],
        "orbit_id": para_int(r["orbit_id"]),
        "jd": para_float(r["jd"]),
        "cd": para_cd(r["cd"]),
        "dist": para_float(r["dist"]),
        "dist_min": para_float(r["dist_min"]),
        "dist_max": para_float(r["dist_max"]),
        "v_rel": para_float(r["v_rel"]),
        "v_inf": para_float(r["v_inf"]),
        "t_sigma_f": r["t_sigma_f"],  # fica texto (ex.: '< 00:01')
        "h": para_float(r["h"]),
        "diameter": para_float(r["diameter"]),  # None se desconhecido
        "diameter_sigma": para_float(r["diameter_sigma"]),
    }


def carregar_silver_cad() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Último snapshot do CAD
            cur.execute(
                """
                SELECT id, payload->'fields', payload->'data'
                FROM bronze.cad_raw
                WHERE source = 'cad_terra'
                ORDER BY id DESC LIMIT 1
                """
            )
            bronze_id, campos, dados = cur.fetchone()

            # 2) Confere os campos do JSON
            assert CAMPOS_ESPERADOS <= set(campos), f"Campos diferentes do esperado: {campos}"

            # 3) Cada linha vira um dict {campo: valor} e é limpa
            brutos = [dict(zip(campos, linha, strict=False)) for linha in dados]
            limpos = [limpar(r) for r in brutos]

            # 4) des e jd são obrigatórios
            assert all(
                l["des"] and l["jd"] is not None for l in limpos
            ), "Há aproximação sem des ou sem jd"

            # 5) Regra do projeto: a conversão não pode criar nulos
            for col in COLUNAS:
                antes = sum(1 for r in brutos if r[col] in (None, "", "NaN"))
                depois = sum(1 for l in limpos if l[col] is None)
                assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

            # 6) Grava (rodar de novo no mesmo snapshot não duplica)
            linhas = [tuple(l[c] for c in COLUNAS) + (bronze_id,) for l in limpos]

            cur.execute("TRUNCATE silver.cad_aproximacao RESTART IDENTITY")

            cur.executemany(
                """
                INSERT INTO silver.cad_aproximacao (
                    des, orbit_id, jd, cd, dist, dist_min, dist_max,
                    v_rel, v_inf, t_sigma_f, h, diameter, diameter_sigma,
                    bronze_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bronze_id, des, jd) DO NOTHING
                """,
                linhas,
            )
            print(f"Aproximações lidas da bronze: {len(dados)} | bronze_id: {bronze_id}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_cad()
