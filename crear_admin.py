from werkzeug.security import generate_password_hash
from db import get_connection

NOMBRE = "Administrador Bodega"
USUARIO = "admin"
CLAVE = "admin123"
ROL = "Administrador"

clave_hash = generate_password_hash(CLAVE)
conn = get_connection()
cursor = conn.cursor()

# Cambiado ? por %s
cursor.execute(
    "INSERT INTO tbl_usuarios (nombre, usuario, clave, rol) VALUES (%s, %s, %s, %s)",
    (NOMBRE, USUARIO, clave_hash, ROL)
)

conn.commit()
conn.close()
print(f"Usuario '{USUARIO}' creado correctamente.")
