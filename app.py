import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# La secret_key ahora viene de una variable de entorno.
# En tu servidor/hosting definí SECRET_KEY con un valor largo y aleatorio.
# Si no está definida, se usa un valor de emergencia SOLO para desarrollo local.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-cambiar-esto')

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db():
    """Abre una conexión nueva a la base de datos."""
    if not DATABASE_URL:
        raise RuntimeError("La variable de entorno DATABASE_URL no está configurada")
    return psycopg2.connect(DATABASE_URL, sslmode='require')


# --- DECORADORES DE SEGURIDAD ---
def login_required(f):
    """Bloquea el acceso a la ruta si no hay una sesión iniciada."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def rol_requerido(*roles_permitidos):
    """Bloquea el acceso si el usuario logueado no tiene uno de los roles permitidos."""
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'usuario' not in session:
                return redirect(url_for('login'))
            if session.get('rol') not in roles_permitidos:
                flash('No tenés permisos para acceder a esta sección', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return wrapper


# --- AUTENTICACIÓN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave = request.form.get('clave', '')

        if not usuario or not clave:
            error = "Ingresá usuario y clave"
            return render_template('login.html', error=error)

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tbl_usuarios WHERE usuario = %s", (usuario,))
            user = cur.fetchone()
            cur.close()

            if user and user.get('activo', True) and check_password_hash(user['clave'], clave):
                session.clear()
                session['usuario'] = user['usuario']
                session['nombre'] = user['nombre']
                session['rol'] = user['rol']
                return redirect(url_for('dashboard'))
            else:
                error = "Usuario o clave incorrectos"
        except RuntimeError as e:
            error = "Error de configuración del servidor"
            print(f"Error configuración login: {e}")
        except Exception as e:
            error = "Error de conexión con la base de datos"
            print(f"Error login: {e}")
        finally:
            if conn is not None:
                conn.close()

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- DASHBOARD ---
@app.route('/dashboard')
@login_required
def dashboard():
    context = {
        'porcentaje_ocupacion': 0, 'ubicaciones_ocupadas': 0, 'ubicaciones_total': 0,
        'pallets_activos': 0, 'pallets_parciales': 0, 'total_entradas': 0, 'total_salidas': 0,
        'proximos_vencer': [], 'racks_long': [], 'racks_trans': [], 'piso': [],
        'capacidad_pallet': 0, 'racks_detalle_json': json.dumps({}),
        'piso_detalle_json': json.dumps({}),
        'pct_rot': {'Alta': 0, 'Media': 0, 'Baja': 0, 'Sin': 0},
        'rotacion_lista': [], 'entradas': [], 'salidas': [],
        'fecha_desde': request.args.get('fecha_desde', ''),
        'fecha_hasta': request.args.get('fecha_hasta', '')
    }

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT COUNT(*) AS total FROM tbl_pallets WHERE estado = 'Activo'")
        context['pallets_activos'] = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) AS total FROM tbl_pallets WHERE estado = 'Parcial'")
        context['pallets_parciales'] = cur.fetchone()['total']

        cur.close()
    except Exception as e:
        print(f"Error al cargar dashboard: {e}")
        flash('No se pudieron cargar algunos datos del dashboard', 'error')
    finally:
        if conn is not None:
            conn.close()

    return render_template('dashboard.html', **context)


# --- GESTIÓN DE PALLETS ---
@app.route('/pallet_nuevo', methods=['GET', 'POST'])
@login_required
def pallet_nuevo():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'POST':
            id_proveedor = request.form.get('id_proveedor')
            factura = request.form.get('factura', '').strip()
            id_producto = request.form.get('id_producto')

            if not id_proveedor or not factura:
                flash('Proveedor y factura son obligatorios', 'error')
            else:
                cur.execute(
                    """INSERT INTO tbl_pallets (id_proveedor, id_producto, factura, estado)
                       VALUES (%s, %s, %s, 'Activo')""",
                    (id_proveedor, id_producto, factura)
                )
                conn.commit()
                flash('Pallet creado correctamente', 'success')

        cur.execute("SELECT id_proveedor, nombre FROM tbl_proveedores ORDER BY nombre")
        provs = cur.fetchall()
        cur.execute("SELECT id_producto, nombre FROM tbl_productos WHERE activo = True ORDER BY nombre")
        prods = cur.fetchall()
        cur.close()

    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(f"Error en pallet_nuevo: {e}")
        flash('Ocurrió un error al procesar el pallet', 'error')
        provs, prods = [], []
    finally:
        if conn is not None:
            conn.close()

    return render_template('pallet_nuevo.html', proveedores=provs, productos=prods)


# --- PRODUCTOS Y USUARIOS ---
@app.route('/productos', methods=['GET', 'POST'])
@login_required
def productos():
    conn = None
    lista = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            codigo = request.form.get('codigo', '').strip()
            unidad = request.form.get('unidad', '').strip()

            if not nombre or not codigo:
                flash('Nombre y código son obligatorios', 'error')
            else:
                cur.execute(
                    "INSERT INTO tbl_productos (nombre, codigo, unidad, activo) VALUES (%s, %s, %s, True)",
                    (nombre, codigo, unidad)
                )
                conn.commit()
                flash('Producto creado correctamente', 'success')

        cur.execute("SELECT * FROM tbl_productos ORDER BY nombre")
        lista = cur.fetchall()
        cur.close()

    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        flash('Ya existe un producto con ese código', 'error')
    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(f"Error en productos: {e}")
        flash('Ocurrió un error al procesar el producto', 'error')
    finally:
        if conn is not None:
            conn.close()

    return render_template('productos.html', productos=lista)


@app.route('/usuarios', methods=['GET', 'POST'])
@rol_requerido('Administrador')
def usuarios():
    conn = None
    lista = []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            usuario = request.form.get('usuario', '').strip()
            clave = request.form.get('clave', '')

            if not nombre or not usuario or not clave:
                flash('Todos los campos son obligatorios', 'error')
            elif len(clave) < 6:
                flash('La clave debe tener al menos 6 caracteres', 'error')
            else:
                clave_hash = generate_password_hash(clave)
                cur.execute(
                    """INSERT INTO tbl_usuarios (nombre, usuario, clave, rol, activo)
                       VALUES (%s, %s, %s, 'Operador', True)""",
                    (nombre, usuario, clave_hash)
                )
                conn.commit()
                flash('Usuario creado correctamente', 'success')

        cur.execute("SELECT id_usuario, nombre, usuario, rol, activo FROM tbl_usuarios ORDER BY nombre")
        lista = cur.fetchall()
        cur.close()

    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        flash('Ese nombre de usuario ya existe', 'error')
    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(f"Error en usuarios: {e}")
        flash('Ocurrió un error al procesar el usuario', 'error')
    finally:
        if conn is not None:
            conn.close()

    return render_template('usuarios.html', usuarios=lista)


# --- NAVEGACIÓN COMPLEMENTARIA ---
@app.route('/detalle_panel/<vista>')
@login_required
def detalle_panel(vista):
    return render_template('detalle_panel.html', titulo=vista)


@app.route('/consulta_pallet')
@login_required
def consulta_pallet():
    return render_template('consulta_pallet.html')


@app.route('/buscar_pallets')
@login_required
def buscar_pallets():
    return render_template('buscar_pallets.html', resultados=None, filtros={'factura': ''})


@app.route('/picking')
@login_required
def picking():
    return render_template('picking.html')


@app.route('/empresas')
@login_required
def empresas():
    return render_template('empresas.html')


@app.route('/pallets/detalle/<int:id_pallet>')
@login_required
def ver_pallet(id_pallet):
    return render_template('pallet_detalle.html', pallet={'id_pallet': id_pallet}, items=[])


if __name__ == '__main__':
    # debug=False para producción; usá una variable de entorno si querés activarlo en desarrollo
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
