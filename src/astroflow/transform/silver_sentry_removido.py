# Carga da silver.sentry_removido (Sentry modo R).
# Lê o ÚLTIMO snapshot de 'sentry_removidos' na bronze.
from astroflow.config import get_connection
from astroflow.transform.conversores import para_datahora

CHAVES_ESPERADAS = {"des", "removed"}


def carregar_silver_sentry_removido() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Último snapshot do modo R
            cur.execute(
                """
                SELECT id, payload->'data'
                FROM bronze.sentry_raw
                WHERE source = 'sentry_removidos'
                ORDER BY id DESC LIMIT 1
                """
            )
            bronze_id, itens = cur.fetchone()

            # 2) Confere as chaves do JSON
            assert CHAVES_ESPERADAS <= set(
                itens[0].keys()
            ), f"Chaves diferentes do esperado: {set(itens[0].keys())}"

            # 3) des tem que ser único (é a PK da tabela)
            assert len({it["des"] for it in itens}) == len(itens), "Há des repetido no modo R"

            # 4) Converte 'removed' (UTC, com segundos) para datetime
            linhas = [(it["des"], para_datahora(it["removed"]), bronze_id) for it in itens]

            # 5) Regra do projeto: a conversão não pode criar nulos
            antes = sum(1 for it in itens if it["removed"] in (None, ""))
            depois = sum(1 for l in linhas if l[1] is None)
            assert antes == depois == 0, f"removed: nulos antes={antes}, depois={depois}"

            cur.execute("TRUNCATE silver.sentry_removido")

            # 6) Grava (rodar de novo não duplica)
            cur.executemany(
                """
                INSERT INTO silver.sentry_removido (des, removido_em, bronze_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (des) DO NOTHING
                """,
                linhas,
            )
            print(f"Itens lidos da bronze: {len(itens)} | bronze_id: {bronze_id}")
        conn.commit()


if __name__ == "__main__":
    carregar_silver_sentry_removido()
