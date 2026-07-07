import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    # Conexión optimizada para PostgreSQL en Render
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Implementar validación real aquí
        session['usuario'] = request.form.get('usuario')
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', 
        pct_rot={'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        rotacion_lista=[], entradas=[], salidas=[], proximos_vencer=[], 
        racks_long=[], piso=[], racks_trans=[])

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista, filas=[])

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        try:
            cur.execute("INSERT INTO tbl_pallets (id_proveedor, factura, estado) VALUES (%s, %s, 'Activo')", 
                        (request.form.get('id_proveedor'), request.form.get('factura')))
            conn.commit()
            flash("Pallet registrado")
        except: flash("Error al registrar")
        return redirect(url_for('dashboard'))
    cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores")
    p = cur.fetchall()
    cur.execute("SELECT id_producto, nombre FROM tbl_productos")
    pr = cur.fetchall()
    cur.close(); conn.close()
    return render_template('pallet_nuevo.html', proveedores=p, productos=pr)

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])

@app.route('/consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet(): return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets(): return render_template('buscar_pallets.html', resultados=None, filtros={})

@app.route('/historial_pallet/<int:id_pallet>')
def historial_pallet(id_pallet): return render_template('historial_pallet.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<int:id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet): return render_template('pallet_editar.html', pallet={'id_pallet': id_pallet})

@app.route('/despachar_pallet/<int:id_pallet>', methods=['POST'])
def despachar_pallet(id_pallet): return redirect(url_for('ver_pallet', id_pallet=id_pallet))

# --- PRODUCTOS Y EMPRESAS ---
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

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        cur.execute("INSERT INTO tbl_empresas (nombre, rut) VALUES (%s, %s)", 
                    (request.form.get('nombre'), request.form.get('rut')))
        conn.commit()
    cur.execute("SELECT * FROM tbl_empresas")
    lista = cur.fetchall()
    cur.close(); conn.close()
    return render_template('empresas.html', empresas=lista)

# --- USUARIOS ---
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

if __name__ == '__main__':
    app.run(debug=True)
