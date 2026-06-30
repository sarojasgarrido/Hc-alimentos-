from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from functools import wraps
import os
# Importamos tu función desde el archivo db.py
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

# --- LOGIN CON DEPURACIÓN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario_form = request.form["usuario"].strip()
        clave_form = request.form["clave"].strip()
        
        # Consultamos usando tu nueva función de db.py
        # Esto devuelve una lista de diccionarios
        resultados = ejecutar_query(
            "SELECT id_usuario, nombre, clave, rol FROM tbl_usuarios WHERE usuario = %s", 
            (usuario_form,)
        )
        
        # DEBUG: Si la lista está vacía, el usuario no existe en la BD
        if not resultados:
            return f"DEBUG: No se encontró ningún usuario con el nombre '{usuario_form}' en la base de datos."
            
        user = resultados[0]
        
        # Verificación de contraseña
        if check_password_hash(user['clave'], clave_form):
            session["usuario_id"] = user["id_usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("dashboard"))
        else:
            return "Login fallido: La contraseña es incorrecta."
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- RUTAS PRINCIPALES (Placeholder para evitar errores 500) ---
@app.route("/")
@login_requerido
def dashboard():
    return render_template("dashboard.html")

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

if __name__ == "__main__":
    app.run(debug=True)
