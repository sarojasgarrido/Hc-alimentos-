
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
    if not url_db:
        print("ERROR CRÍTICO: La variable DATABASE_URL no está configurada en Render.")
        raise ValueError("DATABASE_URL no encontrada en las variables de entorno.")
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
            if check_password_hash(user[2], clave):
                session["usuario_id"] = user[0]
                session["nombre"] = user[1]
                return redirect(url_for("dashboard"))
            else:
                return "Usuario o clave incorrectos"
        else:
            return "Usuario o clave incorrectos"
            
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
        cursor.execute("INSERT INTO tbl_pallet_producto (id_pallet, id_producto, cantidad, cantidad_original) VALUES (%s, %s, %s, %s)", (id_pallet, request.form["id_producto"], request.form["cantidad"], request.form["cantidad"]))
        cursor.execute("INSERT INTO tbl_pallet_ubicacion (id_pallet, id_ubicacion) VALUES (%s, %s)", (id_pallet, request.form["id_ubicacion"]))
        cursor.execute("UPDATE tbl_ubicaciones SET estado = 'Ocupada' WHERE id_ubicacion = %s", (request.form["id_ubicacion"],))
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    
    cursor.execute("SELECT id_empresa, nombre FROM tbl_empresas WHERE es_proveedor = TRUE")
    proveedores = cursor.fetchall()
    cursor.execute("SELECT id_producto, codigo, nombre FROM tbl_productos")
    productos = cursor.fetchall()
    cursor.execute("SELECT id_ubicacion, rack, nivel, posicion FROM tbl_ubicaciones WHERE estado = 'Libre'")
    ubicaciones = cursor.fetchall()
    conn.close()
    return render_template("nuevo_pallet.html", proveedores=proveedores, productos=productos, ubicaciones=ubicaciones)

@app.route("/picking", methods=["POST"])
@login_requerido
def picking_post():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tbl_movimientos (id_pallet, tipo_movimiento, observacion, destino_tipo, id_cliente) VALUES (%s, 'Picking', %s, 'Cliente', %s)", 
                   (request.form["id_pallet"], request.form["observacion"], request.form["id_cliente"]))
    cursor.execute("UPDATE tbl_pallets SET estado = 'Consumido' WHERE id_pallet = %s", (request.form["id_pallet"],))
    cursor.execute("UPDATE tbl_ubicaciones SET estado = 'Libre' WHERE id_ubicacion IN (SELECT id_ubicacion FROM tbl_pallet_ubicacion WHERE id_pallet = %s)", (request.form["id_pallet"],))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/picking")
@login_requerido
def picking():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT p.id_pallet, p.codigo_qr, pr.nombre, pp.cantidad FROM tbl_pallets p JOIN tbl_pallet_producto pp ON p.id_pallet = pp.id_pallet JOIN tbl_productos pr ON pp.id_producto = pr.id_producto WHERE p.estado = 'Activo'")
    pallets = cursor.fetchall()
    cursor.execute("SELECT id_empresa, nombre FROM tbl_empresas WHERE es_cliente = TRUE")
    clientes = cursor.fetchall()
    conn.close()
    return render_template("picking.html", pallets=pallets, clientes=clientes)

@app.route("/historial")
@login_requerido
def historial():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT m.fecha, p.codigo_qr, pr.nombre, m.tipo_movimiento, m.observacion FROM tbl_movimientos m JOIN tbl_pallets p ON m.id_pallet = p.id_pallet JOIN tbl_pallet_producto pp ON p.id_pallet = pp.id_pallet JOIN tbl_productos pr ON pp.id_producto = pr.id_producto ORDER BY
