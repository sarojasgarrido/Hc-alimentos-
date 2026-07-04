import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Nota: Aquí deberías validar el usuario contra tbl_usuarios
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD Y VISTAS ---
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista, filas=[])

# --- PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    return render_template('pallet_nuevo.html')

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])

@app.route('/consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet():
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets():
    return render_template('buscar_pallets.html', resultados=None, filtros={})

@app.route('/historial_pallet/<int:id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<int:id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    return render_template('pallet_editar.html', pallet={'id_pallet': id_pallet}, items=[], proveedores=[], productos=[])

@app.route('/despachar_pallet/<int:id_pallet>', methods=['POST'])
def despachar_pallet(id_pallet):
    return redirect(url_for('ver_pallet', id_pallet=id_pallet))

@app.route('/descargar_qr/<int:id_pallet>')
def descargar_qr(id_pallet):
    return "Descarga de QR pendiente"

# --- PICKING Y PRODUCTOS ---
@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html', productos=[], stock_piso=[])

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
    cur.close()
    conn.close()
    return render_template('productos.html', productos=lista)

@app.route('/editar_producto/<int:id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    return render_template('producto_editar.html', producto={'id_producto': id_producto})

@app.route('/eliminar_producto/<int:id_producto>')
def eliminar_producto(id_producto):
    return redirect(url_for('productos'))

# --- EMPRESAS Y USUARIOS ---
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
    cur.close()
    conn.close()
    return render_template('empresas.html', empresas=lista)

@app.route('/editar_empresa/<int:id_empresa>', methods=['GET', 'POST'])
def editar_empresa(id_empresa):
    return render_template('empresa_editar.html', empresa={'id_empresa': id_empresa})

@app.route('/eliminar_empresa/<int:id_empresa>')
def eliminar_empresa(id_empresa):
    return redirect(url_for('empresas'))

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
    cur.close()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/desactivar_usuario/<int:id_usuario>')
def desactivar_usuario(id_usuario):
    return redirect(url_for('usuarios'))

@app.route('/cambiar_clave_usuario/<int:id_usuario>', methods=['POST'])
def cambiar_clave_usuario(id_usuario):
    return redirect(url_for('usuarios'))

if __name__ == '__main__':
    app.run(debug=True)
