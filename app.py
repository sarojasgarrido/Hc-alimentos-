import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')

# Render proporciona DATABASE_URL automáticamente
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Aquí validación contra tbl_usuarios
        session['usuario'] = request.form.get('usuario')
        session['nombre'] = 'Admin'
        session['rol'] = 'Administrador'
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

# --- PALLETS ---
@app.route('/nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    return render_template('pallet_nuevo.html')

@app.route('/pallet_creado')
def pallet_creado():
    return render_template('pallet_creado.html')

@app.route('/pallets/detalle/<id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    return render_template('pallet_editar.html', id_pallet=id_pallet)

@app.route('/consulta_pallet')
def consulta_pallet():
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets():
    return render_template('buscar_pallets.html')

@app.route('/historial_pallet/<id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet_2.html', id_pallet=id_pallet)

# --- OPERACIONES ---
@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html')

@app.route('/picking/resultado', methods=['POST'])
def resultado_picking():
    return render_template('picking_resultado.html')

@app.route('/mapa')
def mapa():
    return render_template('mapa.html')

# --- ADMINISTRACIÓN ---
@app.route('/productos', methods=['GET', 'POST'])
def productos():
    return render_template('productos.html')

@app.route('/editar_producto/<id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    return render_template('producto_editar.html', id_producto=id_producto)

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    return render_template('empresas.html')

@app.route('/editar_empresa/<id_empresa>', methods=['GET', 'POST'])
def editar_empresa(id_empresa):
    return render_template('empresa_editar.html', id_empresa=id_empresa)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    return render_template('usuarios.html')

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', columnas=vista)

if __name__ == '__main__':
    app.run(debug=True)
