from db import get_connection

PROVEEDORES = [
    {"nombre": "ECKART", "rut": "76.111.111-1"},
    {"nombre": "GRANA", "rut": "76.222.222-2"},
    {"nombre": "DIEGO", "rut": "76.333.333-3"},
]

PRODUCTOS = [
    ("100009", "MP. ALMIDON DE MAIZ", None),
    ("100014", "MP. BICARBONATO", "KG"),
    # ... (resto de tus productos)
]

conn = get_connection()
cursor = conn.cursor()

# Insertar en tbl_empresas
for prov in PROVEEDORES:
    cursor.execute(
        """
        INSERT INTO tbl_empresas (nombre, rut, es_proveedor, es_cliente) 
        VALUES (%s, %s, TRUE, FALSE)
        """,
        (prov["nombre"], prov["rut"])
    )

# Insertar en tbl_productos
for codigo, nombre, unidad in PRODUCTOS:
    cursor.execute(
        "INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)",
        (codigo, nombre, unidad)
    )

conn.commit()
cursor.close()
conn.close()

print(f"Cargados proveedores y productos de ejemplo.")