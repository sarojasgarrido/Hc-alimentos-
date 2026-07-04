"""
Script de un solo uso: carga proveedores y productos DE EJEMPLO
Corregido para sintaxis PostgreSQL (%s en lugar de ?)
"""

from db import get_connection

PROVEEDORES = [
    {"nombre": "ECKART", "rut": "76.111.111-1"},
    {"nombre": "GRANA", "rut": "76.222.222-2"},
    {"nombre": "DIEGO", "rut": "76.333.333-3"},
]

PRODUCTOS = [
    ("100009", "MP. ALMIDON DE MAIZ", None),
    ("100014", "MP. BICARBONATO", "KG"),
    ("100015", "MP. CACAO NATURAL", "KG"),
    ("100019", "CITRATO SODIO", "KG"),
    ("100027", "MP. HARINA DE MANI", "KG"),
    ("200001", "Aulosa liquida", "KG"),
    ("200002", "Sal de Mar", "KG"),
    ("200003", "Pimienta", "KG"),
    ("200004", "Ajo molido", "GR"),
    ("200005", "Dextrin", "KG"),
    ("300001", "Estuche granola your protein", "UNIDAD"),
    ("300002", "Display de frutos del bosque Protein", "UNIDAD"),
    ("300003", "Display de frutos del bosque Vegan", "UNIDAD"),
    ("300004", "Display Chocolate Protein", "UNIDAD"),
    ("300005", "Display Chocolate Vegan", "UNIDAD"),
]

conn = get_connection()
cursor = conn.cursor()

# Carga de proveedores
for prov in PROVEEDORES:
    cursor.execute(
        "INSERT INTO tbl_proveedores (nombre, rut) VALUES (%s, %s)",
        (prov["nombre"], prov["rut"])
    )

# Carga de productos
for codigo, nombre, unidad in PRODUCTOS:
    cursor.execute(
        "INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)",
        (codigo, nombre, unidad)
    )

conn.commit()
cursor.close()
conn.close()

print(f"Cargados {len(PROVEEDORES)} proveedores y {len(PRODUCTOS)} productos de ejemplo.")
