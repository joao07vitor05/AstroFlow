# Carga da silver.sentry_detalhe (Sentry modo O).
# Pega, para cada objeto, o snapshot mais recente de 'sentry_objeto' na bronze
# e guarda só os 12 campos do summary que NÃO existem no resumo (modo S).
from astroflow.config import get_connection
from astroflow.transform.conversores import (
    para_data, para_datahora, para_float, para_int,
)

# Colunas da silver na ordem do INSERT (menos des e bronze_id)
COLUNAS = [
    "metodo", "first_obs", "darc_dias", "nobs", "ndel", "ndop",
    "nsat", "mass", "energy", "v_imp", "cdate", "pdate",
]


def para_darc(valor):
    """'469.18 days' -> 469.18"""
    if valor is None or str(valor).strip() == "":
        return None
    return float(valor.split(" ")[0])


def limpar(summary: dict) -> dict:
    """Converte os campos de um summary para os tipos da silver."""
    return {
        "metodo":    summary.get("method"),
        "first_obs": para_data(summary.get("first_obs")),
        "darc_dias": para_darc(summary.get("darc")),
        "nobs":      para_int(summary.get("nobs")),
        "ndel":      para_int(summary.get("ndel")),
        "ndop":      para_int(summary.get("ndop")),
        "nsat":      para_int(summary.get("nsat")),   # vem como texto
        "mass":      para_float(summary.get("mass")),
        "energy":    para_float(summary.get("energy")),
        "v_imp":     para_float(summary.get("v_imp")),
        "cdate":     para_datahora(summary.get("cdate")),
        "pdate":     para_datahora(summary.get("pdate")),
    }


# Nome da chave no JSON para cada coluna (para a checagem de nulos)
CHAVE_JSON = {
    "metodo": "method", "first_obs": "first_obs", "darc_dias": "darc",
    "nobs": "nobs", "ndel": "ndel", "ndop": "ndop", "nsat": "nsat",
    "mass": "mass", "energy": "energy", "v_imp": "v_imp",
    "cdate": "cdate", "pdate": "pdate",
}


def carregar_silver_sentry_detalhe() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Último snapshot de cada objeto (a bronze guarda um por execução)
            cur.execute(
                """
                SELECT DISTINCT ON (query_params->>'des')
                       id, payload->'summary'
                FROM bronze.sentry_raw
                WHERE source = 'sentry_objeto'
                ORDER BY query_params->>'des', id DESC
                """
            )
            registros = cur.fetchall()

            # 2) Ignora objetos sem summary (ex.: resposta "object not found")
            validos = [(bid, s) for bid, s in registros if s]
            print(f"Objetos na bronze: {len(registros)} | com summary: {len(validos)}")

            # 3) Limpa cada summary
            limpos = [(bid, s, limpar(s)) for bid, s in validos]

            # 4) Regra do projeto: a conversão não pode criar nulos
            for col in COLUNAS:
                chave = CHAVE_JSON[col]
                antes = sum(1 for _, s, _ in limpos if s.get(chave) in (None, "", "NaN"))
                depois = sum(1 for _, _, l in limpos if l[col] is None)
                assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

            # 5) Grava (rodar de novo não duplica)
            linhas = [
                (s["des"], *[l[c] for c in COLUNAS], bid)
                for bid, s, l in limpos
            ]
            cur.executemany(
                """
                INSERT INTO silver.sentry_detalhe (
                    des, metodo, first_obs, darc_dias, nobs, ndel, ndop,
                    nsat, mass, energy, v_imp, cdate, pdate, bronze_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (des) DO NOTHING
                """,
                linhas,
            )
            print(f"Linhas enviadas para silver.sentry_detalhe: {len(linhas)}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_sentry_detalhe()