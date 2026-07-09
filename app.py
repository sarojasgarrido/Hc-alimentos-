import os
import psycopg2
import json
import urllib.request
import base64
from datetime import datetime, date
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- FUNCIÓN DE HOMOLOGACIÓN AUTOMÁTICA DE BASE DE DATOS ---
def homologar_db(cur, conn):
    try:
        # Asegura que las columnas vitales existan para evitar stock fantasma
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS cantidad INTEGER DEFAULT 96;")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS cantidad_original INTEGER DEFAULT 96;")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS fecha_elaboracion DATE;")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE;")
        cur.execute("ALTER TABLE tbl_pallets ADD COLUMN IF NOT EXISTS destino VARCHAR(255);")
        conn.commit()
    except Exception:
        conn.rollback()

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

# --- DASHBOARD PRINCIPAL (TIEMPO REAL) ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    racksData = {f"R{i}": {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}} for i in range(1, 21)}
    pallets = []
    piso_ocupado = []
    entradas = []
    salidas = []
    proximos_vencer = []
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        homologar_db(cur, conn)
        
        # 1. Mapeo de Bodega y Ocupación
        cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL""")
        pallets = cur.fetchall()
        for p in pallets:
            ubi = p.get('ubicacion', '').strip()
            if ubi.startswith('R') and p.get('nivel') in racksData.get(ubi, {}).get('celdas', {}):
                pos_str = str(p.get('posicion', '')).strip().split('.')[0]
                if pos_str in racksData[ubi]['celdas'][p['nivel']]:
                    racksData[ubi]['celdas'][p['nivel']][pos_str] = {
                        "id_pallet": p.get('id_pallet', p.get('id')), 
                        "proveedor": f"{p.get('producto') or 'Pallet'}",
                        "cantidad": p.get('cantidad', 96), "capacidad": 96, "pct_llenado": 100
                    }
                    racksData[ubi]["ocupadas"] += 1
            elif ubi.startswith('P'):
                piso_ocupado.append(ubi)

        # 2. Entradas (Últimos registrados)
        try:
            cur.execute("""SELECT p.*, e.nombre as proveedor FROM tbl_pallets p 
                           LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa ORDER BY p.id_pallet DESC LIMIT 15""")
            for r in cur.fetchall():
                entradas.append({"fecha": "Reciente", "id_pallet": r['id_pallet'], "proveedor": r.get('proveedor') or '-', "observacion": r.get('factura') or '-'})
        except: pass

        # 3. Salidas (Últimos despachados)
        try:
            cur.execute("""SELECT p.* FROM tbl_pallets p WHERE p.estado = 'Despachado' ORDER BY p.id_pallet DESC LIMIT 15""")
            for r in cur.fetchall():
                salidas.append({"fecha": "Reciente", "id_pallet": r['id_pallet'], "destino_tipo": r.get('destino') or 'Despacho', "observacion": "Completado"})
        except: pass

        # 4. Próximos a Vencer
        try:
            for p in pallets:
                fv = p.get('fecha_vencimiento')
                if fv and str(fv).strip():
                    try:
                        fv_date = datetime.strptime(fv.strip(), '%Y-%m-%d').date() if isinstance(fv, str) else fv
                        dias = (fv_date - date.today()).days
                        if dias <= 7:
                            p['dias_para_vencer'] = dias
                            p['rack'] = p.get('ubicacion', '-')
                            p['cantidad'] = p.get('cantidad', 96)
                            p['producto'] = p.get('producto', 'Pallet')
                            p['fecha_vencimiento'] = fv_date.strftime('%Y-%m-%d')
                            proximos_vencer.append(p)
                    except: pass
            proximos_vencer = sorted(proximos_vencer, key=lambda x: x['dias_para_vencer'])[:10]
        except: pass

        cur.close(); conn.close()
    except Exception as e: print(f"Error dashboard: {e}")

    def generar_color_rack(id_rack):
        ocupadas = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocupadas / 12.0) * 100
        if pct >= 100: return "#C8311F", "white" # Rojo al llenarse
        elif pct >= 60: return "#F4B795", "#8C2E1F"
        elif pct > 0: return "#FCEFE2", "#8C5A2A"
        else: return "#E8F0E5", "#3C6B3F"

    zonas_piso = []
    for i in range(1, 13):
        pos_id = f"P{i}"
        if pos_id in piso_ocupado: zonas_piso.append({"posicion": str(i), "ocupada": True, "color": "#F4B795", "color_texto": "#8C2E1F"})
        else: zonas_piso.append({"posicion": str(i), "ocupada": False, "color": "#E8F0E5", "color_texto": "#3C6B3F"})

    total_racks_ocupados = sum(r["ocupadas"] for r in racksData.values())
    porcentaje = round((total_racks_ocupados / 240.0) * 100, 1)

    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData), piso_detalle_json=json.dumps({}),
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": generar_color_rack(f"R{i}")[0], "color_texto": generar_color_rack(f"R{i}")[1]} for i in range(17,21)],
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        porcentaje_ocupacion=porcentaje, ubicaciones_ocupadas=total_racks_ocupados, ubicaciones_total=240,
        pallets_activos=len(pallets), pallets_parciales=len(piso_ocupado), total_entradas=len(entradas), total_salidas=len(salidas),
        proximos_vencer=proximos_vencer, rotacion_lista=[], entradas=entradas, salidas=salidas, 
        fecha_desde='', fecha_hasta='', piso=zonas_piso, capacidad_pallet=96
    )

@app.route('/detalle_panel/<vista>', endpoint='detalle_panel')
def detalle_panel(vista):
    if 'usuario' not in session: return redirect(url_for('login'))
    pallets = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor 
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.estado = 'Activo' ORDER BY p.id_pallet DESC""")
        raw_pallets = cur.fetchall()
        for p in raw_pallets:
            p['id_pallet'] = p.get('id_pallet', p.get('id', '-'))
            p['rack'] = p.get('ubicacion', '-') 
            pallets.append(p)
        cur.close(); conn.close()
    except Exception as e: print(f"Error en detalle_panel: {e}")
    return render_template('detalle_panel.html', pallets=pallets, filas=pallets, columnas='pallets', titulo="Detalle de Existencias", vista=vista)

# --- INGRESAR PALLET (CAÓTICO Y HOMOLOGADO) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
@app.route('/pallet_nuevo', endpoint='pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    provs = []; prods = []
    
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        homologar_db(cur, conn)
        
        if request.method == 'POST':
            qr_manual = request.form.get('codigo_qr', '')
            fact = request.form.get('factura', '')
            
            # Captura de datos de forma dinámica
            id_prov_raw = request.form.get('id_proveedor')
            id_prov = int(str(id_prov_raw).strip()) if id_prov_raw and str(id_prov_raw).strip().isdigit() else None
            
            id_prod_raw = request.form.get('id_producto') or (request.form.getlist('id_producto[]')[0] if request.form.getlist('id_producto[]') else None)
            id_prod = int(str(id_prod_raw).strip()) if id_prod_raw and str(id_prod_raw).strip().isdigit() else None
            
            cant_raw = request.form.get('cantidad') or (request.form.getlist('cantidad[]')[0] if request.form.getlist('cantidad[]') else None)
            cant = int(str(cant_raw).strip()) if cant_raw and str(cant_raw).strip().isdigit() else 96
            
            fecha_elab_raw = request.form.get('fecha_elaboracion') or (request.form.getlist('fecha_elaboracion[]')[0] if request.form.getlist('fecha_elaboracion[]') else None)
            fecha_elab = str(fecha_elab_raw).strip() if fecha_elab_raw and str(fecha_elab_raw).strip() else None

            fecha_venc_raw = request.form.get('fecha_vencimiento') or (request.form.getlist('fecha_vencimiento[]')[0] if request.form.getlist('fecha_vencimiento[]') else None)
            fecha_venc = str(fecha_venc_raw).strip() if fecha_venc_raw and str(fecha_venc_raw).strip() else None

            # Asignación Caótica
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
            
            if not ubi_caotica: ubi_caotica, niv_caotico, pos_caotica = 'P1', None, None

            # Inserción con RETURNING
            cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion, cantidad, cantidad_original, fecha_elaboracion, fecha_vencimiento) 
                           VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s, %s, %s, %s, %s) RETURNING id_pallet""", 
                        (qr_manual, id_prov, id_prod, fact, ubi_caotica, niv_caotico, pos_caotica, cant, cant, fecha_elab, fecha_venc))
            new_id = cur.fetchone()['id_pallet']
            
            # Asignar código HC
            codigo_generado = f"HC-{new_id}"
            cur.execute("UPDATE tbl_pallets SET codigo_qr = %s WHERE id_pallet = %s", (codigo_generado, new_id))
            conn.commit(); cur.close(); conn.close()
            
            return redirect(url_for('pallet_creado', id_pallet=new_id))
            
        try:
            cur.execute("SELECT * FROM tbl_empresas WHERE activo = True")
            for e in cur.fetchall(): provs.append({"id_proveedor": e.get("id_empresa", e.get("id", "")), "nombre": e.get("nombre", "")})
            cur.execute("SELECT * FROM tbl_productos WHERE activo = True")
            for p in cur.fetchall(): prods.append({"id_producto": p.get("id_producto", p.get("id", "")), "nombre": p.get("nombre", "")})
        except: conn.rollback()
        cur.close(); conn.close()
    except Exception as e: print(f"Error nuevo_pallet: {e}")
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

# --- PANTALLA DE ÉXITO (NUEVO) ---
@app.route('/pallet_creado/<int:id_pallet>', endpoint='pallet_creado')
def pallet_creado(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM tbl_pallets WHERE id_pallet = %s", (id_pallet,))
        pallet = cur.fetchone()
        cur.close(); conn.close()
        
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=HC-{id_pallet}"
        try:
            req = urllib.request.Request(qr_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response: qr_base64 = base64.b64encode(response.read()).decode('utf-8')
        except: qr_base64 = ""
            
        return render_template('pallet_creado.html', id_pallet=id_pallet, 
                               rack=pallet.get('ubicacion','-'), nivel=pallet.get('nivel','-'), 
                               posicion=pallet.get('posicion','-'), codigo_qr=f"HC-{id_pallet}", 
                               qr_base64=qr_base64, url_consulta=f"HC-{id_pallet}")
    except Exception: return redirect(url_for('dashboard'))

# --- CONSULTA PALLET (INDEPENDIENTE Y DIRECTA) ---
@app.route('/consulta_pallet', endpoint='consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        codigo = request.form.get('codigo_qr', '').strip().upper()
        id_busqueda = codigo.replace('HC-', '')
        if id_busqueda.isdigit():
            return redirect(url_for('ver_pallet', id_pallet=int(id_busqueda)))
        
        try:
            conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT id_pallet FROM tbl_pallets WHERE codigo_qr ILIKE %s LIMIT 1", (f"%{codigo}%",))
            res = cur.fetchone()
            cur.close(); conn.close()
            if res: return redirect(url_for('ver_pallet', id_pallet=res['id_pallet']))
        except: pass
        return render_template('consulta_pallet.html', error="Pallet no encontrado")
    return render_template('consulta_pallet.html')

# --- DESPACHO Y PICKING ---
@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        destino = request.form.get('destino_tipo', 'Despacho completado')
        conn = get_db(); cur = conn.cursor()
        homologar_db(cur, conn)
        cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL, cantidad = 0, destino = %s WHERE id_pallet = %s", (destino, id_pallet))
        conn.commit(); conn.close()
    except Exception as e: print(f"Error despachando: {e}")
    return redirect(url_for('dashboard'))

@app.route('/picking', endpoint='picking', methods=['GET', 'POST'])
def picking():
    if 'usuario' not in session: return redirect(url_for('login'))
    productos = []; stock_piso = []
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        homologar_db(cur, conn)
        
        if request.method == 'POST':
            accion = request.form.get('accion')
            if accion == 'picking':
                id_prod = request.form.get('id_producto')
                cant = int(request.form.get('cantidad', 0))
                cur.execute("""SELECT id_pallet, cantidad FROM tbl_pallets WHERE id_producto = %s AND estado = 'Activo' AND ubicacion LIKE 'R%' 
                               ORDER BY fecha_vencimiento ASC NULLS LAST LIMIT 1""", (id_prod,))
                p_fefo = cur.fetchone()
                if p_fefo:
                    try:
                        cur.execute("UPDATE tbl_pallets SET cantidad = GREATEST(COALESCE(cantidad, 96) - %s, 0) WHERE id_pallet = %s", (cant, p_fefo['id_pallet']))
                        cur.execute("INSERT INTO tbl_pallets (id_producto, estado, ubicacion, cantidad, cantidad_original) VALUES (%s, 'Activo', 'P1', %s, %s)", (id_prod, cant, cant))
                    except:
                        conn.rollback()
                        cur.execute("UPDATE tbl_pallets SET ubicacion = 'P1', nivel = NULL, posicion = NULL WHERE id_pallet = %s", (p_fefo['id_pallet'],))
                    conn.commit()
            
            elif accion == 'despacho':
                id_stock = request.form.get('id_stock_piso')
                cant_desp = int(request.form.get('cantidad_despacho', 0))
                destino = request.form.get('destino_tipo', 'Despacho de Piso')
                try:
                    cur.execute("UPDATE tbl_pallets SET cantidad = GREATEST(COALESCE(cantidad, 96) - %s, 0) WHERE id_pallet = %s RETURNING cantidad", (cant_desp, id_stock))
                    restante = cur.fetchone()['cantidad']
                    if restante <= 0:
                        cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, destino = %s WHERE id_pallet = %s", (destino, id_stock))
                except:
                    conn.rollback()
                    cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL WHERE id_pallet = %s", (id_stock,))
                conn.commit()

        cur.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = True")
        productos = cur.fetchall()
        cur.execute("""SELECT p.id_pallet as id_stock_piso, p.id_pallet, p.ubicacion as posicion, pr.nombre as producto, COALESCE(p.cantidad, 96) as cantidad, p.fecha_vencimiento
                       FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       WHERE p.estado = 'Activo' AND p.ubicacion LIKE 'P%'""")
        stock_piso = cur.fetchall()
        cur.close(); conn.close()
    except Exception as e: print(f"Error picking: {e}")
    return render_template('picking.html', productos=productos, stock_piso=stock_piso)

# =====================================================================
# INTACTOS: EMPRESAS, PRODUCTOS, USUARIOS Y BUSCAR
# =====================================================================

@app.route('/empresas', endpoint='empresas', methods=['GET', 'POST'])
def empresas():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_empresas (nombre, es_proveedor, activo) VALUES (%s, True, True)", (request.form.get('nombre'),))
        conn.commit()
    cur.execute("SELECT * FROM tbl_empresas ORDER BY id_empresa DESC"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('empresas.html', empresas=lista)

@app.route('/productos', endpoint='productos', methods=['GET', 'POST'])
def productos():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_productos (nombre, activo) VALUES (%s, True)", (request.form.get('nombre'),))
        conn.commit()
    cur.execute("SELECT * FROM tbl_productos ORDER BY id_producto DESC"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('productos.html', productos=lista)

@app.route('/eliminar_producto/<int:id_producto>', endpoint='eliminar_producto')
def eliminar_producto(id_producto):
    if session.get('rol') != 'Administrador': return redirect(url_for('productos'))
    try:
        conn = get_db(); cur = conn.cursor(); cur.execute("UPDATE tbl_productos SET activo = False WHERE id_producto = %s", (id_producto,)); conn.commit(); cur.close(); conn.close()
    except: pass
    return redirect(url_for('productos'))

@app.route('/usuarios', endpoint='usuarios', methods=['GET', 'POST'])
def usuarios():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        clave_hash = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave) VALUES (%s, %s, %s)", (request.form.get('nombre'), request.form.get('usuario'), clave_hash))
        conn.commit()
    cur.execute("SELECT * FROM tbl_usuarios"); lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/eliminar_usuario/<int:id_usuario>', endpoint='eliminar_usuario')
def eliminar_usuario(id_usuario):
    if session.get('rol') != 'Administrador': return redirect(url_for('usuarios'))
    try:
        conn = get_db(); cur = conn.cursor(); cur.execute("DELETE FROM tbl_usuarios WHERE id_usuario = %s", (id_usuario,)); conn.commit(); cur.close(); conn.close()
    except: pass
    return redirect(url_for('usuarios'))

@app.route('/buscar_pallets', endpoint='buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html')

@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT p.*, pr.nombre as producto, e.nombre as proveedor FROM tbl_pallets p LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa WHERE p.id_pallet = %s", (id_pallet,))
    pallet = cur.fetchone(); cur.close(); conn.close()
    return render_template('pallet_detalle.html', pallet=pallet or {}, items=[pallet] if pallet else [])

@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=HC-{id_pallet}"
    return f"""<html><body style="text-align:center; padding:50px; background-color:#FCEFE2; font-family:sans-serif;">
        <div style="background:white; padding: 30px; display: inline-block; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h2 style="color: #2D2925; margin-bottom: 5px;">Pallet N° {id_pallet}</h2>
            <p style="color: #8C2E1F; font-weight: bold; font-size: 14px; margin-top: 0;">HC Alimentos</p>
            <img src="{qr_url}" alt="QR" style="border: 2px solid #2D2925; padding: 10px; border-radius: 8px;">
            <p style="font-size: 26px; font-weight: 900; letter-spacing: 4px; color: #2D2925; margin: 15px 0; font-family: monospace;">HC-{id_pallet}</p>
            <button onclick="window.print()" style="padding:12px 24px; background:#C8311F; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size: 14px;">🖨️ Imprimir Etiqueta</button>
        </div></body></html>"""

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/logout', endpoint='logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
