import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['usuario'] = request.form.get('usuario')
        session['rol'] = 'Administrador'
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def usuarios():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        rol = request.form.get('rol')
        cur.execute("INSERT INTO tbl_usuarios (nombre, rol) VALUES (%s, %s)", (nombre, rol))
        conn.commit()
        flash("Usuario creado exitosamente")
        return redirect(url_for('usuarios'))
    
    cur.execute("SELECT * FROM tbl_usuarios ORDER BY id_usuario DESC")
    lista_usuarios = cur.fetchall()
    cur.close()
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/buscar_pallets', methods=['GET'])
def buscar_pallets():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT p.*, e.nombre as proveedor, u.rack, u.nivel, u.posicion 
        FROM tbl_pallets p
        LEFT JOIN tbl_empresas e ON p.id_proveedor = e.id_empresa
        LEFT JOIN tbl_pallet_ubicacion pu ON p.id_pallet = pu.id_pallet AND pu.vigente = TRUE
        LEFT JOIN tbl_ubicaciones u ON pu.id_ubicacion = u.id_ubicacion
    """)
    resultados = cur.fetchall()
    cur.close()
    return render_template('buscar_pallets.html', resultados=resultados)

if __name__ == '__main__':
    app.run(debug=True)
