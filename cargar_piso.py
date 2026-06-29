from db import get_connection

conn = get_connection()
cursor = conn.cursor()

total = 0
for posicion_num in range(1, 13):
    cursor.execute(
        """
        INSERT INTO tbl_ubicaciones (rack, nivel, posicion, estado)
        VALUES ('P', 'N1', %s, 'Libre')
        """,
        (str(posicion_num),)
    )
    total += 1

conn.commit()
cursor.close()
conn.close()

print(f"Se crearon {total} posiciones de piso (P-N1-1 a P-N1-12).")