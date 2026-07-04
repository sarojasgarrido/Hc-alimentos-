import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_in = request.form.get('usuario')
        pass_in = request.form.get('clave')
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s AND clave = %s", (user_in, pass_in))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user:
                session['usuario'] = user['usuario']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            flash("Credenciales incorrectas")
        except Exception as e:
            flash(f"Error de base de datos: {e}")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Pallets Activos con valor por defecto
    cur.execute("SELECT COUNT(*) as activos FROM tbl_pallets")
    res = cur.fetchone()
    pallets_activos = res['activos'] if res else 0
    
    # 2. Alertas con manejo de errores (evita fallos si no hay productos)
    proximos = []
    try:
        cur.execute("""
            SELECT p.nombre, pp.fecha_vencimiento, 
            (pp.fecha_vencimiento - CURRENT_DATE) as dias_restantes
            FROM tbl_pallet_producto pp
            JOIN tbl_productos p ON pp.id_producto = p.id_producto
            WHERE pp.fecha_vencimiento BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
        """)
        proximos = cur.fetchall()
    except:
        proximos = []
    
    cur.close()
    conn.close()
    
    # Ocupación segura: evita división por cero o errores de tipo
    ocupacion = round((pallets_activos / 100.0) * 100, 1) if pallets_activos else 0
    
    return render_template('dashboard.html', 
                           pallets_activos=pallets_activos, 
                           ocupacion=ocupacion, 
                           proximos_vencer=proximos)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
