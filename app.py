import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario'] = request.form.get('usuario')
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', 
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        rotacion_lista=[], entradas=[], salidas=[], proximos_vencer=[], 
        racks_long=[], piso=[], racks_trans=[])

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista)

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", 
                    (request.form.get('id_proveedor'), request.form.get('factura')))
        conn.commit()
        return redirect(url_for('dashboard'))
    cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores")
    prov = cur.fetchall()
    cur.execute("SELECT id_producto, nombre FROM tbl_productos")
    prod = cur.fetchall()
    cur.close(); conn.close()
    return render_template('pallet_nuevo.html', proveedores=prov, productos=prod)

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_productos (nombre, codigo, unidad, activo) VALUES (%s, %s, %s, True)", 
                    (request.form.get('nombre'), request.form.get('codigo'), request.form.get('unidad')))
        conn.commit()
    cur.execute("SELECT * FROM tbl_productos")
    lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('productos.html', productos=lista)

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

# Otras rutas necesarias para evitar BuildError
@app.route('/consulta_pallet')
def consulta_pallet(): return render_template('consulta_pallet.html')
@app.route('/picking')
def picking(): return render_template('picking.html')
@app.route('/empresas')
def empresas(): return render_template('empresas.html')

if __name__ == '__main__':
    app.run(debug=True)
