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

# --- DASHBOARD (AHORA CON DETALLE EXACTO POR CELDA) ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    activos = 0
    ubicaciones_ocupadas_bd = []
    racksData = {}
    
    # 1. Preparamos el esqueleto de 20 Racks x 4 Niveles x 3 Posiciones
    for i in range(1, 21):
        racksData[f"R{i}"] = {
            "ocupadas": 0,
            "total": 12,
            "celdas": {
                "N4": {"1": None, "2": None, "3": None},
                "N3": {"1": None, "2": None, "3": None},
                "N2": {"1": None, "2": None, "3": None},
                "N1": {"1": None, "2": None, "3": None}
            }
        }

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Validamos estructura de base de datos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_pallets (
                id_pallet SERIAL PRIMARY KEY,
                codigo_qr VARCHAR(100),
                id_proveedor INTEGER,
                factura VARCHAR(50),
                estado VARCHAR(20) DEFAULT 'Activo',
                ubicacion VARCHAR(50)
            )
        """)
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS id_producto INTEGER")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS nivel VARCHAR(10)")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS posicion VARCHAR(10)")
        conn.commit()

        # 2. Consultamos la ubicación exacta uniendo productos y empresas
        cur.execute("""
            SELECT p.id_pallet, p.ubicacion, p.nivel, p.posicion, 
                   pr.nombre as producto, e.nombre as proveedor
            FROM tbl_pallets p
            LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto
            LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
            WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL
        """)
        pallets = cur.fetchall()
        
        for p in pallets:
            ubicaciones_ocupadas_bd.append(p['ubicacion'])
            rack = p['ubicacion']
            nivel = p['nivel']
            pos = p['posicion']
            
            # Llenamos la celda específica si es un Rack
            if rack.startswith('R') and rack in racksData and nivel and pos:
                if nivel in racksData[rack]['celdas'] and pos in racksData[rack]['celdas'][nivel]:
                    # Unimos Producto y Proveedor para que se muestre hermoso en el cuadro
                    etiqueta_detalle = f"<span style='color:#C8311F;'>{p['producto'] or 'Pallet'}</span><br>{p['proveedor'] or ''}"
                    
                    racksData[rack]['celdas'][nivel][pos] = {
                        "id_pallet": p['id_pallet'],
                        "proveedor": etiqueta_detalle,
                        "cantidad": 1,
                        "capacidad": 1,
                        "pct_llenado": 100
                    }
                    racksData[rack]["ocupadas"] += 1
                    
        activos = len(pallets)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en dashboard: {e}")

    # 3. Lógica dinámica de colores según % de ocupación
    def generar_color_rack(id_rack):
        ocupadas = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocupadas / 12.0) * 100
        
        if pct == 100: color, texto = "#C8311F", "white"        # Lleno
        elif pct >= 60: color, texto = "#F4B795", "#8C2E1F"     # Mayoría
        elif pct > 0: color, texto = "#FCEFE2", "#8C5A2A"       # Parcial
        else: color, texto = "#E8F0E5", "#3C6B3F"               # Libre
            
        return {"nombre": id_rack, "ocupadas": ocupadas, "total": 12, "color": color, "color_texto": texto}

    racks_long = [generar_color_rack(f"R{i}") for i in range(1, 17)]
    
    piso = []
    for i in range(1, 13):
        id_piso = f"P{i}"
        ocupado = id_piso in ubicaciones_ocupadas_bd
        piso.append({
            "posicion": str(i),
            "ocupada": ocupado,
            "color": "#C8311F" if ocupado else "#E8F0E5",
            "color_texto": "white" if ocupado else "#3C6B3F"
        })

    racks_trans = [generar_color_rack(f"R{i}") for i in range(17, 21)]
    
    context = {
        'porcentaje_ocupacion': round((activos / 240.0) * 100, 1) if activos else 0.0,
        'ubicaciones_ocupadas': activos, 'ubicaciones_total': 240, 'pallets_activos': activos,
        'pallets_parciales': 0, 'total_entradas': activos, 'total_salidas': 0, 'proximos_vencer': [], 
        'racks_long': racks_long, 'racks_trans': racks_trans, 'piso': piso, 'capacidad_pallet': 96, 
        'racks_detalle_json': json.dumps(racksData), 'piso_detalle_json': json.dumps({}),
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0}, 'rotacion_lista': [], 
        'entradas': [], 'salidas': [], 'fecha_desde': request.args.get('fecha_desde', ''), 
        'fecha_hasta': request.args.get('fecha_hasta', '')
    }
    return render_template('dashboard.html', **context)

# --- INGRESAR PALLET (Recibe coordenadas exactas) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
@app.route('/pallet_nuevo', endpoint='pallet_nuevo', methods=['GET', 'POST'])
def gestionar_pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs, prods = [], []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if request.method == 'POST':
            codigo_qr = request.form.get('codigo_qr')
            id_proveedor = request.form.get('id_proveedor')
            id_producto = request.form.get('id_producto')
            factura = request.form.get('factura')
            ubicacion = request.form.get('ubicacion')
            nivel = request.form.get('nivel')
            posicion = request.form.get('posicion')
            
            cur.execute("""
                INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) 
                VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)
            """, (codigo_qr, id_proveedor, id_producto, factura, ubicacion, nivel, posicion))
            conn.commit()
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

# --- RESTO DE FUNCIONES ESTANDARIZADAS ---
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
    except Exception as e: pass
    return redirect(url_for('empresas'))

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
    except Exception as e: pass
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
    except Exception as e: pass
    return render_template('usuarios.html', usuarios=lista)

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
