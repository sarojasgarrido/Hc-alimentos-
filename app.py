import os
from flask import Flask, render_template, request, url_for, redirect, flash, session
app = Flask(__name__)
# Usamos la variable de entorno de Render, o una clave por defecto para desarrollo
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')

# --- RUTA DE LOGIN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')

        # Lógica de validación (Reemplaza los datos de prueba por tu base de datos)
        if usuario == 'admin' and clave == 'admin123':
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.')
    
    return render_template('login.html')

# --- RUTA DE DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# --- RUTA DE DETALLE PANEL (Solución al error 500) ---
@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    filas = []
    titulo = ""
    descripcion = ""

    # Lógica según la vista
    if vista == 'ocupacion':
        titulo = "Detalle de Ocupación"
        descripcion = "Estado actual de los racks"
    elif vista == 'activos':
        titulo = "Pallets Activos"
        descripcion = "Listado de pallets en proceso"
    elif vista == 'parciales':
        titulo = "Stock en Piso"
        descripcion = "Pallets con stock parcial"
    elif vista == 'ubicaciones':
        titulo = "Gestión de Ubicaciones"
        descripcion = "Detalle de rack, nivel y posición"

    return render_template('detalle_panel.html', 
                           titulo=titulo, 
                           descripcion=descripcion, 
                           filas=filas, 
                           columnas=vista)

# --- RUTA VER PALLET ---
@app.route('/ver_pallet/<id_pallet>')
def ver_pallet(id_pallet):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return f"Detalle del pallet {id_pallet}"

# --- LOGOUT ---
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
