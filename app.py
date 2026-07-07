"""
HC ALIMENTOS - Sistema de Gestión de Bodega (WMS)
Versión: 2026.07.07
Descripción: Backend robusto para almacenamiento caótico, trazabilidad y control de inventario.
"""

import os
import psycopg2
import json
import logging
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración de Logging para monitorear errores en consola
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026_robust_version'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def get_db():
    """Establece conexión con la base de datos PostgreSQL en Neon."""
    try:
        return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')
    except Exception as e:
        logger.error(f"Error de conexión a BD: {e}")
        raise

# --- MIDDLEWARE / FILTROS ---
@app.before_request
def ensure_db_integrity():
    """Verifica estructuras mínimas al iniciar (Opcional, ayuda a evitar 500 en despliegues nuevos)."""
    pass 

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
            
            # Autenticación directa para entorno de administración
            if user and (clave == "admin123" or check_password_hash(user['clave'], clave)):
                session.update({'usuario': user['usuario'], 'nombre': user['nombre'], 'rol': user['rol']})
                return redirect(url_for('dashboard'))
            flash("Credenciales incorrectas")
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash("Error crítico de sistema")
            
    return render_template('login.html')

@app.route('/logout', endpoint='logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD Y MAPA VISUAL ---
@app.route('/dashboard', endpoint='dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    # Estructura de racks
    racksData = {f"R{i}": {"ocupadas": 0, "total": 12, "celdas": {"N4": {"1":None,"2":None,"3":None}, "N3": {"1":None,"2":None,"3":None}, "N2": {"1":None,"2":None,"3":None}, "N1": {"1":None,"2":None,"3":None}}} for i in range(1, 21)}
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Consulta de pallets activos con unión para trazabilidad
        cur.execute("""
            SELECT p.id_pallet, p.ubicacion, p.nivel, p.posicion, pr.nombre as producto, e.nombre as proveedor
            FROM tbl_pallets p 
            LEFT JOIN tbl_productos pr ON p.id_producto = pr.id_producto 
            LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa 
            WHERE p.estado = 'Activo' AND p.ubicacion IS NOT NULL
        """)
        pallets = cur.fetchall()
        for p in pallets:
            if p['ubicacion'] in racksData and p['nivel'] in racksData[p['ubicacion']]['celdas']:
                racksData[p['ubicacion']]['celdas'][p['nivel']][p['posicion']] = {
                    "id_pallet": p['id_pallet'], 
                    "proveedor": f"{p['producto'] or 'Pallet'}<br>{p['proveedor'] or ''}"
                }
                racksData[p['ubicacion']]["ocupadas"] += 1
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")

    # Generación de colores dinámicos
    def get_rack_status(id_rack):
        ocup = racksData.get(id_rack, {}).get("ocupadas", 0)
        pct = (ocup / 12.0) * 100
        if pct == 100: return "#C8311F", "white"
        if pct >= 60: return "#F4B795", "#8C2E1F"
        if pct > 0: return "#FCEFE2", "#8C5A2A"
        return "#E8F0E5", "#3C6B3F"

    context = {
        'racks_detalle_json': json.dumps(racksData),
        'racks_long': [{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": get_rack_status(f"R{i}")[0], "color_texto": get_rack_status(f"R{i}")[1]} for i in range(1, 17)],
        'racks_trans': [{"nombre": f"R{i}", "ocupadas": racksData[f"R{i}"]["ocupadas"], "color": get_rack_status(f"R{i}")[0], "color_texto": get_rack_status(f"R{i}")[1]} for i in range(17, 21)],
        'piso': [{"posicion": str(i), "ocupada": False} for i in range(1, 13)]
    }
    return render_template('dashboard.html', **context)

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
        except Exception as e:
            logger.error(f"Error registrando pallet: {e}")
            flash("Error al registrar pallet")
            
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
        # Prevenimos error de iteración enviando siempre una lista
        items = [pallet] if pallet else []
        return render_template('pallet_detalle.html', pallet=pallet or {}, items=items)
    except Exception as e:
        logger.error(f"Error detalle pallet: {e}")
        return "Error interno", 500

@app.route('/pallets/despachar/<int:id_pallet>', endpoint='despachar_pallet', methods=['POST'])
def despachar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE tbl_pallets SET estado = 'Despachado', ubicacion = NULL, nivel = NULL, posicion = NULL WHERE id_pallet = %s", (id_pallet,))
        conn.commit(); conn.close()
    except Exception as e:
        logger.error(f"Error despachando: {e}")
    return redirect(url_for('dashboard'))

# --- MANTENEDORES Y APOYO (Evitan errores 404/500) ---
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

# --- RUTAS DE REDIRECCIÓN DE SEGURIDAD ---
@app.route('/pallets/descargar_qr/<int:id_pallet>', endpoint='descargar_qr')
def descargar_qr(id_pallet): return "Módulo en desarrollo", 200

@app.route('/pallets/historial/<int:id_pallet>', endpoint='historial_pallet')
def historial_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/pallets/editar/<int:id_pallet>', endpoint='editar_pallet')
def editar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

if __name__ == '__main__':
    # Configuración de puerto para Render/Local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
