import os
import uuid
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
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Consulta de productos próximos a vencer (<= 7 días)
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

@app.route('/picking', methods=['GET', 'POST'])
def picking(): 
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        qr = request.form.get('codigo_qr')
        cantidad = int(request.form.get('cantidad'))
        destino = request.form.get('destino')
        
        try:
            cur.execute("SELECT id_pallet FROM tbl_pallets WHERE codigo_qr = %s", (qr,))
            pallet = cur.fetchone()
            if not pallet:
                flash("Error: Pallet no encontrado.")
                return redirect(url_for('picking'))
            
            # Descontar del pallet original
            cur.execute("""
                UPDATE tbl_pallet_producto 
                SET cantidad = cantidad - %s 
                WHERE id_pallet = %s
            """, (cantidad, pallet['id_pallet']))
            
            # Mover a stock de piso
            cur.execute("""
                INSERT INTO tbl_stock_piso (id_ubicacion, id_producto, id_pallet_origen, cantidad)
                SELECT u.id_ubicacion, pp.id_producto, pp.id_pallet, %s 
                FROM tbl_ubicaciones u, tbl_pallet_producto pp
                WHERE pp.id_pallet = %s AND u.rack = %s LIMIT 1
            """, (cantidad, pallet['id_pallet'], destino))
            
            conn.commit()
            flash(f"Picking exitoso: {cantidad} unidades movidas a {destino}.")
        except Exception as e:
            conn.rollback()
            flash(f"Error en operación de picking: {str(e)}")
            
        return redirect(url_for('picking'))
    
    return render_template('picking.html')

if __name__ == '__main__':
    app.run(debug=True)
