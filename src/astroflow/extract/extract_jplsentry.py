import os

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
import time
from urllib.parse import quote

LIMITE_TESTE = None

load_dotenv()

SENTRY_URL = "https://ssd-api.jpl.nasa.gov/sentry.api"
VERSAO_ESPERADA = "2.0"

DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.sentry_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    query_params  JSONB       NOT NULL,
    http_status   INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Cada item é um modo da Sentry: nome -> parâmetros.
# Sem filtros de propósito: na bronze queremos o dado completo.
# Atenção: não misture parâmetros de modos diferentes na mesma consulta (dá erro).
CONSULTAS = {
    "sentry_resumo": {},                 # modo S: sem parâmetros = resumo de todos os objetos
    "sentry_vi": {"all": "true"},        # modo V: todos os impactores virtuais
    "sentry_removidos": {"removed": "true"},  # modo R: objetos retirados da Sentry
}


def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5436"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def fetch_sentry(params: dict) -> requests.Response:
    response = requests.get(SENTRY_URL, params=params, timeout=60)
    response.raise_for_status()  # levanta erro se vier 4xx/5xx
    return response


def save_raw(conn: psycopg.Connection, source: str, params: dict,
             response: requests.Response) -> None:
    payload = response.json()  # sem chave para limpar

    versao = payload["signature"]["version"]
    if versao != VERSAO_ESPERADA:
        print(f"  ATENÇÃO: versão da API mudou ({versao}), confira o formato!")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.sentry_raw
                (source, query_params, http_status, payload)
            VALUES (%s, %s, %s, %s)
            """,
            (source, Jsonb(params), response.status_code, Jsonb(payload)),
        )
    conn.commit()

def designacoes_do_resumo(conn: psycopg.Connection) -> list[str]:
    """Lê o resumo mais recente na bronze e devolve a designação (des) de cada objeto."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT payload FROM bronze.sentry_raw
            WHERE source = 'sentry_resumo'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        payload = cur.fetchone()[0]  # o psycopg já devolve o JSONB como dicionário
    return [objeto["des"] for objeto in payload["data"]]


def designacoes_ja_extraidas(conn: psycopg.Connection) -> set[str]:
    """Devolve as designações que já estão na bronze no modo O."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT query_params->>'des' FROM bronze.sentry_raw
            WHERE source = 'sentry_objeto'
            """
        )
        return {linha[0] for linha in cur.fetchall()}


def extract_objetos(conn: psycopg.Connection) -> None:
    """Busca os detalhes (modo O) de cada objeto novo e grava na bronze."""
    todas = designacoes_do_resumo(conn)
    ja_extraidas = designacoes_ja_extraidas(conn)   # buscado uma vez só, fora do loop
    novas = [des for des in todas if des not in ja_extraidas]
    print(f"Objetos: {len(novas)} novos de {len(todas)}")

    if LIMITE_TESTE:
        novas = novas[:LIMITE_TESTE]
        print(f"  (modo teste: só {len(novas)})")

    for posicao, des in enumerate(novas, start=1):
        if posicao % 100 == 0:
            print(f"  {posicao}/{len(novas)} objetos processados")
        try:
            # quote troca o espaço por %20; passar a query como texto evita que o requests mexa nela
            resp = requests.get(SENTRY_URL, params=f"des={quote(des)}", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as erro:
            print(f"  {des}: falhou ({erro})")
            continue

        # a API devolve 200 mesmo quando o objeto não existe ou foi removido
        if "error" in resp.json():
            print(f"  {des}: {resp.json()['error']}, pulando")
            continue

        save_raw(conn, "sentry_objeto", {"des": des}, resp)  # reaproveita o save_raw
        time.sleep(0.5)  # pausa curta para não sobrecarregar o servidor

def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

        for nome, params in CONSULTAS.items():
            response = fetch_sentry(params)
            qtd = response.json().get("count")   # os modos S, V e R trazem "count"
            print(f"{nome}: {qtd} registros")
            save_raw(conn, nome, params, response)

        extract_objetos(conn)
if __name__ == "__main__":
    main()