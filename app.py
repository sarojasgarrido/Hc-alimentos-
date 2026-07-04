import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario'] = request.form.get('usuario')
        session['rol'] = 'Administrador'
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    datos = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0, 'total_salidas': 0,
        'proximos_vencer': [], 'racks_long': [], 'racks_trans': [], 'piso': [],
        'capacidad_pallet': 0, 'racks_detalle_json': '{}', 'piso_detalle_json': '{}',
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': []
    }
    return render_template('dashboard.html', **datos)

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", 
                    (request.form.get('id_proveedor'), request.form.get('factura')))
        conn.commit()
        flash("Pallet registrado")
        return redirect(url_for('dashboard'))
    try:
        cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores")
        proveedores = cur.fetchall()
        cur.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = True")
        productos = cur.fetchall()
    except:
        proveedores, productos = [], []
    cur.close()
    conn.close()
    return render_template('pallet_nuevo.html', proveedores=proveedores, productos=productos)

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])

@app.route('/consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet():
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets():
    return render_template('buscar_pallets.html', resultados=None, filtros={})

@app.route('/historial_pallet/<int:id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<int:id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    return render_template('pallet_editar.html', pallet={'id_pallet': id_pallet}, items=[], proveedores=[], productos=[])

@app.route('/despachar_pallet/<int:id_pallet>', methods=['POST'])
def despachar_pallet(id_pallet):
    return redirect(url_for('ver_pallet', id_pallet=id_pallet))

# --- PICKING Y PRODUCTOS ---
@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html', productos=[], stock_piso=[])

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_productos (nombre, codigo, unidad, activo) VALUES (%s, %s, %s, True)", 
                    (request.form.get('nombre'), request.form.get('codigo'), request.form.get('unidad')))
        conn.commit()
    cur.execute("SELECT * FROM tbl_productos")
    lista = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('productos.html', productos=lista)

# --- EMPRESAS Y USUARIOS ---
@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_empresas (nombre, rut) VALUES (%s, %s)", 
                    (request.form.get('nombre'), request.form.get('rut')))
        conn.commit()
    cur.execute("SELECT * FROM tbl_empresas")
    lista = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('empresas.html', empresas=lista)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        clave = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo) VALUES (%s, %s, %s, 'Operador', True)", 
                    (request.form.get('nombre'), request.form.get('usuario'), clave))
        conn.commit()
    try:
        cur.execute("SELECT * FROM tbl_usuarios")
        lista = cur.fetchall()
    except:
        lista = []
    cur.close()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

if __name__ == '__main__':
    app.run(debug=True)
