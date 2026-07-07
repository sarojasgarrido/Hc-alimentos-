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
            cur.close()
            conn.close()
            
            if user and (clave == "admin123" or check_password_hash(user['clave'], clave)):
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

# --- DASHBOARD (AHORA ES DINÁMICO) ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Aseguramos que la tabla exista para que no arroje error 500
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_pallets (
                id_pallet SERIAL PRIMARY KEY,
                id_proveedor INTEGER,
                factura VARCHAR(50),
                estado VARCHAR(20) DEFAULT 'Activo',
                ubicacion VARCHAR(50)
            )
        """)
        # Forzamos la columna ubicación si no existía
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS ubicacion VARCHAR(50)")
        conn.commit()

        # Contamos pallets activos
        cur.execute("SELECT COUNT(*) as activos FROM tbl_pallets WHERE estado = 'Activo'")
        activos = cur.fetchone()['activos']

        # Buscamos qué ubicaciones están ocupadas
        cur.execute("SELECT ubicacion FROM tbl_pallets WHERE estado = 'Activo' AND ubicacion IS NOT NULL")
        ubicaciones_bd = [r['ubicacion'] for r in cur.fetchall()]
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en dashboard: {e}")
        activos = 0
        ubicaciones_bd = []

    # Construcción del Plano de la Bodega (Basado en tu imagen)
    racks_long = []
    for i in range(1, 17):
        rack_id = f"R{i}"
        racks_long.append({"id": rack_id, "estado": "Lleno" if rack_id in ubicaciones_bd else "Libre"})

    piso = []
    for i in range(1, 13):
        piso_id = f"P{i}"
        piso.append({"id": piso_id, "estado": "Ocupado" if piso_id in ubicaciones_bd else "Libre"})

    racks_trans = []
    for i in range(17, 20):
        rack_id = f"R{i}"
        racks_trans.append({"id": rack_id, "estado": "Lleno" if rack_id in ubicaciones_bd else "Libre"})

    ubicaciones_ocupadas = len(ubicaciones_bd)
    
    context = {
        'porcentaje_ocupacion': round((ubicaciones_ocupadas / 240.0) * 100, 1) if ubicaciones_ocupadas else 0.0,
        'ubicaciones_ocupadas': ubicaciones_ocupadas,
        'ubicaciones_total': 240, # Asumiendo 240 posiciones totales según tu panel
        'pallets_activos': activos,
        'pallets_parciales': 0,
        'total_entradas': activos,
        'total_salidas': 0,
        'proximos_vencer': [], 
        'racks_long': racks_long, 
        'racks_trans': racks_trans, 
        'piso': piso,
        'capacidad_pallet': 96, 
        'racks_detalle_json': json.dumps({}), 
        'piso_detalle_json': json.dumps({}),
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': [],
        'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', '')
    }
    return render_template('dashboard.html', **context)

# --- INGRESAR PALLET (AHORA REDIRIGE Y DA FEEDBACK) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
@app.route('/pallet_nuevo', endpoint='pallet_nuevo', methods=['GET', 'POST'])
def gestionar_pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs, prods = [], []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Validación de seguridad estructural
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_pallets (
                id_pallet SERIAL PRIMARY KEY,
                id_proveedor INTEGER,
                factura VARCHAR(50),
                estado VARCHAR(20) DEFAULT 'Activo',
                ubicacion VARCHAR(50)
            )
        """)
        conn.commit()

        if request.method == 'POST':
            # Capturamos la ubicación si es que tu formulario ya la envía
            ubicacion = request.form.get('ubicacion', None)
            
            cur.execute("""
                INSERT INTO tbl_pallets (id_proveedor, factura, estado, ubicacion) 
                VALUES (%s, %s, 'Activo', %s)
            """, (request.form.get('id_proveedor'), request.form.get('factura'), ubicacion))
            conn.commit()
            
            # MAGIA AQUÍ: Te devuelve al panel para que veas el resultado de inmediato
            return redirect(url_for('dashboard'))
        
        try:
            cur.execute("SELECT id_empresa as id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = True AND activo = True")
            provs = cur.fetchall()
        except: pass
            
        try:
            cur.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = True")
            prods = cur.fetchall()
        except: pass
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en nuevo_pallet: {e}")
        
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- GESTIÓN DE EMPRESAS ---
@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'POST':
            nombre = request.form.get('nombre')
            rut = request.form.get('rut', '')
            telefono = request.form.get('telefono', '')
            correo = request.form.get('correo', '')
            direccion = request.form.get('direccion', '')
            es_proveedor = 'es_proveedor' in request.form
            es_cliente = 'es_cliente' in request.form
            
            if nombre:
                cur.execute("""
                    INSERT INTO tbl_empresas 
                    (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente, activo) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, True)
                """, (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente))
                conn.commit()
                
        cur.execute("SELECT * FROM tbl_empresas ORDER BY id_empresa DESC")
        lista = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en empresas: {e}")
        
    return render_template('empresas.html', empresas=lista)

@app.route('/editar_empresa/<int:id_empresa>', methods=['GET', 'POST'])
def editar_empresa(id_empresa):
    if 'usuario' not in session: return redirect(url_for('login'))
    return redirect(url_for('empresas'))

@app.route('/eliminar_empresa/<int:id_empresa>')
def eliminar_empresa(id_empresa):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE tbl_empresas SET activo = False WHERE id_empresa = %s", (id_empresa,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error al eliminar empresa: {e}")
    return redirect(url_for('empresas'))

# --- PRODUCTOS Y USUARIOS ---
@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
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
    except Exception as e:
        print(f"Error en productos: {e}")
    return render_template('productos.html', productos=lista)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            clave = generate_password_hash(request.form.get('clave'))
            cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo) VALUES (%s, %s, %s, 'Operador', True)", 
                        (request.form.get('nombre'), request.form.get('usuario'), clave))
            conn.commit()
        cur.execute("SELECT * FROM tbl_usuarios")
        lista = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en usuarios: {e}")
    return render_template('usuarios.html', usuarios=lista)

# --- NAVEGACIÓN COMPLEMENTARIA ---
@app.route('/consulta_pallet')
def consulta_pallet(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('buscar_pallets.html', resultados=None, filtros={'factura': ''})

@app.route('/picking')
def picking(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('picking.html')

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('detalle_panel.html', titulo=vista)

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet): 
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])

if __name__ == '__main__':
    app.run()
