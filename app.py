import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session

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
        # Búsqueda eliminando espacios por seguridad
        cur.execute("SELECT * FROM tbl_usuarios WHERE TRIM(usuario) = TRIM(%s) AND TRIM(clave) = TRIM(%s)", (user_in, pass_in))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['usuario'] = user['usuario']
            return redirect(url_for('dashboard'))
        else:
            return "Usuario no encontrado o clave incorrecta. <a href='/'>Volver</a>"
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Si logras ver este mensaje, el login funcionó
    return "Login exitoso. Bienvenido al sistema."

if __name__ == '__main__':
    app.run(debug=True)
