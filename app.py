from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "una-clave-secreta-muy-larga")

def get_db():
    """Retorna una conexión y un cursor dict para PostgreSQL."""
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    return conn, cur

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
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        conn, cur = get_db()
        cur.execute("SELECT id_usuario, nombre, clave, rol FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user['clave'], clave):
            session["usuario_id"] = user["id_usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("dashboard"))
        return "Login fallido"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- DASHBOARD Y NAVEGACIÓN ---
@app.route("/")
@login_requerido
def dashboard():
    # Aquí iría la lógica de tu dashboard.html
    return render_template("dashboard.html")

@app.route("/pallets/nuevo")
@login_requerido
def nuevo_pallet():
    return "Pagina de Ingresar Pallet - En construcción"

@app.route("/pallets/consulta")
@login_requerido
def consulta_pallet():
    return render_template("consulta_pallet.html")

@app.route("/pallets/buscar")
@login_requerido
def buscar_pallets():
    # Esta ruta ya la teníamos funcionando
    return "Pagina de Buscar Pallets - En construcción"

@app.route("/picking")
@login_requerido
def picking():
    return "Pagina de Picking/Despacho - En construcción"

@app.route("/productos")
@login_requerido
def productos():
    return "Pagina de Productos - En construcción"

@app.route("/empresas")
@login_requerido
def empresas():
    return "Pagina de Empresas - En construcción"

@app.route("/usuarios")
@login_requerido
def usuarios():
    if session.get('rol') != 'Administrador':
        return "Acceso denegado"
    return "Pagina de Usuarios - En construcción"

# --- DETALLES Y ACCIONES ---
@app.route("/pallets/detalle/<int:id_pallet>")
@login_requerido
def ver_pallet(id_pallet):
    return f"Detalle del pallet {id_pallet}"

if __name__ == "__main__":
    app.run(debug=True)
