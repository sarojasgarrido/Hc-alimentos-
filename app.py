import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')
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

# --- RUTAS ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario'] = 'Admin' # Simulación de login
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
    
    # Valores inicializados para evitar el error 'undefined' en el template
    contexto = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0,
        'total_salidas': 0, 'proximos_vencer': [], 'fecha_desde': '',
        'fecha_hasta': '', 'racks_long': [], 'racks_trans': [], 'piso': [],
        'racks_detalle_json': '{}', 'piso_detalle_json': '{}',
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': []
    }
    return render_template('dashboard.html', **contexto)

@app.route('/nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    return render_template('pallet_nuevo.html')

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

@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html')

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    return render_template('productos.html')

@app.route('/producto_editar/<id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    return render_template('producto_editar.html', id_producto=id_producto)

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    return render_template('empresas.html')

@app.route('/empresa_editar/<id_empresa>', methods=['GET', 'POST'])
def editar_empresa(id_empresa):
    return render_template('empresa_editar.html', id_empresa=id_empresa)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    return render_template('usuarios.html')

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', columnas=vista)

@app.route('/historial_pallet/<id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet_2.html', id_pallet=id_pallet)

@app.route('/mapa')
def mapa():
    return render_template('mapa.html')

if __name__ == '__main__':
    app.run(debug=True)
