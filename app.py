import os
import uuid
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

@app.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        rol = request.form.get('rol')
        try:
            cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol) VALUES (%s, %s, %s, %s)", 
                        (nombre, usuario, clave, rol))
            conn.commit()
            flash("Personal añadido exitosamente.")
        except Exception as e:
            conn.rollback()
            flash(f"Error al crear usuario: {str(e)}")
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
            ORDER BY p.id_pallet DESC
        """)
        resultados = cur.fetchall()
    except Exception as e:
        resultados = []
        flash(f"Error de base de datos en búsqueda: {str(e)}")
    finally:
        cur.close()
    return render_template('buscar_pallets.html', resultados=resultados)

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        nombre = request.form.get('nombre')
        unidad = request.form.get('unidad')
        try:
            cur.execute("INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)", (codigo, nombre, unidad))
            conn.commit()
            flash("Producto registrado exitosamente.")
        except Exception as e:
            conn.rollback()
            flash(f"Error al guardar producto: {str(e)}")
        return redirect(url_for('productos'))
    try:
        cur.execute("SELECT * FROM tbl_productos ORDER BY nombre ASC")
        lista_productos = cur.fetchall()
    except Exception as e:
        lista_productos = []
    finally:
        cur.close()
    return render_template('productos.html', productos=lista_productos)

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        rut = request.form.get('rut')
        es_proveedor = request.form.get('es_proveedor') == 'on'
        es_cliente = request.form.get('es_cliente') == 'on'
        try:
            cur.execute("INSERT INTO tbl_empresas (nombre, rut, es_proveedor, es_cliente) VALUES (%s, %s, %s, %s)", (nombre, rut, es_proveedor, es_cliente))
            conn.commit()
            flash("Empresa registrada exitosamente.")
        except Exception as e:
            conn.rollback()
            flash(f"Error al guardar empresa: {str(e)}")
        return redirect(url_for('empresas'))
    try:
        cur.execute("SELECT * FROM tbl_empresas ORDER BY nombre ASC")
        lista_empresas = cur.fetchall()
    except Exception as e:
        lista_empresas = []
    finally:
        cur.close()
    return render_template('empresas.html', empresas=lista_empresas)

# --- MÓDULO INGRESO DE PALLETS ACTUALIZADO ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        id_proveedor = request.form.get('id_proveedor')
        factura = request.form.get('factura')
        
        # Recuperar arrays de productos ingresados dinámicamente
        id_productos = request.form.getlist('id_producto[]')
        cantidades = request.form.getlist('cantidad[]')
        elaboraciones = request.form.getlist('fecha_elaboracion[]')
        vencimientos = request.form.getlist('fecha_vencimiento[]')

        # Generación automática del QR
        codigo_qr = f"HC-{str(uuid.uuid4())[:8].upper()}"

        try:
            # Insertar cabecera del pallet
            cur.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s) RETURNING id_pallet", 
                        (id_proveedor, codigo_qr, factura))
            id_pallet = cur.fetchone()['id_pallet']

            # Insertar detalle de productos iterando sobre las listas
            for i in range(len(id_productos)):
                cur.execute("""
                    INSERT INTO tbl_pallet_producto 
                    (id_pallet, id_producto, cantidad, cantidad_original, fecha_elaboracion, fecha_vencimiento) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_pallet, id_productos[i], cantidades[i], cantidades[i], elaboraciones[i], vencimientos[i]))

            conn.commit()
            flash(f"Pallet registrado correctamente. QR Asignado: {codigo_qr}")
        except Exception as e:
            conn.rollback()
            flash(f"Error al ingresar pallet: {str(e)}")
        return redirect(url_for('pallet_nuevo'))

    try:
        # Cargar selectores
        cur.execute("SELECT id_empresa, nombre FROM tbl_empresas WHERE es_proveedor = TRUE ORDER BY nombre ASC")
        proveedores = cur.fetchall()
        
        cur.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE ORDER BY nombre ASC")
        productos = cur.fetchall()
    except Exception as e:
        proveedores = []
        productos = []
    finally:
        cur.close()
        
    return render_template('pallet_nuevo.html', proveedores=proveedores, productos=productos)

@app.route('/consulta_pallet')
def consulta_pallet(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('consulta_pallet.html')

@app.route('/picking', methods=['GET', 'POST'])
def picking(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        qr = request.form.get('codigo_qr')
        flash(f"Picking registrado para el QR: {qr} (Modo prueba)")
        return redirect(url_for('picking'))
    return render_template('picking.html')

if __name__ == '__main__':
    app.run(debug=True)
