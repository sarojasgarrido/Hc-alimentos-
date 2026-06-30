import os
from flask import Flask, render_template, request, url_for, redirect, flash, session

app = Flask(__name__)
# Esta clave es obligatoria para manejar sesiones (login)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')

# --- 1. RUTA DE LOGIN (CORRECCIÓN ERROR 405) ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')

        # --- AQUI VA TU CONSULTA A LA BASE DE DATOS ---
        # Ejemplo: if usuario == 'admin' and clave == 'admin123':
        if usuario == 'admin' and clave == 'admin123': # Cambia esto por tu consulta real
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.')
    
    return render_template('login.html')

# --- 2. RUTA DE DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    # Aquí cargarías tus datos para el dashboard
    return render_template('dashboard.html')

# --- 3. RUTA DE DETALLE PANEL (SOLUCIÓN ERROR 500) ---
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
        # filas = tu_conexion.execute("SELECT ...").fetchall()

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

# --- 4. RUTA DE DETALLE PALLET ---
@app.route('/ver_pallet/<id_pallet>')
def ver_pallet(id_pallet):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return f"Detalle del pallet {id_pallet}"

# --- 5. LOGOUT ---
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
