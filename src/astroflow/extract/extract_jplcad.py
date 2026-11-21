from datetime import date, timedelta

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from astroflow.config import get_connection

load_dotenv()

CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"
VERSAO_ESPERADA = "1.5"

DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.cad_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    query_params  JSONB       NOT NULL,
    http_status   INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CONSULTAS = {
    "cad_terra": {
        "dias_a_frente": 60,  # tamanho da janela; as datas são calculadas ao rodar
        "params": {
            "dist-max": "0.05",  # em au (unidade astronômica)
            "body": "Earth",
            "neo": "true",
            "sort": "date",  # explícito, para a ordem não depender do padrão da API
            "diameter": "true",  # inclui diameter e diameter_sigma
            "fullname": "true",  # inclui o nome completo do objeto
        },
    },
    # Exemplo de uma segunda consulta (descomente para usar):
    # "cad_phas": {
    #     "dias_a_frente": 365,
    #     "params": {
    #         "dist-max": "0.05",
    #         "body": "Earth",
    #         "neo": "true",
    #         "pha": "true",      # só asteroides potencialmente perigosos
    #         "sort": "date",
    #         "diameter": "true",
    #         "fullname": "true",
    #     },
    # },
}


def montar_params(nome: str, hoje: date | None = None) -> dict:
    """Monta os parâmetros finais de uma consulta, já com datas reais."""
    config = CONSULTAS[nome]
    hoje = hoje or date.today()  # se não passar data, usa a de hoje
    fim = hoje + timedelta(days=config["dias_a_frente"])

    # {**a, "x": 1} cria um dicionário novo com tudo de "a" mais as chaves extras
    return {
        **config["params"],
        "date-min": hoje.isoformat(),  # ex.: "2026-11-17"
        "date-max": fim.isoformat(),  # ex.: "2027-01-16"
    }


def fetch_cad(params: dict) -> requests.Response:
    response = requests.get(CAD_URL, params=params, timeout=30)
    response.raise_for_status()  # levanta erro se vier 4xx/5xx
    return response


def save_raw(
    conn: psycopg.Connection, source: str, params: dict, response: requests.Response
) -> None:
    payload = response.json()  # sem chave para limpar, o texto já é seguro

    versao = payload["signature"]["version"]
    if versao != VERSAO_ESPERADA:
        print(f"  ATENÇÃO: versão da API mudou ({versao}), confira o formato!")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.cad_raw
                (source, query_params, http_status, payload)
            VALUES (%s, %s, %s, %s)
            """,
            (source, Jsonb(params), response.status_code, Jsonb(payload)),
        )
    conn.commit()


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

        for nome in CONSULTAS:
            params = montar_params(nome)
            response = fetch_cad(params)
            qtd = response.json()["count"]
            print(f"{nome}: {qtd} aproximações")
            save_raw(conn, nome, params, response)


if __name__ == "__main__":
    main()
