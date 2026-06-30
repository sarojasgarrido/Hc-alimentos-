import os
from flask import Flask, render_template, request, url_for, redirect, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')

# --- 1. LOGIN Y LOGOUT ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        # Sustituye admin/admin123 por tu validación de DB
        if usuario == 'admin' and clave == 'admin123':
            session['usuario'] = usuario
            session['rol'] = 'Administrador' # Ejemplo
            session['nombre'] = 'Admin'      # Ejemplo
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 2. DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

# --- 3. GESTIÓN DE PALLETS ---
@app.route('/nuevo_pallet', methods=['GET', 'POST'])
def nuevo_pallet():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_nuevo.html')

@app.route('/pallet_creado')
def pallet_creado():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_creado.html')

@app.route('/ver_pallet/<id_pallet>')
def ver_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_detalle.html', id_pallet=id_pallet)

@app.route('/editar_pallet/<id_pallet>', methods=['GET', 'POST'])
def editar_pallet(id_pallet):
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_editar.html', id_pallet=id_pallet)

@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('detalle_panel.html', columnas=vista)

# --- 4. RUTAS RESTANTES DEL MENÚ (Placeholders para evitar errores) ---
@app.route('/consulta_pallet')
def consulta_pallet():
    return "Página de Consulta Pallet en desarrollo"

@app.route('/buscar_pallets')
def buscar_pallets():
    return "Página de Buscar Pallets en desarrollo"

@app.route('/picking')
def picking():
    return "Página de Picking en desarrollo"

@app.route('/productos')
def productos():
    return "Página de Productos en desarrollo"

@app.route('/empresas')
def empresas():
    return "Página de Empresas en desarrollo"

@app.route('/usuarios')
def usuarios():
    return "Página de Usuarios en desarrollo"

# --- 5. EJECUCIÓN ---
if __name__ == '__main__':
    app.run(debug=True)
