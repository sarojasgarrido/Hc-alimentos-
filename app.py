import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import timedelta

app = Flask(__name__)
# Configuración crítica para que la sesión sea persistente
app.secret_key = 'hc_alimentos_secret_2026'
app.config['SESSION_COOKIE_SECURE'] = False # Cambiar a True solo si tu sitio tiene HTTPS activo
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
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
                session.permanent = True
                session['usuario'] = user['usuario']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                flash("Usuario o clave incorrecta")
        except Exception as e:
            flash(f"Error: {e}")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Depuración: Si no entra al dashboard, es que session está vacía
    if 'usuario' not in session: 
        return redirect(url_for('login'))
        
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) as total FROM tbl_pallets")
    res = cur.fetchone()
    pallets_activos = res['total'] if res else 0
    
    cur.execute("""
        SELECT p.nombre, pp.fecha_vencimiento, 
        (pp.fecha_vencimiento - CURRENT_DATE) as dias_restantes
        FROM tbl_pallet_producto pp
        JOIN tbl_productos p ON pp.id_producto = p.id_producto
        WHERE pp.fecha_vencimiento BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '7 days')
    """)
    proximos = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', 
                           pallets_activos=pallets_activos, 
                           ocupacion=round((pallets_activos / 100.0) * 100, 1), 
                           proximos_vencer=proximos)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
