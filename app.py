import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    # Asegúrate de que esta variable esté configurada en tu entorno de Render
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_in = request.form.get('usuario')
        pass_in = request.form.get('clave')
        # Lógica de verificación pendiente de implementar según tu esquema de base de datos
        session['usuario'] = user_in
        session['rol'] = 'Administrador' # Ejemplo
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        id_prov = request.form.get('id_proveedor')
        factura = request.form.get('factura')
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", (id_prov, factura))
        conn.commit()
        flash("Pallet registrado")
        return redirect(url_for('dashboard'))
    cur.execute("SELECT * FROM tbl_proveedores")
    provs = cur.fetchall()
    cur.execute("SELECT * FROM tbl_productos")
    prods = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- PRODUCTOS ---
@app.route('/productos', methods=['GET', 'POST'])
def productos():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        codigo = request.form.get('codigo')
        unidad = request.form.get('unidad')
        cur.execute("INSERT INTO tbl_productos (nombre, codigo, unidad, activo) VALUES (%s, %s, %s, True)", (nombre, codigo, unidad))
        conn.commit()
    cur.execute("SELECT * FROM tbl_productos")
    lista = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('productos.html', productos=lista)

# --- EMPRESAS ---
@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        rut = request.form.get('rut')
        cur.execute("INSERT INTO tbl_empresas (nombre, rut) VALUES (%s, %s)", (nombre, rut))
        conn.commit()
    cur.execute("SELECT * FROM tbl_empresas")
    lista = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('empresas.html', empresas=lista)

# --- USUARIOS ---
@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        user = request.form.get('usuario')
        clave = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo) VALUES (%s, %s, %s, 'Operador', True)", 
                    (nombre, user, clave))
        conn.commit()
    cur.execute("SELECT * FROM tbl_usuarios")
    lista = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

if __name__ == '__main__':
    app.run(debug=True)
