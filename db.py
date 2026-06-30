import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL no configurada")
    return psycopg2.connect(db_url)

# Para consultas SELECT
def ejecutar_query(query, params=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(query, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

# Para INSERT, UPDATE, DELETE (Operaciones que cambian datos)
def ejecutar_comando(query, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        conn.commit() # ¡Esto es lo que faltaba!
    finally:
        cur.close()
        conn.close()
