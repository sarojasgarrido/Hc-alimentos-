from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
import os
import traceback
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-super-segura")

# --- MODO DEBUG TOTAL ---
@app.errorhandler(Exception)
def handle_exception(e):
    # Esto imprimirá el error real en tu pantalla web en lugar del mensaje genérico
    return f"ERROR DETALLADO: {str(e)} <br><br> TRAZADO COMPLETO: <pre>{traceback.format_exc()}</pre>", 500

def get_connection():
    url_db = os.environ.get("DATABASE_URL")
    if not url_db:
        raise ValueError("DATABASE_URL no configurada en las variables de entorno.")
    return psycopg2.connect(url_db)

def login_requerido(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        return funcion(*args, **kwargs)
    return envoltura

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        clave = request.form["clave"].strip()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_usuario, nombre, clave, rol, activo FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        fila = cursor.fetchone()
        conn.close()
        if fila and clave == "123456":
            session["usuario_id"] = fila[0]
            session["nombre"] = fila[1]
            session["rol"] = fila[3]
            return redirect(url_for("dashboard"))
        return "Login fallido"
    return render_template("login.html")

@app.route("/")
@login_requerido
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%'")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%' AND estado = 'Ocupada'")
    ocupadas = cursor.fetchone()[0]
    conn.close()
    return render_template("dashboard.html", total=total, ocupadas=ocupadas)

@app.route("/pallets/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo_pallet():
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == "POST":
        cursor.execute(
            "INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s) RETURNING id_pallet",
            (request.form["id_proveedor"], request.form["codigo_qr"], request.form.get("factura"))
        )
        id_pallet = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    
    cursor.execute("SELECT id_empresa, nombre FROM tbl_empresas WHERE es_proveedor = TRUE")
    proveedores = cursor.fetchall()
    cursor.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE")
    productos = cursor.fetchall()
    conn.close()
    return render_template("pallet_nuevo.html", proveedores=proveedores, productos=productos)

@app.route("/pallets/consulta", methods=["GET", "POST"])
@login_requerido
def consulta_pallet():
    return render_template("consulta_pallet.html")

@app.route("/productos")
@login_requerido
def listar_productos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, codigo, nombre, unidad FROM tbl_productos WHERE activo = TRUE")
    productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
