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
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Pallets Activos
    cur.execute("SELECT COUNT(*) as activos FROM tbl_pallets")
    pallets_activos = cur.fetchone()['activos']
    
    # 2. Alertas de vencimiento (7 días)
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
                           ocupacion=round((pallets_activos / 100) * 100, 1), 
                           proximos_vencer=proximos)

@app.route('/pallet_nuevo', methods=['GET', 'POST'])
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'POST':
        qr = f"HC-{str(uuid.uuid4())[:8].upper()}"
        cur.execute("INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura) VALUES (%s, %s, %s)", 
                    (int(request.form.get('id_proveedor')), qr, request.form.get('factura')))
        conn.commit()
        flash(f"Pallet creado: {qr}")
        return redirect(url_for('pallet_nuevo'))

    cur.execute("SELECT * FROM tbl_empresas WHERE es_proveedor = TRUE")
    provs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('pallet_nuevo.html', proveedores=provs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
