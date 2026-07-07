import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- RUTAS PRINCIPALES ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', 
        pct_rot={'Alta':0, 'Media':0, 'Baja':0, 'Sin':0}, rotacion_lista=[], 
        entradas=[], salidas=[], proximos_vencer=[], racks_long=[], 
        piso=[], racks_trans=[], capacidad_pallet=0, 
        racks_detalle_json=json.dumps({}), piso_detalle_json=json.dumps({}))

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", 
                    (request.form.get('id_proveedor'), request.form.get('factura')))
        conn.commit()
    cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores")
    provs = cur.fetchall()
    cur.execute("SELECT id_producto, nombre FROM tbl_productos")
    prods = cur.fetchall()
    cur.close(); conn.close()
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

@app.route('/buscar_pallets')
def buscar_pallets():
    # Se agrega la variable 'filtros' que faltaba
    return render_template('buscar_pallets.html', resultados=None, filtros={'factura': ''})

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        clave = generate_password_hash(request.form.get('clave'))
        cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo) VALUES (%s, %s, %s, 'Operador', True)", 
                    (request.form.get('nombre'), request.form.get('usuario'), clave))
        conn.commit()
    cur.execute("SELECT * FROM tbl_usuarios")
    lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('usuarios.html', usuarios=lista)

# --- RUTAS DE NAVEGACIÓN ---
@app.route('/detalle_panel/<vista>')
def detalle_panel(vista): return render_template('detalle_panel.html', titulo=vista)
@app.route('/consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')
@app.route('/picking')
def picking(): return render_template('picking.html')
@app.route('/empresas')
def empresas(): return render_template('empresas.html')
@app.route('/productos')
def productos(): return render_template('productos.html')
@app.route('/')
def login(): return render_template('login.html')

if __name__ == '__main__':
    app.run()
