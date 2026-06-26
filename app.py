import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
import psycopg2
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = "clave_secreta_super_segura"

def get_connection():
    # Render leerá la variable DATABASE_URL de su panel de configuración
    url_db = os.environ.get("DATABASE_URL")
    return psycopg2.connect(url_db)

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS PRINCIPALES ---
@app.route("/")
@login_requerido
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%%'")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%%' AND estado = 'Ocupada'")
    ocupadas = cursor.fetchone()[0]
    conn.close()
    return render_template("dashboard.html", total=total, ocupadas=ocupadas)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_usuario, nombre, clave FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            print(f"DEBUG: Usuario encontrado: {user[1]}")
            print(f"DEBUG: Hash en BD: {user[2]}")
            
            if check_password_hash(user[2], clave):
                print("DEBUG: La contraseña coincide. Acceso concedido.")
                session["usuario_id"] = user[0]
                session["nombre"] = user[1]
                return redirect(url_for("dashboard"))
            else:
                print("DEBUG: ERROR - La contraseña no coincide.")
                return "Usuario o clave incorrectos (Error: Pass)"
        else:
            print(f"DEBUG: ERROR - Usuario '{usuario}' no encontrado en BD.")
            return "Usuario o clave incorrectos (Error: User)"
            
    return render_template("login.html")

# --- PRODUCTOS ---
@app.route("/productos")
@login_requerido
def listar_productos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, codigo, nombre, unidad FROM tbl_productos WHERE activo = TRUE")
    productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)

@app.route("/agregar_producto", methods=["GET", "POST"])
@login_requerido
def agregar_producto():
    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)", (request.form["codigo"], request.form["nombre"], request.form["unidad"]))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_productos"))
    return render_template("agregar_producto.html")

@app.route("/eliminar_producto/<int:id>")
@login_requerido
def eliminar_producto(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tbl_productos SET activo = FALSE WHERE id_producto = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_productos"))

# --- EMPRESAS ---
@app.route("/empresas")
@login_requerido
def listar_empresas():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_empresa, nombre, rut, es_proveedor, es_cliente FROM tbl_empresas WHERE activo = TRUE")
    empresas = cursor.fetchall()
    conn.close()
    return render_template("empresas.html", empresas=empresas)

@app.route("/agregar_empresa", methods=["GET", "POST"])
@login_requerido
def agregar_empresa():
    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tbl_empresas (nombre, rut, es_proveedor, es_cliente) VALUES (%s, %s, %s, %s)", 
                       (request.form["nombre"], request.form["rut"], True if request.form.get("es_proveedor") else False, True if request.form.get("es_cliente") else False))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_empresas"))
    return render_template("agregar_empresa.html")

@app.route("/eliminar_empresa/<int:id>")
@login_requerido
def eliminar_empresa(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tbl_empresas SET activo = FALSE WHERE id_empresa = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_empresas"))

# --- LOGÍSTICA ---
@app.route("/nuevo_pallet", methods=["GET", "POST"])
@login_requerido
def nuevo_pallet():
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == "POST":
        cursor.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr) VALUES (%s, %s) RETURNING id_pallet", (request.form["id_proveedor"], request.form["codigo_qr"]))
        id_pallet = cursor.fetchone()[0]
        cursor.execute("INSERT INTO tbl_pallet_producto (id_pallet, id_producto, cantidad, cantidad_