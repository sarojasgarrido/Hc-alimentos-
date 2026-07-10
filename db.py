import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Crea y devuelve una conexion a PostgreSQL.
    Usa NamedTupleCursor para que los resultados se accedan por nombre de columna.
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Render provee DATABASE_URL completa
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.NamedTupleCursor)
    else:
        # Desarrollo local
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "sistema_almacen"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            cursor_factory=psycopg2.extras.NamedTupleCursor
        )

    conn.autocommit = False
    return conn
