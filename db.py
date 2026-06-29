import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """
    Crea una conexión a Neon. 
    Lanza un error claro si la variable de entorno no existe.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("Error: La variable DATABASE_URL no está definida en tu archivo .env")
    
    return psycopg2.connect(db_url)

# Helper para ejecutar consultas y cerrar automáticamente
def ejecutar_query(query, params=None):
    """
    Función utilitaria para consultas que no requieren transacción (SELECTs).
    Abre y cierra la conexión automáticamente.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(query, params)
        resultado = cur.fetchall()
        return resultado
    finally:
        cur.close()
        conn.close()
