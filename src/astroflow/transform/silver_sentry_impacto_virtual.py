# Carga da silver.sentry_impacto_virtual (Sentry modo V).
# Lê o ÚLTIMO snapshot de 'sentry_vi' na bronze (só um, para não duplicar).
from astroflow.config import get_connection
from astroflow.transform.conversores import para_data, para_float, para_int

# Chaves que todo registro deve ter (sigma_vi e sigma_mc dependem do método)
CHAVES_ESPERADAS = {"des", "date", "ip", "ps", "ts", "energy", "method"}

# Coluna da silver -> chave no JSON (para a checagem de nulos)
CHAVE_JSON = {
    "data_impacto": "date",
    "ip": "ip",
    "ps": "ps",
    "ts": "ts",
    "energy": "energy",
    "metodo": "method",
    "sigma_vi": "sigma_vi",
    "sigma_mc": "sigma_mc",
}


def limpar(it: dict) -> dict:
    """Converte um registro do array 'data' para os tipos da silver."""
    return {
        "data_impacto": para_data(it.get("date")),  # '2108-05-24.69' -> só a data
        "ip": para_float(it.get("ip")),
        "ps": para_float(it.get("ps")),
        "ts": para_int(it.get("ts")),  # nulo continua nulo
        "energy": para_float(it.get("energy")),
        "metodo": it.get("method"),
        "sigma_vi": para_float(it.get("sigma_vi")),  # só nos IOBS
        "sigma_mc": para_float(it.get("sigma_mc")),  # só nos MC
    }


def carregar_silver_sentry_impacto_virtual() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Último snapshot do modo V
            cur.execute(
                """
                SELECT id, payload->'data'
                FROM bronze.sentry_raw
                WHERE source = 'sentry_vi'
                ORDER BY id DESC LIMIT 1
                """
            )
            bronze_id, itens = cur.fetchone()

            # 2) Confere as chaves do JSON em todos os registros
            for it in itens:
                faltando = CHAVES_ESPERADAS - set(it.keys())
                assert not faltando, f"Chaves faltando em {it.get('des')}: {faltando}"

            # 3) Limpa cada registro (posicao = índice no array)
            limpos = [limpar(it) for it in itens]

            # 4) Regra do projeto: a conversão não pode criar nulos
            for col, chave in CHAVE_JSON.items():
                antes = sum(1 for it in itens if it.get(chave) in (None, "", "NaN"))
                depois = sum(1 for l in limpos if l[col] is None)
                assert antes == depois, f"{col}: nulos antes={antes}, depois={depois}"

            # 5) Monta as linhas na ordem do INSERT
            linhas = [
                (
                    it["des"],
                    posicao,
                    l["data_impacto"],
                    l["ip"],
                    l["ps"],
                    l["ts"],
                    l["energy"],
                    l["metodo"],
                    l["sigma_vi"],
                    l["sigma_mc"],
                    bronze_id,
                )
                for posicao, (it, l) in enumerate(zip(itens, limpos, strict=False))
            ]

            # 6) Grava (rodar de novo no mesmo snapshot não duplica)

            cur.execute("TRUNCATE silver.sentry_impacto_virtual RESTART IDENTITY")

            cur.executemany(
                """
                INSERT INTO silver.sentry_impacto_virtual (
                    des, posicao, data_impacto, ip, ps, ts, energy,
                    metodo, sigma_vi, sigma_mc, bronze_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bronze_id, posicao) DO NOTHING
                """,
                linhas,
            )
            print(f"Registros lidos da bronze: {len(itens)} | bronze_id: {bronze_id}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_sentry_impacto_virtual()
