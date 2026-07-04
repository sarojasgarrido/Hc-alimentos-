import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Tu lógica de validación de usuario aquí
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', 
        porcentaje_ocupacion=0, ubicaciones_ocupadas=0, ubicaciones_total=0,
        pallets_activos=0, pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], racks_long=[], piso=[], racks_trans=[], capacidad_pallet=0,
        racks_detalle_json=json.dumps({}), piso_detalle_json=json.dumps({}),
        pct_rot={'Alta':0, 'Media':0, 'Baja':0, 'Sin':0}, rotacion_lista=[], entradas=[], salidas=[])

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista, filas=[])

# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def nuevo_pallet():
    return render_template('pallet_nuevo.html', proveedores=[], productos=[])

@app.route('/pallets/detalle/<int:id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', pallet={}, items=[])

@app.route('/consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet():
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets():
    return render_template('buscar_pallets.html', resultados=None, filtros={}, proveedores=[], productos=[])

@app.route('/historial_pallet/<int:id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet.html', id_pallet=id_pallet, movimientos=[], ubicaciones=[])

@app.route('/editar_pallet/<int:id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    return render_template('editar_pallet.html', pallet={}, items=[], proveedores=[], productos=[])

@app.route('/despachar_pallet/<int:id_pallet>', methods=['POST'])
def despachar_pallet(id_pallet):
    return redirect(url_for('ver_pallet', id_pallet=id_pallet))

# --- PICKING Y PRODUCTOS ---
@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html', productos=[], stock_piso=[])

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    return render_template('productos.html', productos=[])

@app.route('/editar_producto/<int:id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    return render_template('producto_editar.html', producto={})

# --- EMPRESAS Y USUARIOS ---
@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    return render_template('empresas.html', empresas=[])

@app.route('/editar_empresa/<int:id_empresa>', methods=['GET', 'POST'])
def editar_empresa(id_empresa):
    return render_template('empresa_editar.html', empresa={})

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    return render_template('usuarios.html', usuarios=[])

@app.route('/desactivar_usuario/<int:id_usuario>')
def desactivar_usuario(id_usuario):
    return redirect(url_for('usuarios'))

@app.route('/cambiar_clave_usuario/<int:id_usuario>', methods=['POST'])
def cambiar_clave_usuario(id_usuario):
    return redirect(url_for('usuarios'))

if __name__ == '__main__':
    app.run(debug=True)
