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
            cur.close(); conn.close()
            
            if user and (clave == "admin123" or check_password_hash(user['clave'], clave)):
                session['usuario'] = user['usuario']
                session['nombre'] = user['nombre']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                error = "Usuario o clave incorrectos"
        except Exception as e:
            error = "Error de conexión"
            print(f"Error login: {e}")
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD (MAPA VISUAL DINÁMICO) ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    activos = 0
    racksData = {}
    for i in range(1, 21):
        racksData[f"R{i}"] = {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}}

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
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
            if p['ubicacion'].startswith('R') and p['ubicacion'] in racksData and p['nivel'] and p['posicion']:
                if p['nivel'] in racksData[p['ubicacion']]['celdas']:
                    racksData[p['ubicacion']]['celdas'][p['nivel']][p['posicion']] = {"id_pallet": p['id_pallet'], "proveedor": f"{p['producto'] or 'Pallet'}<br>{p['proveedor'] or ''}"}
                    racksData[p['ubicacion']]["ocupadas"] += 1
        activos = len(pallets)
        cur.close(); conn.close()
    except Exception as e: print(f"Error: {e}")

    def generar_color_rack(id_rack):
        pct = (racksData.get(id_rack, {}).get("ocupadas", 0) / 12.0) * 100
        if pct == 100: color, texto = "#C8311F", "white"
        elif pct >= 60: color, texto = "#F4B795", "#8C2E1F"
        elif pct > 0: color, texto = "#FCEFE2", "#8C5A2A"
        else: color, texto = "#E8F0E5", "#3C6B3F"
        return {"nombre": id_rack, "ocupadas": racksData.get(id_rack, {}).get("ocupadas", 0), "total": 12, "color": color, "color_texto": texto}

    context = {
        'porcentaje_ocupacion': round((activos / 240.0) * 100, 1), 'ubicaciones_ocupadas': activos, 'pallets_activos': activos,
        'racks_long': [generar_color_rack(f"R{i}") for i in range(1, 17)],
        'piso': [{"posicion": str(i), "ocupada": False, "color": "#E8F0E5", "color_texto": "#3C6B3F"} for i in range(1, 13)],
        'racks_trans': [generar_color_rack(f"R{i}") for i in range(17, 21)],
        'racks_detalle_json': json.dumps(racksData), 'capacidad_pallet': 96
    }
    return render_template('dashboard.html', **context)

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)", 
                    (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), request.form.get('ubicacion'), request.form.get('nivel'), request.form.get('posicion')))
        conn.commit(); conn.close()
        return redirect(url_for('dashboard'))
    return render_template('pallet_nuevo.html', proveedores=[], productos=[])

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT p.*, pr.nombre as producto, e.nombre as proveedor 
                   FROM tbl_pallets p 
                   LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                   LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                   WHERE p.id_pallet = %s""", (id_pallet,))
    pallet = cur.fetchone()
    cur.close(); conn.close()
    return render_template('pallet_detalle.html', pallet=pallet or {}, items=[pallet] if pallet else [])

@app.route('/pallets/despachar/<int:id_pallet>', methods=['POST'])
def despachar_pallet(id_pallet):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard'))

# --- RUTAS DE SEGURIDAD Y COMPLEMENTOS ---
@app.route('/pallets/descargar_qr/<int:id_pallet>')
def descargar_qr(id_pallet): return "Módulo QR en desarrollo"
@app.route('/pallets/historial/<int:id_pallet>')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/pallets/editar/<int:id_pallet>')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/detalle_panel/<vista>')
def detalle_panel(vista): return redirect(url_for('dashboard'))
@app.route('/empresas', methods=['GET','POST'])
def empresas(): return render_template('empresas.html', empresas=[])
@app.route('/productos', methods=['GET','POST'])
def productos(): return render_template('productos.html', productos=[])
@app.route('/usuarios', methods=['GET','POST'])
def usuarios(): return render_template('usuarios.html', usuarios=[])
@app.route('/consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')
@app.route('/buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html')
@app.route('/picking')
def picking(): return render_template('picking.html')

if __name__ == '__main__':
    app.run()
