from werkzeug.security import generate_password_hash
from psycopg2 import errors
from dotenv import load_dotenv
import os
from db import get_connection

# 1. Cargamos el archivo .env primero
load_dotenv()

# Datos del usuario
NOMBRE = "Administrador Bodega"
USUARIO = "admin"
CLAVE = "admin123"
ROL = "Administrador"

# 2. Generamos el hash de seguridad
clave_hash = generate_password_hash(CLAVE)

try:
    # 3. Intentamos conectar
    conn = get_connection()
    
    # Imprimimos a dónde nos estamos conectando para estar 100% seguros
    dsn = conn.get_dsn_parameters()
    print(f"--- Conectado exitosamente a: {dsn['host']} ---")
    
    cursor = conn.cursor()

    # 4. Intentamos insertar
    cursor.execute(
        """
        INSERT INTO tbl_usuarios (nombre, usuario, clave, rol)
        VALUES (%s, %s, %s, %s)
        """,
        (NOMBRE, USUARIO, clave_hash, ROL)
    )

    conn.commit()
    print(f"ÉXITO: Usuario '{USUARIO}' creado correctamente en la base de datos.")

except errors.UniqueViolation:
    print(f"AVISO: El usuario '{USUARIO}' ya existe en la base de datos. No se realizaron cambios.")
except Exception as e:
    print(f"ERROR: Ocurrió un problema inesperado: {e}")
    # Si la conexión falló, no podemos hacer rollback, pero cerramos si existe
    if 'conn' in locals():
        conn.rollback()

finally:
    # 5. Cerramos conexión
    if 'cursor' in locals(): cursor.close()
    if 'conn' in locals(): conn.close()
    print("--- Conexión cerrada ---")
