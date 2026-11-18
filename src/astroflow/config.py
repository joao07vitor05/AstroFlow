# Configuração central: conexão com o PostgreSQL.
import os

import psycopg  # psycopg 3
from dotenv import load_dotenv

load_dotenv()  # lê o arquivo .env


def get_connection() -> psycopg.Connection:
    """Abre uma conexão nova (quem chama fecha)."""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5436"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )