import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_2026'
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_in = request.form.get('usuario')
        pass_in = request.form.get('clave')
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s AND clave = %s", (user_in, pass_in))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['usuario'] = user['usuario']
            session['rol'] = user['rol']
            return redirect(url_for('dashboard'))
        flash("Usuario o clave incorrecta")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        # Simplificamos la inserción para evitar errores de tipo
        qr = f"HC-{str(uuid.uuid4())[:8].upper()}"
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s)", 
                    (int(request.form.get('id_proveedor')), qr, request.form.get('factura')))
        conn.commit()
        cur.close()
        conn.close()
        flash(f"Pallet creado: {qr}")
        return redirect(url_for('pallet_nuevo'))

    cur.execute("SELECT * FROM tbl_empresas WHERE es_proveedor = TRUE")
    provs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('pallet_nuevo.html', proveedores=provs)

# Asegúrate de mantener el resto de funciones con esta misma estructura
# de abrir y cerrar conexión explícitamente para evitar bloqueos del pool.

if __name__ == '__main__':
    app.run(debug=True)
