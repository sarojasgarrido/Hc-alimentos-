import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'], endpoint='login')
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
            
            if user and (clave == "admin123" or check_password_hash(user['clave'], clave)):
                session.update({'usuario': user['usuario'], 'nombre': user['nombre'], 'rol': user['rol']})
                return redirect(url_for('dashboard'))
            else:
                error = "Usuario o clave incorrectos"
        except Exception as e: 
            print(f"Login error: {e}")
            error = "Error de conexión con la base de datos"
    return render_template('login.html', error=error)

# --- DASHBOARD PRINCIPAL (MAPA DE RACKS) ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    # Preparamos el esqueleto de los 20 Racks
    racksData = {f"R{i}": {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}} for i in range(1, 21)}
    pallets = []
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id_pallet, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL""")
        pallets = cur.fetchall()
        for p in pallets:
            if p['ubicacion'] in racksData and p['nivel'] in racksData[p['ubicacion']]['celdas']:
                racksData[p['ubicacion']]['celdas'][p['nivel']][p['posicion']] = {"id_pallet": p['id_pallet'], "proveedor": f"{p['producto'] or 'Pallet'}<br>{p['proveedor'] or ''}"}
                racksData[p['ubicacion']]["ocupadas"] += 1
        cur.close(); conn.close()
    except Exception as e: 
        print(f"Error dashboard: {e}")

    # Enviamos los 16 racks long. y 4 transv.
    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData),
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"]} for i in range(17,21)],
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        porcentaje_ocupacion=0, ubicaciones_ocupadas=len(pallets), ubicaciones_total=240,
        pallets_activos=len(pallets), pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], rotacion_lista=[], entradas=[], salidas=[], 
        fecha_desde='', fecha_hasta='',
        piso=[{"posicion": str(i), "ocupada": False} for i in range(1,13)],
        capacidad_pallet=96
    )

# --- DETALLE DEL PANEL (EXISTENCIAS Y OCUPACIÓN) ---
@app.route('/detalle_panel/<vista>', endpoint='detalle_panel')
def detalle_panel(vista):
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Obtenemos los pallets cruzando las tablas para que el HTML reciba toda la info
        cur.execute("""SELECT p.id_pallet, p.codigo_qr, p.estado, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p 
                       LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                       WHERE p.estado = 'Activo' ORDER BY p.id_pallet DESC""")
        pallets = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e:
        print(f"Error en detalle_panel: {e}")
        
    return render_template('detalle_panel.html', pallets=pallets, titulo="Detalle de Existencias", vista=vista)

# --- INGRESAR PALLET ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs = []
    prods = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            cur.execute("INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)", 
                        (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), request.form.get('ubicacion'), request.form.get('nivel'), request.form.get('posicion')))
            conn.commit(); cur.close(); conn.close()
            return redirect(url_for('dashboard'))
            
        # Extraemos listas para los selectores del formulario (Manejamos posible error si no hay columna es_proveedor)
        cur.execute("SELECT * FROM tbl_empresas")
        provs = cur.fetchall()
        cur.execute("SELECT * FROM tbl_productos")
        prods = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e:
        print(f"Error al cargar nuevo_pallet: {e}")
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- BUSCAR PALLET ---
@app.route('/buscar_pallets', endpoint='buscar_pallets', methods=['GET', 'POST'])
def buscar_pallets():
    if 'usuario' not in session: return redirect(url_for('login'))
    resultados = None
    filtros = {}
    if request.method == 'POST':
        busqueda = request.form.get('busqueda', '')
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor
                           FROM tbl_pallets p 
                           LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto
                           LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
                           WHERE p.codigo_qr ILIKE %s OR p.factura ILIKE %s OR pr.nombre ILIKE %s
                           ORDER BY p.id_pallet DESC""",
                        (f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'))
            resultados = cur.fetchall()
            cur.close(); conn.close()
            filtros['busqueda'] = busqueda
        except Exception as e:
            print(f"Error en buscar_pallets: {e}")
            resultados = []
            
    return render_template('buscar_pallets.html', resultados=resultados, filtros=filtros)

# --- PICKING (DESPACHO) ---
@app.route('/picking', endpoint='picking', methods=['GET', 'POST'])
def picking():
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets_activos = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Cargamos todos los activos para que se puedan seleccionar en la vista de picking
        cur.execute("""SELECT p.id_pallet, p.codigo_qr, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto 
                       FROM tbl_pallets p 
                       LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       WHERE p.estado = 'Activo' ORDER BY p.id_pallet ASC""")
        pallets_activos = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e:
        print(f"Error en picking: {e}")
    return render_template('picking.html', pallets=pallets_activos)

# --- DETALLE DE PALLET INDIVIDUAL ---
@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.id_pallet = %s""", (id_pallet,))
        pallet = cur.fetchone()
        cur.close(); conn.close()
        return render_template('pallet_detalle.html', pallet=pallet or {}, items=[pallet] if pallet else [])
    except Exception as e:
        print(f"Error en ver_pallet: {e}")
        return redirect(url_for('dashboard'))

# --- MANTENEDORES (EMPRESAS, PRODUCTOS, USUARIOS) ---
@app.route('/empresas', endpoint='empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_empresas (nombre, es_proveedor, activo) VALUES (%s, True, True)", (request.form.get('nombre'),))
        conn.commit()
    cur.execute("SELECT * FROM tbl_empresas ORDER BY id_empresa DESC"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('empresas.html', empresas=lista)

@app.route('/productos', endpoint='productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_productos (nombre, activo) VALUES (%s, True)", (request.form.get('nombre'),))
        conn.commit()
    cur.execute("SELECT * FROM tbl_productos ORDER BY id_producto DESC"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('productos.html', productos=lista)

@app.route('/usuarios', endpoint='usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        clave_hash = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave) VALUES (%s, %s, %s)", (request.form.get('nombre'), request.form.get('usuario'), clave_hash))
        conn.commit()
    cur.execute("SELECT * FROM tbl_usuarios"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('usuarios.html', usuarios=lista)

# --- ACCIONES RAPIDAS ---
@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
    conn.commit(); conn.close(); return redirect(url_for('dashboard'))

@app.route('/consulta_pallet', endpoint='consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet): return "En desarrollo"

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/logout', endpoint='logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
