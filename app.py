from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from functools import wraps
import os
from db import ejecutar_query

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-super-segura")

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- LOGIN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario_form = request.form["usuario"].strip()
        clave_form = request.form["clave"].strip()
        resultados = ejecutar_query("SELECT id_usuario, nombre, clave, rol FROM tbl_usuarios WHERE usuario = %s", (usuario_form,))
        if not resultados: return "Usuario no encontrado"
        user = resultados[0]
        if check_password_hash(user['clave'], clave_form):
            session["usuario_id"] = user["id_usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("dashboard"))
        return "Login fallido: Clave incorrecta."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- RUTAS PRINCIPALES ---
@app.route("/")
@login_requerido
def dashboard():
    return render_template("dashboard.html")

@app.route("/dashboard/detalle/<vista>")
@login_requerido
def detalle_panel(vista):
    return f"Detalle de vista: {vista} (En construcción)"

@app.route("/pallets/nuevo")
@login_requerido
def nuevo_pallet():
    return "Ingreso de Pallet (En construcción)"

@app.route("/pallets/consulta")
@login_requerido
def consulta_pallet():
    return render_template("consulta_pallet.html")

@app.route("/pallets/buscar")
@login_requerido
def buscar_pallets():
    return "Buscar Pallets (En construcción)"

@app.route("/picking")
@login_requerido
def picking():
    return "Picking/Despacho (En construcción)"

@app.route("/productos")
@login_requerido
def productos():
    return "Productos (En construcción)"

@app.route("/empresas")
@login_requerido
def empresas():
    return "Empresas (En construcción)"

@app.route("/usuarios")
@login_requerido
def usuarios():
    return "Usuarios (En construcción)"

# --- DETALLES Y ACCIONES ---
@app.route("/pallets/detalle/<int:id_pallet>")
@login_requerido
def ver_pallet(id_pallet):
    return f"Detalle del pallet {id_pallet}"

@app.route("/pallets/descargar_qr/<int:id_pallet>")
@login_requerido
def descargar_qr(id_pallet):
    return f"Descargando QR del pallet {id_pallet}"

@app.route("/pallets/editar/<int:id_pallet>")
@login_requerido
def editar_pallet(id_pallet):
    return f"Editando pallet {id_pallet}"

@app.route("/pallets/despachar/<int:id_pallet>", methods=["POST"])
@login_requerido
def despachar_pallet(id_pallet):
    return "Despachando..."

@app.route("/pallets/historial/<int:id_pallet>")
@login_requerido
def historial_pallet(id_pallet):
    return "Historial..."

if __name__ == "__main__":
    app.run(debug=True)
