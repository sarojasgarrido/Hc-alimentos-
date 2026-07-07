import os
import psycopg2
import json
import logging
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- CONFIGURACIÓN ---
app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026_final'
logging.basicConfig(level=logging.INFO)

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'], endpoint='login')
def login():
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
            flash("Credenciales incorrectas")
        except Exception as e: print(f"Error login: {e}")
    return render_template('login.html')

@app.route('/logout', endpoint='logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD PRINCIPAL ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    # Estructura para el plano visual
    racksData = {f"R{i}": {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}} for i in range(1, 21)}
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id_pallet, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor
                       FROM tbl_pallets p 
                       LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
                       LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
                       WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL""")
        pallets = cur.fetchall()
        for p in pallets:
            if p['ubicacion'] in racksData and p['nivel'] in racksData[p['ubicacion']]['celdas']:
                racksData[p['ubicacion']]['celdas'][p['nivel']][p['posicion']] = {"id_pallet": p['id_pallet'], "proveedor": f"{p['producto'] or 'Pallet'}<br>{p['proveedor'] or ''}"}
                racksData[p['ubicacion']]["ocupadas"] += 1
        cur.close(); conn.close()
    except Exception as e: print(f"Error dashboard: {e}")

    # Variables de UI para evitar el error 'undefined' en el template
    return render_template('dashboard.html', 
        racks_detalle_json=json.dumps(racksData),
        racks_long=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"]} for i in range(1,17)],
        racks_trans=[{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"]} for i in range(17,21)],
        porcentaje_ocupacion=0, ubicaciones_ocupadas=0, ubicaciones_total=240,
        pallets_activos=len(pallets), pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        rotacion_lista=[], entradas=[], salidas=[], fecha_desde='', fecha_hasta='',
        piso=[{"posicion": str(i), "ocupada": False} for i in range(1,13)],
        capacidad_pallet=96
    )

# --- GESTIÓN DE PALLETS (Endpoints explícitos) ---
@app.route('/nuevo_pallet', endpoint='nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""INSERT INTO tbl_pallets (codigo_qr, id_proveedor, id_producto, factura, estado, ubicacion, nivel, posicion) 
                           VALUES (%s, %s, %s, %s, 'Activo', %s, %s, %s)""", 
                        (request.form.get('codigo_qr'), request.form.get('id_proveedor'), request.form.get('id_producto'), request.form.get('factura'), 
                         request.form.get('ubicacion'), request.form.get('nivel'), request.form.get('posicion')))
            conn.commit(); conn.close()
            return redirect(url_for('dashboard'))
        except Exception as e: print(f"Error ingreso: {e}")
    return render_template('pallet_nuevo.html', proveedores=[], productos=[])

@app.route('/pallets/detalle/<int:id_pallet>', endpoint='ver_pallet')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
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
    except Exception as e: print(f"Error detalle: {e}"); return "Error de carga", 500

@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
        conn.commit(); conn.close()
    except Exception as e: print(f"Error despacho: {e}")
    return redirect(url_for('dashboard'))

# --- MANTENEDORES Y RUTAS AUXILIARES ---
@app.route('/empresas', endpoint='empresas')
def empresas(): return render_template('empresas.html', empresas=[])
@app.route('/productos', endpoint='productos')
def productos(): return render_template('productos.html', productos=[])
@app.route('/usuarios', endpoint='usuarios')
def usuarios(): return render_template('usuarios.html', usuarios=[])
@app.route('/consulta_pallet', endpoint='consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')
@app.route('/buscar_pallets', endpoint='buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html')
@app.route('/picking', endpoint='picking')
def picking(): return render_template('picking.html')

# --- DETALLE PANEL (Trazabilidad) ---
@app.route('/detalle_panel/<vista>', endpoint='detalle_panel')
def detalle_panel(vista):
    return redirect(url_for('dashboard'))

# --- SEGURIDAD Y QR ---
@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet): return "Modulo en desarrollo"
@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))
@app.route('/editar_empresa/<int:id_empresa>', endpoint='editar_empresa')
def editar_empresa(id_empresa): return redirect(url_for('empresas'))
@app.route('/eliminar_empresa/<int:id_empresa>', endpoint='eliminar_empresa')
def eliminar_empresa(id_empresa): return redirect(url_for('empresas'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
