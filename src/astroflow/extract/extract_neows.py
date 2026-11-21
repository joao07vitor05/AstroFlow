import json
import os
import time
from datetime import date, timedelta

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from astroflow.config import get_connection

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.nasa.gov/neo/rest/v1/feed"
LOOKUP_URL = "https://api.nasa.gov/neo/rest/v1/neo"

DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.neows_feed_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    start_date    DATE        NOT NULL,
    end_date      DATE        NOT NULL,
    http_status   INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.neows_lookup_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    asteroid_id   TEXT        NOT NULL,
    http_status   INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def fetch_feed(start: date, end: date) -> requests.Response:
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "api_key": API_KEY,
    }
    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()  # levanta erro se vier 4xx/5xx
    except requests.RequestException as erro:
        # a mensagem original tem a URL com a api_key, então não a repassamos
        raise RuntimeError(f"Feed da NeoWs falhou ({type(erro).__name__})") from None
    return response


def limpar_chave(texto_resposta: str, api_key: str) -> dict:
    """
    Recebe o texto cru da resposta da NASA e devolve um dicionário Python
    com a api_key trocada por REDACTED.
    """
    # replace no TEXTO: troca todas as ocorrências da chave de uma vez
    texto_limpo = texto_resposta.replace(api_key, "REDACTED")

    # trava de segurança: se a chave ainda estiver no texto, o script para
    assert api_key not in texto_limpo, "A api_key ainda está no texto!"

    # json.loads transforma o texto em dicionário Python
    return json.loads(texto_limpo)


def save_raw(conn: psycopg.Connection, start: date, end: date, response: requests.Response) -> None:
    payload = limpar_chave(response.text, API_KEY)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.neows_feed_raw
                (source, start_date, end_date, http_status, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("neows_feed", start, end, response.status_code, Jsonb(payload)),
        )
    conn.commit()


def ids_do_feed(feed_json: dict) -> list[str]:
    """Pega os ids dos asteroides que vieram no feed."""
    # o feed agrupa os asteroides por data: {"2026-11-16": [ast1, ast2], ...}
    ids = []
    for _dia, asteroides in feed_json["near_earth_objects"].items():
        for asteroide in asteroides:
            ids.append(asteroide["id"])
    return ids


def ids_ja_extraidos(conn: psycopg.Connection) -> set[str]:
    """Devolve os ids que já estão na bronze do lookup."""
    with conn.cursor() as cur:
        cur.execute("SELECT asteroid_id FROM bronze.neows_lookup_raw")
        # set = conjunto: não repete valores e é rápido para perguntar "está aí?"
        return {linha[0] for linha in cur.fetchall()}


def save_lookup(conn: psycopg.Connection, asteroid_id: str, response: requests.Response) -> None:
    payload = limpar_chave(response.text, API_KEY)  # mesma limpeza do feed
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.neows_lookup_raw
                (source, asteroid_id, http_status, payload)
            VALUES (%s, %s, %s, %s)
            """,
            ("neows_lookup", asteroid_id, response.status_code, Jsonb(payload)),
        )
    conn.commit()


def extract_lookup(conn: psycopg.Connection, ids: list[str]) -> None:
    """Busca o lookup de cada asteroide novo e grava na bronze."""
    # só busca o que ainda não temos
    ja_extraidos = ids_ja_extraidos(conn)  # uma consulta só
    novos = [i for i in set(ids) if i not in ja_extraidos]
    print(f"Lookup: {len(novos)} asteroides novos de {len(set(ids))}")

    for asteroid_id in novos:
        try:
            resp = requests.get(
                f"{LOOKUP_URL}/{asteroid_id}",
                params={"api_key": API_KEY},
                timeout=30,
            )
        except requests.RequestException as erro:
            # imprime só o tipo do erro, porque a mensagem completa pode ter a URL com a chave
            print(f"  {asteroid_id}: falhou ({type(erro).__name__})")
            continue

        if resp.status_code != 200:
            # não grava respostas de erro (a coluna payload é obrigatória)
            print(f"  {asteroid_id}: status {resp.status_code}, pulando")
            continue

        save_lookup(conn, asteroid_id, resp)
        time.sleep(0.5)  # pausa curta para respeitar o limite de requisições da NASA


def main() -> None:
    if not API_KEY:
        raise RuntimeError("API_KEY não encontrada no .env")

    start = date.today()
    end = start + timedelta(days=6)  # janela de 7 dias, o máximo da API

    response = fetch_feed(start, end)
    print(f"Feed {start} -> {end}: {response.json()['element_count']} asteroides")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        save_raw(conn, start, end, response)

        ids = ids_do_feed(response.json())
        extract_lookup(conn, ids)


if __name__ == "__main__":
    main()
