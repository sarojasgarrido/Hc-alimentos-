from db import get_connection

conn = get_connection()
cursor = conn.cursor()

total_creadas = 0

for rack_num in range(1, 21):           # R1 a R20
    for nivel_num in range(1, 5):       # N1 a N4
        for posicion_num in range(1, 4):  # 1 a 3
            rack = f"R{rack_num}"
            nivel = f"N{nivel_num}"
            posicion = str(posicion_num)

            cursor.execute(
                """
                INSERT INTO tbl_ubicaciones (rack, nivel, posicion, estado)
                VALUES (%s, %s, %s, 'Libre')
                """,
                (rack, nivel, posicion)
            )
            total_creadas += 1

conn.commit()
cursor.close()
conn.close()

print(f"Se crearon {total_creadas} ubicaciones.")