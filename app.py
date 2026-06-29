from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-secreta-super-segura")

def get_connection():
    """Crea una conexión a Neon y retorna el cursor dict."""
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    # Usamos RealDictCursor para que los resultados sean diccionarios (acceso por nombre de columna)
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
        usuario_form = request.form["usuario"].strip()
        clave_form = request.form["clave"].strip()
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id_usuario, nombre, clave, rol FROM tbl_usuarios WHERE usuario = %s", (usuario_form,))
        user = cur.fetchone()
        conn.close()
        
        # Verificación segura de contraseña
        if user and check_password_hash(user['clave'], clave_form):
            session["usuario_id"] = user["id_usuario"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("dashboard"))
        return "Login fallido. Usuario o clave incorrectos."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- DASHBOARD ---
@app.route("/")
@login_requerido
def dashboard():
    # Aquí iría la lógica para renderizar el dashboard
    return render_template("dashboard.html")

# --- BUSCAR PALLETS ---
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
    
    # Query dinámica adaptada a nuestro esquema
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
    
    # Obtener listas para filtros
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
