import os
import psycopg2
from dotenv import load_dotenv

# Carga las variables de entorno (asegúrate de que DATABASE_URL esté en Render)
load_dotenv()

def get_connection():
    """
    Crea y devuelve una conexión a la base de datos PostgreSQL (Neon).
    """
    # La variable DATABASE_URL ya contiene toda la información de conexión
    # que te da Neon/Render.
    url_db = os.environ.get("DATABASE_URL")
    
    if not url_db:
        raise ValueError("DATABASE_URL no está configurada en las variables de entorno.")
        
    return psycopg2.connect(url_db)