import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'Administrador':
            flash("No tienes permisos suficientes.")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    datos_dashboard = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0, 'total_salidas': 0,
        'proximos_vencer': [], 'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', ''), 'capacidad_pallet': 0,
        'racks_long': [], 'piso': [], 'racks_trans': [],
        'racks_detalle_json': '{}', 'piso_detalle_json': '{}',
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': []
    }
    return render_template('dashboard.html', **datos_dashboard)

# --- RUTAS DE GESTIÓN (Evitan Error 500) ---

@app.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        rol = request.form.get('rol')
        try:
            cur.execute("INSERT INTO tbl_usuarios (nombre, rol) VALUES (%s, %s)", (nombre, rol))
            conn.commit()
            flash("Operador creado exitosamente")
        except Exception as e:
            conn.rollback() # Revierte si hay error para no bloquear la BD
            flash(f"Error de base de datos al crear: {str(e)}")
        return redirect(url_for('usuarios'))
    
    try:
        cur.execute("SELECT * FROM tbl_usuarios ORDER BY id_usuario DESC")
        lista_usuarios = cur.fetchall()
    except Exception as e:
        lista_usuarios = []
        flash(f"Error cargando usuarios: {str(e)}")
    finally:
        cur.close()
        
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/buscar_pallets', methods=['GET'])
def buscar_pallets():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT p.*, e.nombre as proveedor, u.rack, u.nivel, u.posicion 
            FROM tbl_pallets p
            LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
            LEFT JOIN tbl_pallet_ubicacion pu ON p.id_pallet = pu.id_pallet AND pu.vigente = TRUE
            LEFT JOIN tbl_ubicaciones u ON pu.id_ubicacion = u.id_ubicacion
        """)
        resultados = cur.fetchall()
    except Exception as e:
        resultados = []
        flash(f"Error de SQL en pallets: {str(e)}")
    finally:
        cur.close()
    return render_template('buscar_pallets.html', resultados=resultados)

# --- RUTAS EN CONSTRUCCIÓN (Para que el menú funcione) ---

@app.route('/nuevo_pallet')
def nuevo_pallet(): 
    flash("Módulo de Ingreso de Pallet en desarrollo.")
    return redirect(url_for('dashboard'))

@app.route('/consulta_pallet')
def consulta_pallet(): 
    flash("Módulo de Consulta en desarrollo.")
    return redirect(url_for('dashboard'))

@app.route('/picking')
def picking(): 
    flash("Módulo de Picking/Despacho en desarrollo.")
    return redirect(url_for('dashboard'))

@app.route('/productos')
def productos(): 
    flash("Módulo de Productos en desarrollo.")
    return redirect(url_for('dashboard'))

@app.route('/empresas')
def empresas(): 
    flash("Módulo de Empresas en desarrollo.")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
