import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'hc_alimentos_secret_2026'
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Simplemente validamos contra la tabla que ya verificamos que existe
        usuario_in = request.form.get('usuario')
        clave_in = request.form.get('clave')
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s AND clave = %s", (usuario_in, clave_in))
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
    return render_template('dashboard.html')

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('productos.html')

@app.route('/empresas', methods=['GET', 'POST'])
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('empresas.html')

@app.route('/pallet_nuevo')
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_nuevo.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
