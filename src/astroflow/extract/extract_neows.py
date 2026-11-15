import os
from datetime import date, timedelta

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.nasa.gov/neo/rest/v1/feed"

DDL = """
CREATE TABLE IF NOT EXISTS bronze.neows_feed_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    start_date    DATE        NOT NULL,
    end_date      DATE        NOT NULL,
    http_status   INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5436"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def fetch_feed(start: date, end: date) -> requests.Response:
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "api_key": API_KEY,
    }
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()  # levanta erro se vier 4xx/5xx
    return response


def save_raw(conn: psycopg.Connection, start: date, end: date, response: requests.Response) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.neows_feed_raw
                (source, start_date, end_date, http_status, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("neows_feed", start, end, response.status_code, Jsonb(response.json())),
        )
    conn.commit()


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

    print("Payload bruto salvo em bronze.neows_feed_raw")


if __name__ == "__main__":
    main()
