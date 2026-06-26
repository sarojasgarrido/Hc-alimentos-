import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
import psycopg2
from functools import wraps

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
app.secret_key = "clave_secreta_super_segura"

def get_connection():
    url_db = os.environ.get("DATABASE_URL")
    if not url_db:
        raise ValueError("DATABASE_URL no encontrada en las variables de entorno.")
    return psycopg2.connect(url_db)

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id_usuario, nombre, clave FROM tbl_usuarios WHERE usuario = %s", (usuario,))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                # AQUÍ ESTÁ LA MAGIA: Si falla, te mostrará el error en pantalla
                if check_password_hash(user[2], clave):
                    session["usuario_id"] = user[0]
                    session["nombre"] = user[1]
                    return redirect(url_for("dashboard"))
                else:
                    return f"DEBUG: Usuario '{usuario}' encontrado, pero la clave no coincide. Hash en BD: {user[2]}"
            else:
                return f"DEBUG: Usuario '{usuario}' no encontrado en la base de datos."
        except Exception as e:
            return f"Error de conexión a BD: {str(e)}"
            
    return render_template("login.html")

# --- MANTEN EL RESTO DE TUS RUTAS IGUAL QUE ANTES (Dashboard, Productos, etc.) ---
# ... (asegúrate de pegar el resto de funciones abajo tal como las tenías)
