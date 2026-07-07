import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- RUTAS DE NAVEGACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario'] = request.form.get('usuario')
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    # Estructuras de datos requeridas por dashboard.html
    context = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0, 'total_salidas': 0,
        'proximos_vencer': [], 
        'racks_long': [], 'racks_trans': [], 'piso': [],
        'capacidad_pallet': 0, 
        'racks_detalle_json': json.dumps({}), 
        'piso_detalle_json': json.dumps({}),
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': [],
        'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', '')
    }
    return render_template('dashboard.html', **context)

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista)

# --- RUTAS DE NAVEGACIÓN FALTANTES (Evitan BuildError) ---
@app.route('/nuevo_pallet')
def nuevo_pallet(): return render_template('pallet_nuevo.html')

@app.route('/consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html')

@app.route('/picking')
def picking(): return render_template('picking.html')

@app.route('/empresas')
def empresas(): return render_template('empresas.html')

# --- RUTAS CON LÓGICA DE DATOS ---
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

@app.route
