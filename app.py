import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
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

# --- RUTA DE EMERGENCIA: AUTO-REPARACIÓN DE CLAVE ---
@app.route("/reparar_clave")
def reparar_clave():
    try:
        # Genera el hash usando la librería interna del servidor
        nueva_clave_hash = generate_password_hash("123456")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tbl_usuarios SET clave = %s WHERE usuario = 'Admin'", (nueva_clave_hash,))
        conn.commit()
        conn.close()
        return "¡Clave reparada con éxito! Ahora ve a /login"
    except Exception as e:
        return f"Error al reparar: {str(e)}"

# --- RUTA PRINCIPAL ---
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

# --- LOGIN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        clave = request.form["clave"].strip()
        
        try:
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
                    return f"DEBUG: Clave incorrecta para '{usuario}'."
            else:
                return f"DEBUG: Usuario '{usuario}' no encontrado."
        except Exception as e:
            return f"Error de conexión a BD: {str(e)}"
            
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

# --- HISTORIAL ---
@app.route("/historial")
@login_requerido
def historial():
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT m.fecha, p.codigo_qr, pr.nombre, m.tipo_movimiento, m.observacion 
        FROM tbl_movimientos m 
        JOIN tbl_pallets p ON m.id_pallet = p.id_pallet 
        JOIN tbl_pallet_producto pp ON p.id_pallet = pp.id_pallet 
        JOIN tbl_productos pr ON pp.id_producto = pr.id_producto 
        ORDER BY m.fecha DESC
    """
    cursor.execute(query)
    movimientos = cursor.fetchall()
    conn.close()
    return render_template("historial.html", movimientos=movimientos)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
