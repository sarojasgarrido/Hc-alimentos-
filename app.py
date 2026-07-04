import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
# Asegúrate de configurar tu SECRET_KEY en las variables de entorno de tu hosting
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_muy_segura_2026')
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

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('usuario')
        pass_input = request.form.get('clave')
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s AND clave = %s", (user_input, pass_input))
            user = cur.fetchone()
            cur.close()
            if user:
                session['usuario'] = user['usuario']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                flash("Credenciales incorrectas.")
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

# --- GESTIÓN DE PERSONAL ---

@app.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        rol = request.form.get('rol')
        try:
            cur.execute("INSERT INTO tbl_usuarios (nombre, usuario, clave, rol) VALUES (%s, %s, %s, %s)", 
                        (nombre, usuario, clave, rol))
            conn.commit()
            flash("Personal añadido exitosamente.")
        except Exception as e:
            conn.rollback()
            flash(f"Error al crear usuario: {str(e)}")
        return redirect(url_for('usuarios'))
    
    cur.execute("SELECT * FROM tbl_usuarios ORDER BY id_usuario DESC")
    lista = cur.fetchall()
    cur.close()
    return render_template('usuarios.html', usuarios=lista)

# --- MÓDULOS DE BODEGA ---

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        try:
            cur.execute("INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)", 
                        (request.form.get('codigo'), request.form.get('nombre'), request.form.get('unidad')))
            conn.commit()
            flash("Producto registrado.")
        except: conn.rollback()
        return redirect(url_for('productos'))
    
    cur.execute("SELECT * FROM tbl_productos ORDER BY nombre ASC")
    lista = cur.fetchall()
    cur.close()
    return render_template('productos.html', productos=lista)

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        try:
            cur.execute("INSERT INTO tbl_empresas (nombre, rut, es_proveedor, es_cliente) VALUES (%s, %s, %s, %s)", 
                        (request.form.get('nombre'), request.form.get('rut'), 
                         request.form.get('es_proveedor')=='on', request.form.get('es_cliente')=='on'))
            conn.commit()
            flash("Empresa registrada.")
        except: conn.rollback()
        return redirect(url_for('empresas'))
    
    cur.execute("SELECT * FROM tbl_empresas ORDER BY nombre ASC")
    lista = cur.fetchall()
    cur.close()
    return render_template('empresas.html', empresas=lista)

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        codigo_qr = f"HC-{str(uuid.uuid4())[:8].upper()}"
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s) RETURNING id_pallet", 
                    (request.form.get('id_proveedor'), codigo_qr, request.form.get('factura')))
        id_pallet = cur.fetchone()['id_pallet']
        
        # Guardar productos
        p_ids = request.form.getlist('id_producto[]')
        cantidades = request.form.getlist('cantidad[]')
        for i in range(len(p_ids)):
            cur.execute("INSERT INTO tbl_pallet_producto (id_pallet, id_producto, cantidad, cantidad_original) VALUES (%s, %s, %s, %s)",
                        (id_pallet, p_ids[i], cantidades[i], cantidades[i]))
        conn.commit()
        flash(f"Pallet creado: {codigo_qr}")
        return redirect(url_for('pallet_nuevo'))

    cur.execute("SELECT * FROM tbl_empresas WHERE es_proveedor = TRUE")
    provs = cur.fetchall()
    cur.execute("SELECT * FROM tbl_productos WHERE activo = TRUE")
    prods = cur.fetchall()
    cur.close()
    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)

@app.route('/picking', methods=['GET', 'POST'])
def picking(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor()
        qr = request.form.get('codigo_qr')
        cant = request.form.get('cantidad')
        dest = request.form.get('destino')
        cur.execute("UPDATE tbl_pallet_producto SET cantidad = cantidad - %s WHERE id_pallet = (SELECT id_pallet FROM tbl_pallets WHERE codigo_qr = %s)", (cant, qr))
        conn.commit()
        flash("Picking registrado.")
        return redirect(url_for('picking'))
    return render_template('picking.html')

if __name__ == '__main__':
    app.run(debug=True)
