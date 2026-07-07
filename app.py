import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s", (usuario,))
            user = cur.fetchone()
            cur.close(); conn.close()
            
            if user and check_password_hash(user['clave'], clave):
                session['usuario'] = user['usuario']
                session['nombre'] = user['nombre']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                error = "Usuario o clave incorrectos"
        except Exception as e:
            error = "Error de conexión con la base de datos"
            print(f"Error login: {e}")
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    context = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0, 'total_salidas': 0,
        'proximos_vencer': [], 'racks_long': [], 'racks_trans': [], 'piso': [],
        'capacidad_pallet': 0, 'racks_detalle_json': json.dumps({}), 
        'piso_detalle_json': json.dumps({}),
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': [],
        'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', '')
    }
    return render_template('dashboard.html', **context)

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", 
                    (request.form.get('id_proveedor'), request.form.get('factura')))
        conn.commit()
    cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores")
    provs = cur.fetchall()
    cur.execute("SELECT id_producto, nombre FROM tbl_productos")
    prods = cur.fetchall()
    cur.close(); conn.close()
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- PRODUCTOS Y USUARIOS ---
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
    cur.close(); conn.close()
    return render_template('productos.html', productos=lista)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        clave = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo) VALUES (%s, %s, %s, 'Operador', True)", 
                    (request.form.get('nombre'), request.form.get('usuario'), clave))
        conn.commit()
    cur.execute("SELECT * FROM tbl_usuarios")
    lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('usuarios.html', usuarios=lista)

# --- NAVEGACIÓN COMPLEMENTARIA ---
@app.route('/detalle_panel/<vista>')
def detalle_panel(vista): return render_template('detalle_panel.html', titulo=vista)
@app.route('/consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')
@app.route('/buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html', resultados=None, filtros={'factura': ''})
@app.route('/picking')
def picking(): return render_template('picking.html')
@app.route('/empresas')
def empresas(): return render_template('empresas.html')
@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet): return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])

if __name__ == '__main__':
    app.run()
