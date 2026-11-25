# Carga da silver.sentry_resumo (Sentry modo S).
# Lê o ÚLTIMO snapshot de 'sentry_resumo' na bronze, limpa e grava na silver.

from astroflow.config import get_connection
from astroflow.comum.conversores import para_data, para_float, para_int

# Chaves que esperamos em cada item do array "data"
CHAVES_ESPERADAS = {
    "id",
    "des",
    "fullname",
    "h",
    "diameter",
    "ip",
    "n_imp",
    "ps_cum",
    "ps_max",
    "ts_max",
    "v_inf",
    "last_obs",
    "last_obs_jd",
    "range",
}


def separar_range(valor):
    """'2064-2118' -> (2064, 2118). Se vier um ano só, min = max."""
    if valor is None or str(valor).strip() == "":
        return None, None
    partes = str(valor).split("-")
    return int(partes[0]), int(partes[-1])


def carregar_silver_sentry_resumo() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Pega o último snapshot do modo S
            cur.execute(
                """
                SELECT id, payload->'data'
                FROM bronze.sentry_raw
                WHERE source = 'sentry_resumo'
                ORDER BY id DESC LIMIT 1
                """
            )
            bronze_id, itens = cur.fetchone()  # itens já vem como lista Python

            # 2) Confere as chaves do JSON
            assert CHAVES_ESPERADAS <= set(
                itens[0].keys()
            ), f"Chaves diferentes do esperado: {set(itens[0].keys())}"

            # 3) Limpa e converte cada item
            linhas = []
            for it in itens:
                ano_min, ano_max = separar_range(it["range"])
                linhas.append(
                    (
                        it["des"],
                        it["id"],
                        para_float(it["h"]),
                        para_float(it["diameter"]),
                        para_float(it["ip"]),
                        para_int(it["n_imp"]),
                        para_float(it["ps_cum"]),
                        para_float(it["ps_max"]),
                        para_int(it["ts_max"]),
                        para_float(it["v_inf"]),
                        para_data(it["last_obs"]),
                        para_float(it["last_obs_jd"]),
                        ano_min,
                        ano_max,
                        bronze_id,
                    )
                )

            # 4) Regra do projeto: a conversão não pode criar nulos.
            #    Nulos antes = None ou 'NaN'; depois = None. Têm que ser iguais.
            for nome, pos in [("v_inf", 9), ("ts_max", 8)]:
                antes = sum(1 for it in itens if it[nome] in (None, "NaN"))
                depois = sum(1 for l in linhas if l[pos] is None)
                assert antes == depois, f"{nome}: nulos antes={antes}, depois={depois}"

            cur.execute("TRUNCATE silver.sentry_resumo")

            # 5) Grava (rodar de novo não duplica)
            cur.executemany(
                """
                INSERT INTO silver.sentry_resumo (
                    des, id_sentry, h, diameter, ip, n_imp, ps_cum, ps_max,
                    ts_max, v_inf, last_obs, last_obs_jd, ano_min, ano_max,
                    bronze_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (des) DO NOTHING
                """,
                linhas,
            )
            print(f"Itens lidos da bronze: {len(itens)} | bronze_id: {bronze_id}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_sentry_resumo()
