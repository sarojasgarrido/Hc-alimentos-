import os
from flask import Flask, render_template, request, url_for
# Importa aquí tu objeto de base de datos, por ejemplo: from database import db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_segura')

# --- TUS OTRAS RUTAS (dashboard, etc) YA EXISTENTES ---
@app.route('/')
def index():
    return "Bienvenido"

@app.route('/dashboard')
def dashboard():
    # Tu lógica actual del dashboard
    return render_template('dashboard.html')

# --- RUTA QUE FALTABA Y QUE CAUSABA EL ERROR ---
@app.route('/detalle_panel/<vista>')
def detalle_panel(vista):
    filas = []
    titulo = ""
    descripcion = ""

    # Lógica según la vista enviada desde el dashboard
    if vista == 'ocupacion':
        titulo = "Detalle de Ocupación"
        descripcion = "Estado actual de racks y espacios"
        # AQUÍ TU CONSULTA SQL (ejemplo: filas = db.execute("SELECT * FROM ubicaciones"))
        
    elif vista == 'activos':
        titulo = "Pallets Activos"
        descripcion = "Listado de pallets en proceso"
        # AQUÍ TU CONSULTA SQL (ejemplo: filas = db.execute("SELECT * FROM pallets WHERE estado='Activo'"))
        
    elif vista == 'parciales':
        titulo = "Stock en Piso"
        descripcion = "Pallets con stock parcial en piso"
        # AQUÍ TU CONSULTA SQL
        
    elif vista == 'ubicaciones':
        titulo = "Gestión de Ubicaciones"
        descripcion = "Detalle de rack, nivel y posición"
        # AQUÍ TU CONSULTA SQL
        
    else:
        titulo = "Detalle"
        descripcion = "Información del sistema"

    # Retornamos los datos al template que subiste
    return render_template('detalle_panel.html', 
                           titulo=titulo, 
                           descripcion=descripcion, 
                           filas=filas, 
                           columnas=vista)

# --- OTRAS RUTAS ---
@app.route('/ver_pallet/<id_pallet>')
def ver_pallet(id_pallet):
    return f"Detalle del pallet {id_pallet}"

if __name__ == '__main__':
    app.run(debug=True)
