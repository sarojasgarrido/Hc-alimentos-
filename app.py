import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
# Asegúrate de configurar SECRET_KEY en tu entorno
app.secret_key = os.environ.get('SECRET_KEY', 'hc_alimentos_secret_2026')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'Administrador':
            flash("No tienes permisos suficientes.")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTENTICACIÓN ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_in = request.form.get('usuario')
        clave_in = request.form.get('clave')
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s AND clave = %s", (usuario_in, clave_in))
            user = cur.fetchone()
            cur.close()
            if user:
                session['usuario'] = user['usuario']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                flash("Usuario o contraseña incorrectos.")
        except Exception as e:
            flash(f"Error de conexión: {str(e)}")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD Y ALERTAS ---

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT p.nombre, pp.fecha_vencimiento, 
        (pp.fecha_vencimiento - CURRENT_DATE) as dias_restantes
        FROM tbl_pallet_producto pp
        JOIN tbl_productos p ON pp.id_producto = p.id_producto
        WHERE pp.fecha_vencimiento BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
    """)
    proximos = cur.fetchall()
    cur.close()
    return render_template('dashboard.html', proximos_vencer=proximos)

# --- MÓDULOS DE BODEGA ---

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        try:
            codigo_qr = f"HC-{str(uuid.uuid4())[:8].upper()}"
            cur.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s) RETURNING id_pallet", 
                        (request.form.get('id_proveedor'), codigo_qr, request.form.get('factura')))
            id_pallet = cur.fetchone()['id_pallet']
            
            p_ids = request.form.getlist('id_producto[]')
            cantidades = request.form.getlist('cantidad[]')
            for i in range(len(p_ids)):
                cur.execute("INSERT INTO tbl_pallet_producto (id_pallet, id_producto, cantidad, cantidad_original) VALUES (%s, %s, %s, %s)",
                            (id_pallet, p_ids[i], cantidades[i], cantidades[i]))
            conn.commit()
            flash(f"Pallet creado
