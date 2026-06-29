from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-super-segura")

def get_connection():
    # Retorna un cursor que permite usar dot notation (r.id_pallet) en el HTML
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    return conn

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# --- LOGIN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        clave = request.form["clave"].strip()
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id_usuario, nombre, clave FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        user = cur.fetchone()
        conn.close()
        # Bypass temporal
        if user and clave == "123456":
            session["usuario_id"] = user["id_usuario"]
            session["nombre"] = user["nombre"]
            return redirect(url_for("dashboard"))
        return "Login fallido"
    return render_template("login.html")

# --- DASHBOARD ---
@app.route("/")
@login_requerido
def dashboard():
    return render_template("dashboard.html")

# --- BUSCAR PALLETS (MATCH PERFECTO CON HTML) ---
@app.route("/pallets/buscar", methods=["GET"])
@login_requerido
def buscar_pallets():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Captura de filtros
    id_prov = request.args.get("id_proveedor")
    id_prod = request.args.get("id_producto")
    factura = request.args.get("factura")
    estado = request.args.get("estado")
    
    # Query dinámica
    query = """
        SELECT pa.id_pallet, pv.nombre as proveedor, pa.factura, 
               u.rack, u.nivel, u.posicion, pa.estado, pa.fecha_ingreso
        FROM tbl_pallets pa
        JOIN tbl_empresas pv ON pa.id_proveedor = pv.id_empresa
        LEFT JOIN tbl_pallet_ubicacion pu ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
        LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
        WHERE 1=1
    """
    params = []
    
    if id_prov:
        query += " AND pa.id_proveedor = %s"
        params.append(id_prov)
    if id_prod:
        query += " AND pa.id_pallet IN (SELECT id_pallet FROM tbl_pallet_producto WHERE id_producto = %s)"
        params.append(id_prod)
    if factura:
        query += " AND pa.factura ILIKE %s"
        params.append(f"%{factura}%")
    if estado:
        query += " AND pa.estado = %s"
        params.append(estado)
        
    cur.execute(query, tuple(params))
    resultados = cur.fetchall()
    
    # Obtener listas para filtros (alias id_proveedor/id_producto para que el HTML funcione)
    cur.execute("SELECT id_empresa AS id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = TRUE")
    proveedores = cur.fetchall()
    
    cur.execute("SELECT id_producto, nombre FROM tbl_productos")
    productos = cur.fetchall()
    
    conn.close()
    
    return render_template("buscar_pallets.html", 
                           resultados=resultados, 
                           proveedores=proveedores, 
                           productos=productos,
                           filtros={'id_proveedor': id_prov, 'id_producto': id_prod, 'factura': factura, 'estado': estado})

# --- DETALLE ---
@app.route("/pallets/detalle/<int:id_pallet>")
@login_requerido
def ver_pallet(id_pallet):
    return f"Detalle del pallet {id_pallet}" 

if __name__ == "__main__":
    app.run(debug=True, port=5000)
