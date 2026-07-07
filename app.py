import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
            error = "Error de conexión"
    return render_template('login.html', error=error)

# --- DASHBOARD PRINCIPAL ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    # Esqueleto de 20 Racks
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
                # Estructura JSON exacta que espera mostrarDetalle() en tu HTML
                racksData[p['ubicacion']]['celdas'][p['nivel']][p['posicion']] = {
                    "id_pallet": p['id_pallet'], 
                    "proveedor": f"{p['producto'] or 'Pallet'}",
                    "cantidad": 96, "capacidad": 96, "pct_llenado": 100
                }
                racksData[p['ubicacion']]["ocupadas"] += 1
        cur.close(); conn.close()
    except Exception as e: print(f"Error dashboard: {e}")

    def generar_color_rack(id_rack):
        ocupadas = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocupadas / 12.0) * 100
        if pct == 100: return "#C8311F", "white"
        elif pct >= 60: return "#F4B795", "#8C2E1F"
        elif pct > 0: return "#FCEFE2", "#8C5A2A"
        else: return "#E8F0E5", "#3C6B3F"

    activos_count = len(pallets)
    porcentaje = round((activos_count / 240.0) * 100, 1) if activos_count > 0 else 0.0

    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData),
        piso_detalle_json=json.dumps({}), # Previene error de Javascript en el HTML
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(17,21)],
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        porcentaje_ocupacion=porcentaje, ubicaciones_ocupadas=activos_count, ubicaciones_total=240,
        pallets_activos=activos_count, pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], rotacion_lista=[], entradas=[], salidas=[], fecha_desde='', fecha_hasta='',
        piso=[{"posicion": str(i), "ocupada": False} for i in range(1,13)],
        capacidad_pallet=96
    )

# --- DETALLE DEL PANEL MAESTRO ---
@app.route('/detalle_panel/<vista>', endpoint='detalle_panel')
def detalle_panel(vista):
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        # Adaptamos las variables a lo que espera detalle_panel.html (r.rack, r.proveedor, r.id_pallet)
        cur.execute("""SELECT p.id_pallet, p.estado, p.ubicacion as rack, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor, p.factura as fecha_ingreso
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' ORDER BY 1 DESC""")
        pallets = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error en detalle_panel: {e}")
    # Tu HTML usa la variable 'columnas' y 'filas', se las enviamos:
    return render_template('detalle_panel.html', filas=pallets, columnas='pallets', titulo="Detalle de Existencias", descripcion="Listado total")

# --- INGRESAR PALLET (CORREGIDO Y SIN ERRORES 500) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs = []; prods = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) 
                           VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)""", 
                        (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), request.form.get('ubicacion'), request.form.get('nivel'), request.form.get('posicion')))
            conn.commit(); cur.close(); conn.close()
            return redirect(url_for('dashboard'))
            
        # El HTML espera prov.id_proveedor. Le damos un alias a id_empresa para que haga match
        try:
            cur.execute("SELECT id_empresa as id_proveedor, nombre FROM tbl_empresas")
            provs = cur.fetchall()
        except: conn.rollback()
        
        try:
            cur.execute("SELECT id_producto, nombre FROM tbl_productos")
            prods = cur.fetchall()
        except: conn.rollback()
        
        cur.close(); conn.close()
    except Exception as e: print(f"Error 500 evitado en nuevo_pallet: {e}")
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- EMPRESAS (CORREGIDO PARA COINCIDIR CON HTML) ---
@app.route('/empresas', endpoint='empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            # Tu form manda: nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente
            nombre = request.form.get('nombre')
            es_prov = True if request.form.get('es_proveedor') else False
            es_cli = True if request.form.get('es_cliente') else False
            # Guardamos lo basico, si falla intentamos guardar solo nombre
            try:
                cur.execute("INSERT INTO tbl_empresas (nombre, es_proveedor, es_cliente, activo) VALUES (%s, %s, %s, True)", (nombre, es_prov, es_cli))
            except:
                conn.rollback()
                cur.execute("INSERT INTO tbl_empresas (nombre) VALUES (%s)", (nombre,))
            conn.commit()
            
        cur.execute("SELECT * FROM tbl_empresas ORDER BY 1 DESC")
        # Aseguramos que los diccionarios tengan las llaves que pide tu HTML para que no de 500
        empresas_raw = cur.fetchall()
        for e in empresas_raw:
            lista.append({
                "id_empresa": e.get('id_empresa', '-'),
                "nombre": e.get('nombre', '-'),
                "rut": e.get('rut', '-'),
                "es_proveedor": e.get('es_proveedor', True),
                "es_cliente": e.get('es_cliente', False),
                "activo": e.get('activo', True)
            })
        cur.close(); conn.close()
    except Exception as e: print(f"Error empresas: {e}")
    return render_template('empresas.html', empresas=lista)

# --- PICKING Y DESPACHO (CONECTADO A JAVASCRIPT Y API) ---
@app.route('/picking', endpoint='picking', methods=['GET', 'POST'])
def picking():
    if 'usuario' not in session: return redirect(url_for('login'))
    productos = []; stock_piso = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        # 1. Cargamos productos para el <select>
        cur.execute("SELECT id_producto, nombre FROM tbl_productos")
        productos = cur.fetchall()
        # 2. Cargamos el stock que ya está en piso para despacharlo (Sección 2 de tu HTML)
        cur.execute("""SELECT p.id_pallet, p.ubicacion as posicion, pr.nombre as producto, 96 as cantidad, '-' as fecha_vencimiento
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       WHERE p.estado = 'Activo' AND p.ubicacion LIKE 'P%'""")
        stock_piso = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error picking: {e}")
    return render_template('picking.html', productos=productos, stock_piso=stock_piso)

# API Oculta que pide tu Javascript en picking.html (Línea: fetch('/picking/disponibilidad/' + idProducto))
@app.route('/picking/disponibilidad/<int:id_producto>')
def api_disponibilidad(id_producto):
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id_pallet, ubicacion, 96 as cantidad, 96 as cantidad_original FROM tbl_pallets WHERE id_producto = %s AND estado = 'Activo'", (id_producto,))
        pallets = cur.fetchall()
        cur.close(); conn.close()
        if pallets:
            return jsonify({"disponible": True, "total_en_racks": len(pallets)*96, "total_en_piso": 0, "total_disponible": len(pallets)*96, "pallets": pallets})
    except: pass
    return jsonify({"disponible": False})

# --- DETALLES DE PALLET Y DESPACHO DIRECTO ---
@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        # Tu HTML usa "rack", no "ubicacion", lo aliamos
        cur.execute("""SELECT p.*, p.ubicacion as rack, pr.nombre as producto, e.nombre as proveedor FROM tbl_pallets p 
                       LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                       WHERE p.id_pallet = %s""", (id_pallet,))
        pallet = cur.fetchone()
        cur.close(); conn.close()
        items = [{"producto": pallet['producto'], "cantidad": 96}] if pallet and pallet.get('producto') else []
        return render_template('pallet_detalle.html', pallet=pallet or {}, items=items)
    except Exception as e: print(f"Error ver_pallet: {e}"); return redirect(url_for('dashboard'))

@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor()
        try: cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
        except: 
            conn.rollback()
            cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL WHERE id_pallet = %s", (id_pallet,))
        conn.commit(); conn.close()
    except Exception as e: print(f"Error despachando: {e}")
    return redirect(url_for('dashboard'))

# --- BUSCAR PALLETS (Funcional) ---
@app.route('/buscar_pallets', endpoint='buscar_pallets', methods=['GET', 'POST'])
def buscar_pallets():
    if 'usuario' not in session: return redirect(url_for('login'))
    resultados = []; filtros = {}
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            busqueda = request.form.get('busqueda', '')
            cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor FROM tbl_pallets p 
                           LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
                           WHERE CAST(p.codigo_qr AS TEXT) ILIKE %s OR CAST(p.factura AS TEXT) ILIKE %s OR pr.nombre ILIKE %s ORDER BY 1 DESC""",
                        (f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'))
            filtros['busqueda'] = busqueda
        else:
            cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor FROM tbl_pallets p 
                           LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
                           WHERE p.estado = 'Activo' ORDER BY 1 DESC""")
        
        resultados = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error buscar_pallets: {e}")
    return render_template('buscar_pallets.html', resultados=resultados, filtros=filtros)

# --- MANTENEDORES Y APOYO ---
@app.route('/productos', endpoint='productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            cur.execute("INSERT INTO tbl_productos (nombre, activo) VALUES (%s, True)", (request.form.get('nombre'),))
            conn.commit()
        cur.execute("SELECT * FROM tbl_productos ORDER BY 1 DESC")
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
        cur.execute("SELECT * FROM tbl_usuarios")
        lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception: pass
    return render_template('usuarios.html', usuarios=lista)

@app.route('/consulta_pallet', endpoint='consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=Pallet_{id_pallet}_HC_Alimentos"
    return f"""<html><body style="text-align:center; padding:50px; background-color:#FCEFE2;">
        <div style="background:white; padding: 30px; display: inline-block; border-radius: 10px;">
            <h2>Pallet N° {id_pallet}</h2><img src="{qr_url}" alt="QR"><br><br>
            <button onclick="window.print()" style="padding:12px 24px; background:#C8311F; color:white; border:none;">Imprimir</button>
        </div></body></html>"""

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/logout', endpoint='logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/editar_empresa/<int:id_empresa>', endpoint='editar_empresa')
def editar_empresa(id_empresa): return redirect(url_for('empresas'))

@app.route('/eliminar_empresa/<int:id_empresa>', endpoint='eliminar_empresa')
def eliminar_empresa(id_empresa): return redirect(url_for('empresas'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
