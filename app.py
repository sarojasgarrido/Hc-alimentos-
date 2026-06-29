from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
import os
import io
import base64
import uuid
import json
import qrcode
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-temporal-cambiar-despues")

# --- CONEXIÓN A NEON (POSTGRESQL) ---
def get_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

# --- Decoradores ---
def login_requerido(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        return funcion(*args, **kwargs)
    return envoltura

def admin_requerido(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        if session.get("rol") != "Administrador":
            return "Acceso restringido: solo administradores.", 403
        return funcion(*args, **kwargs)
    return envoltura

# --- LOGIN (Bypass habilitado para acceso inmediato) ---
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

        if fila is None:
            return render_template("login.html", error="Usuario no encontrado", next=siguiente)
        
        id_usuario, nombre, clave_hash, rol, activo = fila
        if not activo:
            return render_template("login.html", error="Usuario inactivo", next=siguiente)
        
        # BYPASS TEMPORAL activo
        if clave == "123456":
            session["usuario_id"] = id_usuario
            session["nombre"] = nombre
            session["rol"] = rol
            return redirect(siguiente or url_for("dashboard"))
        else:
            return render_template("login.html", error="Clave incorrecta", next=siguiente)

    return render_template("login.html", next=siguiente)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- DASHBOARD Y LÓGICA LOGÍSTICA ---
CAJAS_POR_PALLET_ESTANDAR = 96

@app.route("/")
@login_requerido
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%'")
    ubicaciones_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%' AND estado = 'Ocupada'")
    ubicaciones_ocupadas = cursor.fetchone()[0]

    # ... (El dashboard completo lo mantienes integrando la lógica de tu compañero con las conversiones SQL)
    # Ejemplo de conversión:
    # cursor.execute("...WHERE pp.fecha_vencimiento <= CURRENT_TIMESTAMP + INTERVAL '7 days'")

    conn.close()
    return render_template("dashboard.html")

# --- PICKING CON CONVERSIÓN A POSTGRES ---
@app.route("/picking", methods=["GET", "POST"])
@login_requerido
def picking():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        accion = request.form.get("accion", "picking")
        # Asegúrate de reemplazar TODOS los '?' por '%s' en tus queries de picking
        # Y reemplazar TOP 1 por LIMIT 1 al final de la consulta.
        # Ejemplo:
        # cursor.execute("SELECT ... FROM ... WHERE ... LIMIT 1", (params,))
        pass # Aquí insertas la lógica de tu compañero traducida
    
    conn.close()
    return render_template("picking.html")

# --- MANTENEDORES (PRODUCTOS, EMPRESAS, ETC) ---
@app.route("/productos", methods=["GET", "POST"])
@login_requerido
def productos():
    conn = get_connection()
    cursor = conn.cursor()
    # Cambia '?' por '%s'
    cursor.execute("SELECT id_producto, codigo, nombre, unidad, activo FROM tbl_productos ORDER BY nombre")
    lista_productos = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=lista_productos)

# ... Copia aquí el resto de las rutas (pallets, usuarios, historial) 
# asegurando que todas usan '%s' para parámetros y 'LIMIT 1' para top 1.

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
