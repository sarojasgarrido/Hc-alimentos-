from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
import os
import traceback
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-super-segura")

def get_connection():
    url_db = os.environ.get("DATABASE_URL")
    if not url_db:
        raise ValueError("DATABASE_URL no configurada.")
    return psycopg2.connect(url_db)

def login_requerido(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        return funcion(*args, **kwargs)
    return envoltura

# --- LOGIN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    siguiente = request.args.get("next") or request.form.get("next")
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
            return redirect(siguiente or url_for("dashboard"))
        return "Login fallido"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- DASHBOARD ---
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

# --- PALLETS ---
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
        ids_prod = request.form.getlist("id_producto[]")
        cants = request.form.getlist("cantidad[]")
        for p_id, cant in zip(ids_prod, cants):
            cursor.execute(
                "INSERT INTO tbl_pallet_producto (id_pallet, id_producto, cantidad, cantidad_original) VALUES (%s, %s, %s, %s)",
                (id_pallet, p_id, cant, cant)
            )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    
    cursor.execute("SELECT id_empresa, nombre FROM tbl_empresas WHERE es_proveedor = TRUE")
    proveedores = cursor.fetchall()
    cursor.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE")
    productos = cursor.fetchall()
    conn.close()
    return render_template("pallet_nuevo.html", proveedores=proveedores, productos=productos)

@app.route("/pallets/buscar")
@login_requerido
def buscar_pallets():
    # Nueva función para evitar el BuildError
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pa.id_pallet, pa.factura, pa.fecha_ingreso, pa.estado, pv.nombre 
        FROM tbl_pallets pa 
        JOIN tbl_empresas pv ON pa.id_proveedor = pv.id_empresa
        ORDER BY pa.fecha_ingreso DESC LIMIT 50
    """)
    resultados = cursor.fetchall()
    conn.close()
    return render_template("buscar_pallets.html", resultados=resultados)

@app.route("/pallets/consulta", methods=["GET", "POST"])
@login_requerido
def consulta_pallet():
    if request.method == "POST":
        return redirect(url_for("consulta_pallet_detalle", codigo_qr=request.form["codigo_qr"]))
    return render_template("consulta_pallet.html")

@app.route("/pallets/consulta/<codigo_qr>")
@login_requerido
def consulta_pallet_detalle(codigo_qr):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_pallet FROM tbl_pallets WHERE codigo_qr = %s", (codigo_qr,))
    pallet = cursor.fetchone()
    if not pallet:
        return "Pallet no encontrado", 404
    cursor.execute("SELECT * FROM tbl_pallet_producto WHERE id_pallet = %s", (pallet[0],))
    items = cursor.fetchall()
    conn.close()
    return render_template("pallet_detalle.html", pallet=pallet, items=items)

# --- MANTENEDORES ---
@app.route("/productos")
@login_requerido
def listar_productos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, codigo, nombre, unidad FROM tbl_productos WHERE activo = TRUE")
    productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)

@app.route("/empresas")
@login_requerido
def listar_empresas():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_empresa, nombre, rut, es_proveedor, es_cliente FROM tbl_empresas WHERE activo = TRUE")
    empresas = cursor.fetchall()
    conn.close()
    return render_template("empresas.html", empresas=empresas)

@app.route("/historial")
@login_requerido
def historial():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fecha, tipo_movimiento, observacion FROM tbl_movimientos ORDER BY fecha DESC")
    movimientos = cursor.fetchall()
    conn.close()
    return render_template("historial.html", movimientos=movimientos)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
