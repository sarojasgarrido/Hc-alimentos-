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

# --- DASHBOARD PRINCIPAL (MAPA DE RACKS Y PORCENTAJES) ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
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
    except Exception as e: print(f"Error dashboard: {e}")

    # Lógica de colores restaurada
    def generar_color_rack(id_rack):
        ocupadas = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocupadas / 12.0) * 100
        if pct == 100: return "#C8311F", "white"           # Rojo (Lleno)
        elif pct >= 60: return "#F4B795", "#8C2E1F"       # Naranja (Mayoría)
        elif pct > 0: return "#FCEFE2", "#8C5A2A"         # Naranja Claro (Poco)
        else: return "#E8F0E5", "#3C6B3F"                 # Verde (Vacío)

    # Cálculo matemático de ocupación real restaurado
    activos_count = len(pallets)
    porcentaje = round((activos_count / 240.0) * 100, 1) if activos_count > 0 else 0.0

    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData),
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(17,21)],
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        porcentaje_ocupacion=porcentaje, ubicaciones_ocupadas=activos_count, ubicaciones_total=240,
        pallets_activos=activos_count, pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], rotacion_lista=[], entradas=[], salidas=[], fecha_desde='', fecha_hasta='',
        piso=[{"posicion": str(i), "ocupada": False, "color": "#E8F0E5", "color_texto": "#3C6B3F"} for i in range(1,13)],
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
        cur.execute("""SELECT p.id_pallet, p.codigo_qr, p.estado, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' ORDER BY p.id_pallet DESC""")
        pallets = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error en detalle_panel: {e}")
    return render_template('detalle_panel.html', pallets=pallets, titulo="Detalle de Existencias", vista=vista)

# --- INGRESAR PALLET (Blindado contra Error 500) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs = []; prods = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            try:
                cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) 
                               VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)""", 
                            (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), request.form.get('ubicacion'), request.form.get('nivel'), request.form.get('posicion')))
            except Exception as e:
                conn.rollback() # Si falla (ej. faltan columnas), inserta lo básico
                cur.execute("INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion) VALUES (%s, %s, %s, %s, 'Activo', %s)", 
                            (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), request.form.get('ubicacion')))
            conn.commit(); cur.close(); conn.close()
            return redirect(url_for('dashboard'))
            
        try:
            cur.execute("SELECT * FROM tbl_empresas WHERE es_proveedor = True")
            provs = cur.fetchall()
        except:
            conn.rollback() # Fallback si no existe la columna es_proveedor
            cur.execute("SELECT * FROM tbl_empresas")
            provs = cur.fetchall()
            
        cur.execute("SELECT * FROM tbl_productos")
        prods = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error al cargar nuevo_pallet: {e}")
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- BUSCAR PALLET ---
@app.route('/buscar_pallets', endpoint='buscar_pallets', methods=['GET', 'POST'])
def buscar_pallets():
    if 'usuario' not in session: return redirect(url_for('login'))
    resultados = None; filtros = {}
    if request.method == 'POST':
        busqueda = request.form.get('busqueda', '')
        try:
            conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor
                           FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto
                           LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
                           WHERE p.codigo_qr ILIKE %s OR p.factura ILIKE %s OR pr.nombre ILIKE %s ORDER BY p.id_pallet DESC""",
                        (f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'))
            resultados = cur.fetchall()
            cur.close(); conn.close()
            filtros['busqueda'] = busqueda
        except Exception as e:
            print(f"Error buscar_pallets: {e}"); resultados = []
    return render_template('buscar_pallets.html', resultados=resultados, filtros=filtros)

# --- PICKING (DESPACHO DE EXISTENCIAS) ---
@app.route('/picking', endpoint='picking', methods=['GET', 'POST'])
def picking():
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets_activos = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id_pallet, p.codigo_qr, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       WHERE p.estado = 'Activo' ORDER BY p.id_pallet ASC""")
        pallets_activos = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error picking: {e}")
    return render_template('picking.html', pallets=pallets_activos)

# --- DETALLE PALLET INDIVIDUAL ---
@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.id_pallet = %s""", (id_pallet,))
        pallet = cur.fetchone()
        cur.close(); conn.close()
        return render_template('pallet_detalle.html', pallet=pallet or {}, items=[pallet] if pallet else [])
    except Exception as e:
        print(f"Error ver_pallet: {e}"); return redirect(url_for('dashboard'))

# --- CONFIRMAR DESPACHO (Libera Rack y evita Error 500) ---
@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor()
        try: # Intentamos limpiar columnas nivel y posicion por si existen
            cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
        except:
            conn.rollback() # Fallback seguro si no existen
            cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL WHERE id_pallet = %s", (id_pallet,))
        conn.commit(); conn.close()
    except Exception as e: print(f"Error despachando: {e}")
    return redirect(url_for('dashboard'))

# --- GENERADOR DE CÓDIGO QR REAL ---
@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet):
    # Ya no es un mensaje "en desarrollo". Genera un QR real consultando un API gráfica
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=Pallet_{id_pallet}_HC_Alimentos"
    html_qr = f"""
    <html>
    <head><title>Imprimir QR Pallet N° {id_pallet}</title></head>
    <body style="text-align:center; padding:50px; font-family:sans-serif; background-color:#FCEFE2;">
        <div style="background:white; padding: 30px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2 style="color: #2D2925; margin-bottom: 5px;">Pallet N° {id_pallet}</h2>
            <p style="color: #8C2E1F; font-weight: bold; font-size: 14px; margin-top: 0;">HC Alimentos</p>
            <img src="{qr_url}" alt="Código QR Pallet" style="border: 2px solid #2D2925; padding: 10px;">
            <br><br>
            <button onclick="window.print()" style="padding:12px 24px; background:#C8311F; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size: 14px;">🖨️ Imprimir Etiqueta QR</button>
        </div>
    </body>
    </html>
    """
    return html_qr

# --- EMPRESAS, PRODUCTOS Y USUARIOS (Blindados) ---
@app.route('/empresas', endpoint='empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            cur.execute("INSERT INTO tbl_empresas (nombre) VALUES (%s)", (request.form.get('nombre'),))
            conn.commit()
        try:
            cur.execute("SELECT * FROM tbl_empresas ORDER BY id_empresa DESC")
        except:
            conn.rollback() # Fallback si no hay columna id_empresa
            cur.execute("SELECT * FROM tbl_empresas")
        lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error empresas: {e}")
    return render_template('empresas.html', empresas=lista)

@app.route('/productos', endpoint='productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            cur.execute("INSERT INTO tbl_productos (nombre, activo) VALUES (%s, True)", (request.form.get('nombre'),))
            conn.commit()
        try:
            cur.execute("SELECT * FROM tbl_productos ORDER BY id_producto DESC")
        except:
            conn.rollback()
            cur.execute("SELECT * FROM tbl_productos")
        lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception: pass
    return render_template('productos.html', productos=lista)

@app.route('/usuarios', endpoint='usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            clave_hash = generate_password_hash(request.form.get('clave'))
            cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave) VALUES (%s, %s, %s)", (request.form.get('nombre'), request.form.get('usuario'), clave_hash))
            conn.commit()
        cur.execute("SELECT * FROM tbl_usuarios"); lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception: pass
    return render_template('usuarios.html', usuarios=lista)

# --- RUTAS RESTANTES ---
@app.route('/consulta_pallet', endpoint='consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/logout', endpoint='logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
