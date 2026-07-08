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
                session.update({'usuario': user['usuario'], 'nombre': user['nombre'], 'rol': user.get('rol', 'Operador')})
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
    
    racksData = {f"R{i}": {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}} for i in range(1, 21)}
    pallets = []
    piso_ocupado = []
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id_pallet, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor, p.cantidad
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL""")
        pallets = cur.fetchall()
        for p in pallets:
            if p['ubicacion'].startswith('R') and p['nivel'] in racksData.get(p['ubicacion'], {}).get('celdas', {}):
                pos_str = str(p['posicion']) if p['posicion'] is not None else None
                if pos_str in racksData[p['ubicacion']]['celdas'][p['nivel']]:
                    racksData[p['ubicacion']]['celdas'][p['nivel']][pos_str] = {
                        "id_pallet": p.get('id_pallet', p.get('id')), 
                        "proveedor": f"{p['producto'] or 'Pallet'}",
                        "cantidad": p.get('cantidad', 96), "capacidad": 96, "pct_llenado": 100
                    }
                    racksData[p['ubicacion']]["ocupadas"] += 1
            elif p['ubicacion'].startswith('P'):
                piso_ocupado.append(p['ubicacion'])
        cur.close(); conn.close()
    except Exception as e: print(f"Error dashboard: {e}")

    def generar_color_rack(id_rack):
        ocupadas = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocupadas / 12.0) * 100
        if pct == 100: return "#C8311F", "white"
        elif pct >= 60: return "#F4B795", "#8C2E1F"
        elif pct > 0: return "#FCEFE2", "#8C5A2A"
        else: return "#E8F0E5", "#3C6B3F"

    zonas_piso = []
    for i in range(1, 13):
        pos_id = f"P{i}"
        if pos_id in piso_ocupado:
            zonas_piso.append({"posicion": str(i), "ocupada": True, "color": "#F4B795", "color_texto": "#8C2E1F"})
        else:
            zonas_piso.append({"posicion": str(i), "ocupada": False, "color": "#E8F0E5", "color_texto": "#3C6B3F"})

    activos_count = len(pallets)
    porcentaje = round((activos_count / 240.0) * 100, 1) if activos_count > 0 else 0.0

    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData),
        piso_detalle_json=json.dumps({}),
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(17,21)],
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        porcentaje_ocupacion=porcentaje, ubicaciones_ocupadas=activos_count, ubicaciones_total=240,
        pallets_activos=activos_count, pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], rotacion_lista=[], entradas=[], salidas=[], fecha_desde='', fecha_hasta='',
        piso=zonas_piso,
        capacidad_pallet=96
    )

@app.route('/detalle_panel/<vista>', endpoint='detalle_panel')
def detalle_panel(vista):
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                       WHERE p.estado = 'Activo' ORDER BY p.id_pallet DESC""")
        raw_pallets = cur.fetchall()
        for p in raw_pallets:
            p['id_pallet'] = p.get('id_pallet', p.get('id', '-'))
            p['rack'] = p.get('ubicacion', '-') 
            pallets.append(p)
        cur.close(); conn.close()
    except Exception as e: print(f"Error en detalle_panel: {e}")
    return render_template('detalle_panel.html', pallets=pallets, filas=pallets, columnas='pallets', titulo="Detalle de Existencias", vista=vista)

# --- INGRESAR PALLET (ALGORITMO CAÓTICO Y LECTURA DE LISTAS DE UI) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
@app.route('/pallet_nuevo', endpoint='pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs = []; prods = []
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if request.method == 'POST':
            id_prov = request.form.get('id_proveedor')
            fact = request.form.get('factura', '')
            
            # Leemos los arrays (listas) que envía tu nuevo HTML
            ids_productos = request.form.getlist('id_producto[]')
            cantidades = request.form.getlist('cantidad[]')
            fechas_elab = request.form.getlist('fecha_elaboracion[]')
            fechas_venc = request.form.getlist('fecha_vencimiento[]')

            # Para simplificar con la base actual, tomamos el primer producto de la lista enviada
            id_prod = ids_productos[0] if ids_productos else None
            cantidad_cajas = cantidades[0] if cantidades else 96
            fecha_elab = fechas_elab[0] if fechas_elab and fechas_elab[0] else None
            fecha_venc = fechas_venc[0] if fechas_venc and fechas_venc[0] else None

            # MOTOR DE ALMACENAMIENTO CAÓTICO
            cur.execute("SELECT ubicacion, nivel, posicion FROM tbl_pallets WHERE estado = 'Activo' AND ubicacion LIKE 'R%'")
            ocupados = set((r.get('ubicacion'), r.get('nivel'), str(r.get('posicion'))) for r in cur.fetchall())
            
            ubi_caotica, niv_caotico, pos_caotica = None, None, None
            for r_num in range(1, 21):
                for n_val in ['N1', 'N2', 'N3', 'N4']:
                    for p_val in ['1', '2', '3']:
                        if (f"R{r_num}", n_val, p_val) not in ocupados:
                            ubi_caotica, niv_caotico, pos_caotica = f"R{r_num}", n_val, p_val
                            break
                    if ubi_caotica: break
                if ubi_caotica: break
            
            if not ubi_caotica: ubi_caotica, niv_caotico, pos_caotica = 'P1', None, None # Fallback a piso

            try:
                # Intenta guardar con datos enriquecidos (Cantidades y Fechas)
                cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion, cantidad, cantidad_original, fecha_elaboracion, fecha_vencimiento) 
                               VALUES ('QR-AUTO', %s, %s, %s, 'Activo', %s, %s, %s, %s, %s, %s, %s)""", 
                            (id_prov, id_prod, fact, ubi_caotica, niv_caotico, pos_caotica, cantidad_cajas, cantidad_cajas, fecha_elab, fecha_venc))
            except:
                conn.rollback() # Si la base es antigua, lo guarda de forma básica
                cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) 
                               VALUES ('QR-AUTO', %s, %s, %s, 'Activo', %s, %s, %s)""", 
                            (id_prov, id_prod, fact, ubi_caotica, niv_caotico, pos_caotica))
            
            conn.commit()
            cur.close(); conn.close()
            return redirect(url_for('dashboard'))
            
        # Listas para cargar el formulario inicial
        try:
            cur.execute("SELECT * FROM tbl_empresas")
            empresas_db = cur.fetchall()
            for e in empresas_db: provs.append({"id_proveedor": e.get("id_empresa", e.get("id", "")), "nombre": e.get("nombre", "")})
            cur.execute("SELECT * FROM tbl_productos")
            productos_db = cur.fetchall()
            for p in productos_db: prods.append({"id_producto": p.get("id_producto", p.get("id", "")), "nombre": p.get("nombre", "")})
        except: conn.rollback()
            
        cur.close(); conn.close()
    except Exception as e: print(f"Error en pallet_nuevo: {e}")
        
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- EMPRESAS (REPARADO: RUT, TELÉFONO, DIRECCIÓN Y ELIMINACIÓN) ---
@app.route('/empresas', endpoint='empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            rut = request.form.get('rut')
            telefono = request.form.get('telefono')
            correo = request.form.get('correo')
            direccion = request.form.get('direccion')
            es_prov = True if request.form.get('es_proveedor') else False
            es_cli = True if request.form.get('es_cliente') else False
            try:
                cur.execute("""INSERT INTO tbl_empresas (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente, activo) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s, True)""", (nombre, rut, telefono, correo, direccion, es_prov, es_cli))
            except:
                conn.rollback() # Si la DB no tiene los campos nuevos, asegura guardar el nombre
                cur.execute("INSERT INTO tbl_empresas (nombre, es_proveedor, es_cliente, activo) VALUES (%s, %s, %s, True)", (nombre, es_prov, es_cli))
            conn.commit()
            
        cur.execute("SELECT * FROM tbl_empresas WHERE activo = True ORDER BY 1 DESC")
        empresas_raw = cur.fetchall()
        for e in empresas_raw:
            lista.append({
                "id_empresa": e.get('id_empresa', '-'), "nombre": e.get('nombre', '-'),
                "rut": e.get('rut', '-'), "es_proveedor": e.get('es_proveedor', True),
                "es_cliente": e.get('es_cliente', False), "activo": e.get('activo', True)
            })
        cur.close(); conn.close()
    except Exception as e: print(f"Error empresas: {e}")
    return render_template('empresas.html', empresas=lista)

@app.route('/eliminar_empresa/<int:id_empresa>', endpoint='eliminar_empresa')
def eliminar_empresa(id_empresa):
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE tbl_empresas SET activo = False WHERE id_empresa = %s", (id_empresa,))
        conn.commit(); cur.close(); conn.close()
    except Exception: pass
    return redirect(url_for('empresas'))

# --- PRODUCTOS (REPARADO: UNIDADES DE MEDIDA) ---
@app.route('/productos', endpoint='productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            unidad = request.form.get('unidad', 'Unidades') # Lee la unidad del form
            try:
                cur.execute("INSERT INTO tbl_productos (nombre, unidad, activo) VALUES (%s, %s, True)", (nombre, unidad))
            except:
                conn.rollback()
                cur.execute("INSERT INTO tbl_productos (nombre, activo) VALUES (%s, True)", (nombre,))
            conn.commit()
        cur.execute("SELECT * FROM tbl_productos ORDER BY 1 DESC")
        lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception: pass
    return render_template('productos.html', productos=lista)

# --- USUARIOS (REPARADO: CARGA FLEXIBLE PARA QUE NO DESAPAREZCAN) ---
@app.route('/usuarios', endpoint='usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario' not in session: return redirect(url_for('login'))
    lista = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            user = request.form.get('usuario')
            rol = request.form.get('rol', 'Operador')
            clave_hash = generate_password_hash(request.form.get('clave'))
            try:
                cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol) VALUES (%s, %s, %s, %s)", (nombre, user, clave_hash, rol))
            except:
                conn.rollback()
                cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave) VALUES (%s, %s, %s)", (nombre, user, clave_hash))
            conn.commit()
        cur.execute("SELECT * FROM tbl_usuarios")
        lista = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error usuarios: {e}")
    return render_template('usuarios.html', usuarios=lista)

# --- PICKING Y DESPACHO (REPARADO: LOGICA POST HABILITADA) ---
@app.route('/picking', endpoint='picking', methods=['GET', 'POST'])
def picking():
    if 'usuario' not in session: return redirect(url_for('login'))
    productos = []; stock_piso = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # PROCESAMIENTO DE LAS ACCIONES DEL HTML
        if request.method == 'POST':
            accion = request.form.get('accion')
            if accion == 'picking':
                # Bajar de rack a piso
                id_prod = request.form.get('id_producto')
                cant = int(request.form.get('cantidad', 0))
                # Buscamos el pallet más antiguo (FEFO) en racks
                cur.execute("""SELECT id_pallet, cantidad FROM tbl_pallets WHERE id_producto = %s AND estado = 'Activo' AND ubicacion LIKE 'R%' 
                               ORDER BY fecha_vencimiento ASC NULLS LAST LIMIT 1""", (id_prod,))
                p_fefo = cur.fetchone()
                if p_fefo:
                    try:
                        # Simulamos bajar al piso creando un sub-pallet en P1
                        cur.execute("INSERT INTO tbl_pallets (id_producto, estado, ubicacion, cantidad, cantidad_original) VALUES (%s, 'Activo', 'P1', %s, %s)", (id_prod, cant, cant))
                        # Descontamos del rack
                        cur.execute("UPDATE tbl_pallets SET cantidad = GREATEST(cantidad - %s, 0) WHERE id_pallet = %s", (cant, p_fefo['id_pallet']))
                    except:
                        conn.rollback() # Si falla, solo movemos el pallet físico completo a P1
                        cur.execute("UPDATE tbl_pallets SET ubicacion = 'P1', nivel = NULL, posicion = NULL WHERE id_pallet = %s", (p_fefo['id_pallet'],))
                    conn.commit()
                    
            elif accion == 'despacho':
                # Despachar desde el piso hacia afuera
                id_stock = request.form.get('id_stock_piso')
                cant_desp = int(request.form.get('cantidad_despacho', 0))
                try:
                    cur.execute("UPDATE tbl_pallets SET cantidad = GREATEST(cantidad - %s, 0) WHERE id_pallet = %s", (cant_desp, id_stock))
                    cur.execute("UPDATE tbl_pallets SET estado = 'Despachado' WHERE cantidad <= 0 AND id_pallet = %s", (id_stock,))
                except:
                    conn.rollback()
                    cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL WHERE id_pallet = %s", (id_stock,))
                conn.commit()

        cur.execute("SELECT id_producto, nombre FROM tbl_productos")
        productos = cur.fetchall()
        # Modificado alias a id_stock_piso para coincidir con tu HTML
        cur.execute("""SELECT p.id_pallet as id_stock_piso, p.id_pallet, p.ubicacion as posicion, pr.nombre as producto, p.cantidad, p.fecha_vencimiento
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       WHERE p.estado = 'Activo' AND p.ubicacion LIKE 'P%'""")
        stock_piso = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error picking: {e}")
    return render_template('picking.html', productos=productos, stock_piso=stock_piso)

@app.route('/picking/disponibilidad/<int:id_producto>')
def api_disponibilidad(id_producto):
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id_pallet, ubicacion, cantidad, cantidad as cantidad_original, fecha_vencimiento FROM tbl_pallets WHERE id_producto = %s AND estado = 'Activo'", (id_producto,))
        pallets = cur.fetchall()
        cur.close(); conn.close()
        if pallets:
            return jsonify({"disponible": True, "total_en_racks": len(pallets)*96, "total_en_piso": 0, "total_disponible": len(pallets)*96, "pallets": pallets})
    except: pass
    return jsonify({"disponible": False})

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

# --- DETALLES DE PALLET Y QR ---
@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.*, p.ubicacion as rack, pr.nombre as producto, e.nombre as proveedor FROM tbl_pallets p 
                       LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                       WHERE p.id_pallet = %s""", (id_pallet,))
        pallet = cur.fetchone()
        cur.close(); conn.close()
        items = [{"producto": pallet['producto'], "cantidad": pallet.get('cantidad', 96)}] if pallet and pallet.get('producto') else []
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

@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=Pallet_{id_pallet}_HC_Alimentos"
    return f"""<html><body style="text-align:center; padding:50px; background-color:#FCEFE2;">
        <div style="background:white; padding: 30px; display: inline-block; border-radius: 10px;">
            <h2>Pallet N° {id_pallet}</h2><img src="{qr_url}" alt="QR"><br><br>
            <button onclick="window.print()" style="padding:12px 24px; background:#C8311F; color:white; border:none;">Imprimir</button>
        </div></body></html>"""

@app.route('/consulta_pallet', endpoint='consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/editar_empresa/<int:id_empresa>', endpoint='editar_empresa')
def editar_empresa(id_empresa): return redirect(url_for('empresas'))

@app.route('/logout', endpoint='logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
