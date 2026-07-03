import os
from flask import Flask, render_template, request, url_for, redirect, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')

# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Implementa aquí tu lógica de validación de usuario
        if request.form.get('usuario') == 'admin': # Ejemplo
            session['usuario'] = 'admin'
            session['nombre'] = 'Admin'
            session['rol'] = 'Administrador'
            return redirect(url_for('dashboard'))
        flash('Credenciales incorrectas.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD Y MAPA ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html') # Usa 'mapa' o 'dashboard' según tu estructura final

# --- GESTIÓN DE PALLETS ---
@app.route('/nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    return render_template('nuevo_pallet.html')

@app.route('/pallet_creado')
def pallet_creado():
    return render_template('pallet_creado.html')

@app.route('/ver_pallet/<id_pallet>')
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    return render_template('pallet_editar.html', id_pallet=id_pallet)

@app.route('/consulta_pallet', methods=['GET', 'POST'])
def consulta_pallet():
    return render_template('consulta_pallet.html')

@app.route('/buscar_pallets')
def buscar_pallets():
    return render_template('buscar_pallets.html')

@app.route('/historial_pallet/<id_pallet>')
def historial_pallet(id_pallet):
    return render_template('historial_pallet.html', id_pallet=id_pallet)

@app.route('/descargar_qr/<id_pallet>')
def descargar_qr(id_pallet):
    return "Descarga QR"

# --- PICKING Y DESPACHO ---
@app.route('/picking', methods=['GET', 'POST'])
def picking():
    return render_template('picking.html')

@app.route('/resultado_picking', methods=['POST'])
def resultado_picking():
    return render_template('resultado_picking.html')

# --- ADMINISTRACIÓN (PRODUCTOS, EMPRESAS, USUARIOS) ---
@app.route('/productos', methods=['GET', 'POST'])
def productos():
    return render_template('productos.html')

@app.route('/editar_producto/<id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    return render_template('editar_producto.html', id_producto=id_producto)

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
