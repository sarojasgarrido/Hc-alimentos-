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
        
        # Obtenemos todos los usuarios para depurar la comparación
        cur.execute("SELECT usuario, clave FROM tbl_usuarios")
        todos = cur.fetchall()
        cur.close()
        conn.close()
        
        # Comparación manual para depuración
        for u in todos:
            # Imprimimos en los logs de Render para que puedas ver la comparación real
            print(f"DEBUG: Ingresado '{user_in}' vs DB '{u['usuario']}' | Ingresado '{pass_in}' vs DB '{u['clave']}'")
            
            if user_in.strip() == u['usuario'].strip() and pass_in.strip() == u['clave'].strip():
                session['usuario'] = u['usuario']
                return redirect(url_for('dashboard'))
        
        # Si llega aquí, es que no hubo coincidencia
        return f"Error: No hay coincidencia. Ingresaste '{user_in}'/'{pass_in}'. Usuarios en DB: {todos}"
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session: return redirect(url_for('login'))
    return "Login exitoso. Bienvenido al sistema."

@app.route('/pallet_nuevo')
def pallet_nuevo():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('pallet_nuevo.html')

@app.route('/productos')
def productos():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('productos.html')

@app.route('/empresas')
def empresas():
    if 'usuario' not in session: return redirect(url_for('login'))
    return render_template('empresas.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
