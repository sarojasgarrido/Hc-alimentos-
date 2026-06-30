from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from functools import wraps
import os
import json
from db import ejecutar_query

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "una-clave-super-secreta")

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTENTICACIÓN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        clave = request.form["clave"].strip()
        
        # Usamos ejecutar_query (que retorna diccionarios)
        resultados = ejecutar_query("SELECT id_usuario, nombre, clave, rol FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        
        if resultados and check_password_hash(resultados[0]['clave'], clave):
            session["usuario_id"] = resultados[0]["id_usuario"]
            session["nombre"] = resultados[0]["nombre"]
            session["rol"] = resultados[0]["rol"]
            return redirect(url_for("dashboard"))
        return "Login fallido: Usuario o clave incorrectos."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- DASHBOARD (Con valores por defecto para no romper el HTML) ---
@app.route("/")
@login_requerido
def dashboard():
    # Pasamos variables vacías o 0 para que el HTML no explote si no hay datos
    return render_template("dashboard.html",
        porcentaje_ocupacion=0, ubicaciones_ocupadas=0, ubicaciones_total=0,
        pallets_activos=0, pallets_parciales=0, total_entradas=0, total_salidas=0,
        proximos_vencer=[], racks_long=[], racks_trans=[], piso=[],
        racks_detalle_json=json.dumps({}), piso_detalle_json=json.dumps({}),
        pct_rot={'Alta':0, 'Media':0, 'Baja':0, 'Sin':0},
        rotacion_lista=[], entradas=[], salidas=[], 
        fecha_desde="", fecha_hasta=""
    )

# --- RUTAS DE NAVEGACIÓN (Para evitar BuildError) ---
@app.route("/pallets/nuevo")
@login_requerido
def nuevo_pallet():
    return "Ingreso de Pallet - En construcción"

@app.route("/pallets/consulta")
@login_requerido
def consulta_pallet():
    return render_template("consulta_pallet.html")

@app.route("/pallets/buscar")
@login_requerido
def buscar_pallets():
    return "Buscar Pallets - En construcción"

@app.route("/picking")
@login_requerido
def picking():
    return "Picking/Despacho - En construcción"

@app.route("/productos")
@login_requerido
def productos():
    return "Productos - En construcción"

@app.route("/empresas")
@login_requerido
def empresas():
    return "Empresas - En construcción"

@app.route("/usuarios")
@login_requerido
def usuarios():
    return "Usuarios - En construcción"

# --- OTRAS RUTAS ---
@app.route("/pallets/detalle/<int:id_pallet>")
@login_requerido
def ver_pallet(id_pallet):
    return f"Detalle del pallet {id_pallet}"

@app.route("/pallets/historial/<int:id_pallet>")
@login_requerido
def historial_pallet(id_pallet):
    return "Historial..."

@app.route("/pallets/editar/<int:id_pallet>")
@login_requerido
def editar_pallet(id_pallet):
    return "Editar..."

@app.route("/pallets/descargar_qr/<int:id_pallet>")
@login_requerido
def descargar_qr(id_pallet):
    return "Descargando QR..."

@app.route("/despachar/<int:id_pallet>", methods=["POST"])
@login_requerido
def despachar_pallet(id_pallet):
    return "Despachando..."

@app.route("/eliminar_empresa/<int:id_empresa>")
@login_requerido
def eliminar_empresa(id_empresa):
    return "Eliminando..."

@app.route("/editar_empresa/<int:id_empresa>")
@login_requerido
def editar_empresa(id_empresa):
    return "Editando..."

if __name__ == "__main__":
    app.run(debug=True)
