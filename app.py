from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from db import get_connection
import os
import io
import base64
import uuid
import json
import qrcode
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-temporal-cambiar-despues")


def login_requerido(funcion):
    """
    Decorador: bloquea el acceso a una ruta si el usuario
    no ha iniciado sesion (no hay 'usuario_id' guardado).
    Si no hay sesion, redirige al login y recuerda a donde
    se queria ir, para volver ahi mismo despues de iniciar sesion.
    """
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        return funcion(*args, **kwargs)
    return envoltura


def admin_requerido(funcion):
    """
    Decorador: solo deja pasar a usuarios con rol Administrador.
    Si no es admin, lo manda al panel con codigo 403 (acceso denegado).
    """
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login", next=request.path))
        if session.get("rol") != "Administrador":
            return "Acceso restringido: solo administradores.", 403
        return funcion(*args, **kwargs)
    return envoltura


@app.route("/login", methods=["GET", "POST"])
def login():
    siguiente = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id_usuario, nombre, clave, rol, activo
            FROM tbl_usuarios
            WHERE usuario = %s
            """,
            (usuario,)
        )
        fila = cursor.fetchone()
        conn.close()

        if fila is None:
            return render_template("login.html", error="Usuario no encontrado", next=siguiente)

        id_usuario, nombre, clave_hash, rol, activo = fila

        if not activo:
            return render_template("login.html", error="Usuario inactivo", next=siguiente)

        if not check_password_hash(clave_hash, clave):
            return render_template("login.html", error="Clave incorrecta", next=siguiente)

        # Login correcto: se guarda la sesion
        session["usuario_id"] = id_usuario
        session["nombre"] = nombre
        session["rol"] = rol

        # Si venia de una pagina protegida (ej: el link del QR), vuelve ahi mismo.
        # Si no, va al panel principal.
        if siguiente:
            return redirect(siguiente)
        return redirect(url_for("dashboard"))

    return render_template("login.html", next=siguiente)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# Capacidad estimada por pallet (en cajas estandar 40x30x30 sobre pallet 1.0x1.2m).
# Esta constante se usa para mostrar el % de llenado de cada pallet en el mapa.
# Ajustable mas adelante segun el tipo de producto.
CAJAS_POR_PALLET_ESTANDAR = 96


@app.route("/")
@login_requerido
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%'")
    ubicaciones_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tbl_ubicaciones WHERE rack LIKE 'R%' AND estado = 'Ocupada'")
    ubicaciones_ocupadas = cursor.fetchone()[0]

    porcentaje_ocupacion = (
        round((ubicaciones_ocupadas / ubicaciones_total) * 100, 1)
        if ubicaciones_total > 0 else 0
    )

    cursor.execute("SELECT COUNT(*) FROM tbl_pallets WHERE estado != 'Consumido'")
    pallets_activos = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(DISTINCT id_ubicacion)
        FROM tbl_stock_piso
        WHERE cantidad > 0
        """
    )
    pallets_parciales = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            pr.nombre AS producto, pa.id_pallet, pp.cantidad, pp.fecha_vencimiento,
            u.rack, u.nivel, u.posicion,
            (pp.fecha_vencimiento - CURRENT_DATE) AS dias_para_vencer
        FROM tbl_pallet_producto pp
        JOIN tbl_productos pr ON pr.id_producto = pp.id_producto
        JOIN tbl_pallets pa ON pa.id_pallet = pp.id_pallet
        LEFT JOIN tbl_pallet_ubicacion pu
            ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
        LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
        WHERE pp.cantidad > 0
            AND pp.fecha_vencimiento IS NOT NULL
            AND pp.fecha_vencimiento <= NOW() + INTERVAL '7 days'
        ORDER BY pp.fecha_vencimiento ASC
        """
    )
    proximos_vencer = cursor.fetchall()

    # Datos del mapa: traer tambien cantidades para calcular % de llenado.
    # Para racks: cantidad del pallet. Para piso: suma del stock suelto en esa posicion.
    cursor.execute(
        """
        SELECT u.rack, u.nivel, u.posicion, u.estado,
               pa.id_pallet, e.nombre AS proveedor,
               CASE
                   WHEN u.rack = 'P' THEN
                       (SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso WHERE id_ubicacion = u.id_ubicacion)
                   ELSE
                       (SELECT COALESCE(SUM(cantidad), 0) FROM tbl_pallet_producto WHERE id_pallet = pa.id_pallet)
               END AS total_cantidad
        FROM tbl_ubicaciones u
        LEFT JOIN tbl_pallet_ubicacion pu
            ON pu.id_ubicacion = u.id_ubicacion AND pu.vigente = TRUE
        LEFT JOIN tbl_pallets pa ON pa.id_pallet = pu.id_pallet
        LEFT JOIN tbl_empresas e ON e.id_empresa = pa.id_proveedor
        """
    )
    filas = cursor.fetchall()
    conn.close()

    def color_por_ocupacion(ocupadas, total):
        if total == 0 or ocupadas == 0:
            return ("#E8F0E5", "#3C6B3F")
        pct = ocupadas / total * 100
        if pct <= 50:
            return ("#FCEFE2", "#8C5A2A")
        if pct < 100:
            return ("#F4B795", "#5C2E14")
        return ("#C8311F", "#FFFFFF")

    racks = {}
    piso = {}

    # Detalle de stock suelto por posicion de piso (para el mapa)
    cursor_piso = get_connection()
    cur2 = cursor_piso.cursor()
    cur2.execute(
        """
        SELECT u.posicion, pr.nombre AS producto, sp.cantidad,
               sp.fecha_vencimiento, sp.id_pallet_origen
        FROM tbl_stock_piso sp
        JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
        JOIN tbl_productos pr ON pr.id_producto = sp.id_producto
        WHERE sp.cantidad > 0
        """
    )
    detalle_piso = {}
    for r in cur2.fetchall():
        detalle_piso.setdefault(r.posicion, []).append({
            "producto": r.producto,
            "cantidad": r.cantidad,
            "fecha_vencimiento": str(r.fecha_vencimiento) if r.fecha_vencimiento else None,
            "id_pallet": r.id_pallet_origen
        })
    cursor_piso.close()

    for f in filas:
        # Calcular % de llenado de la caja contenida (vs capacidad estandar)
        pct_llenado = None
        if f.total_cantidad:
            pct_llenado = min(round(f.total_cantidad / CAJAS_POR_PALLET_ESTANDAR * 100, 0), 100)

        if f.rack == "P":
            piso[f.posicion] = {
                "id_pallet": f.id_pallet,
                "proveedor": f.proveedor,
                "ocupada": (f.estado == "Ocupada"),
                "cantidad": int(f.total_cantidad) if f.total_cantidad else 0,
                "capacidad": CAJAS_POR_PALLET_ESTANDAR,
                "pct_llenado": pct_llenado,
                "items": detalle_piso.get(f.posicion, [])
            }
            continue
        if f.rack not in racks:
            racks[f.rack] = {"ocupadas": 0, "total": 0, "celdas": {}}
        racks[f.rack]["total"] += 1
        if f.estado == "Ocupada":
            racks[f.rack]["ocupadas"] += 1
        if f.nivel not in racks[f.rack]["celdas"]:
            racks[f.rack]["celdas"][f.nivel] = {}
        racks[f.rack]["celdas"][f.nivel][f.posicion] = {
            "id_pallet": f.id_pallet,
            "proveedor": f.proveedor or "",
            "cantidad": int(f.total_cantidad) if f.total_cantidad else 0,
            "capacidad": CAJAS_POR_PALLET_ESTANDAR,
            "pct_llenado": pct_llenado
        }

    def num_rack(nombre):
        return int(nombre[1:]) if nombre[1:].isdigit() else 999

    racks_long = []
    racks_trans = []
    for nombre in sorted(racks.keys(), key=num_rack):
        info = racks[nombre]
        color, color_texto = color_por_ocupacion(info["ocupadas"], info["total"])
        item = {
            "nombre": nombre, "ocupadas": info["ocupadas"], "total": info["total"],
            "color": color, "color_texto": color_texto
        }
        if num_rack(nombre) <= 16:
            racks_long.append(item)
        else:
            racks_trans.append(item)

    piso_lista = []
    for pos in sorted(piso.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        info = piso[pos]
        color, color_texto = ("#C8311F", "#FFFFFF") if info["ocupada"] else ("#E8F0E5", "#3C6B3F")
        piso_lista.append({
            "posicion": pos, "ocupada": info["ocupada"],
            "color": color, "color_texto": color_texto
        })

    # Control de inventario: entradas y salidas con filtro de fechas
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")

    filtro_fecha = ""
    params_fecha = []
    if fecha_desde and fecha_hasta:
        filtro_fecha += " AND m.fecha >= %s::DATE"
        params_fecha.append(fecha_desde)
        filtro_fecha += " AND m.fecha < %s::DATE + INTERVAL '1 day'"
        params_fecha.append(fecha_hasta)
    elif fecha_desde:
        # Solo fecha desde: filtrar solo ese dia
        filtro_fecha += " AND m.fecha >= %s::DATE AND m.fecha < %s::DATE + INTERVAL '1 day'"
        params_fecha.append(fecha_desde)
        params_fecha.append(fecha_desde)
    elif fecha_hasta:
        filtro_fecha += " AND m.fecha < %s::DATE + INTERVAL '1 day'"
        params_fecha.append(fecha_hasta)

    conn2 = get_connection()
    cur2 = conn2.cursor()

    # Entradas (ingresos de pallets)
    cur2.execute(
        f"""
        SELECT m.fecha, m.id_pallet, m.observacion, e.nombre AS proveedor
        FROM tbl_movimientos m
        JOIN tbl_pallets pa ON pa.id_pallet = m.id_pallet
        JOIN tbl_empresas e ON e.id_empresa = pa.id_proveedor
        WHERE m.tipo_movimiento = 'Ingreso' {filtro_fecha}
        ORDER BY m.fecha DESC
        """,
        tuple(params_fecha)
    )
    entradas = cur2.fetchall()

    # Salidas (despachos desde piso)
    cur2.execute(
        f"""
        SELECT m.fecha, m.id_pallet, m.observacion, m.destino_tipo,
               e.nombre AS cliente_nombre
        FROM tbl_movimientos m
        LEFT JOIN tbl_empresas e ON e.id_empresa = m.id_cliente
        WHERE m.tipo_movimiento = 'Despacho' {filtro_fecha}
        ORDER BY m.fecha DESC
        """,
        tuple(params_fecha)
    )
    salidas = cur2.fetchall()

    # Conteos
    cur2.execute(
        f"SELECT COUNT(*) FROM tbl_movimientos m WHERE m.tipo_movimiento = 'Ingreso' {filtro_fecha}",
        tuple(params_fecha)
    )
    total_entradas = cur2.fetchone()[0]

    cur2.execute(
        f"SELECT COUNT(*) FROM tbl_movimientos m WHERE m.tipo_movimiento = 'Despacho' {filtro_fecha}",
        tuple(params_fecha)
    )
    total_salidas = cur2.fetchone()[0]

    conn2.close()

    # Indicador de rotacion: clasificar productos por frecuencia de despacho
    conn3 = get_connection()
    cur3 = conn3.cursor()
    cur3.execute(
        """
        SELECT
            p.id_producto, p.nombre,
            COALESCE(rack_stock.total, 0) + COALESCE(piso_stock.total, 0) AS stock_actual,
            COALESCE(movs30.cnt, 0) AS despachos_30d,
            COALESCE(movs_all.cnt, 0) AS despachos_total
        FROM tbl_productos p
        LEFT JOIN (
            SELECT pp.id_producto, SUM(pp.cantidad) AS total
            FROM tbl_pallet_producto pp
            JOIN tbl_pallets pa ON pa.id_pallet = pp.id_pallet
            WHERE pa.estado != 'Consumido'
            GROUP BY pp.id_producto
        ) rack_stock ON rack_stock.id_producto = p.id_producto
        LEFT JOIN (
            SELECT id_producto, SUM(cantidad) AS total
            FROM tbl_stock_piso WHERE cantidad > 0
            GROUP BY id_producto
        ) piso_stock ON piso_stock.id_producto = p.id_producto
        LEFT JOIN (
            SELECT pp.id_producto, COUNT(DISTINCT m.id_movimiento) AS cnt
            FROM tbl_movimientos m
            JOIN tbl_pallet_producto pp ON pp.id_pallet = m.id_pallet
            WHERE m.tipo_movimiento IN ('Picking', 'Despacho')
                AND m.fecha >= NOW() - INTERVAL '30 days'
            GROUP BY pp.id_producto
        ) movs30 ON movs30.id_producto = p.id_producto
        LEFT JOIN (
            SELECT pp.id_producto, COUNT(DISTINCT m.id_movimiento) AS cnt
            FROM tbl_movimientos m
            JOIN tbl_pallet_producto pp ON pp.id_pallet = m.id_pallet
            WHERE m.tipo_movimiento IN ('Picking', 'Despacho')
            GROUP BY pp.id_producto
        ) movs_all ON movs_all.id_producto = p.id_producto
        WHERE p.activo = TRUE
            AND (COALESCE(rack_stock.total, 0) + COALESCE(piso_stock.total, 0) > 0
                 OR COALESCE(movs_all.cnt, 0) > 0)
        ORDER BY movs30.cnt DESC, p.nombre
        """
    )
    rotacion_productos = cur3.fetchall()
    conn3.close()

    # Clasificar
    rotacion_lista = []
    conteo_rot = {"Alta": 0, "Media": 0, "Baja": 0, "Sin": 0}
    for r in rotacion_productos:
        if r.despachos_30d >= 3:
            clase = "Alta"
        elif r.despachos_30d >= 1:
            clase = "Media"
        elif r.despachos_total > 0:
            clase = "Baja"
        else:
            clase = "Sin"
        conteo_rot[clase] += 1
        rotacion_lista.append({
            "nombre": r.nombre,
            "stock": r.stock_actual,
            "despachos": r.despachos_30d,
            "clase": clase
        })

    total_rot = max(sum(conteo_rot.values()), 1)
    pct_rot = {k: round(v / total_rot * 100) for k, v in conteo_rot.items()}

    return render_template(
        "dashboard.html",
        ubicaciones_total=ubicaciones_total,
        ubicaciones_ocupadas=ubicaciones_ocupadas,
        porcentaje_ocupacion=porcentaje_ocupacion,
        pallets_activos=pallets_activos,
        pallets_parciales=pallets_parciales,
        proximos_vencer=proximos_vencer,
        racks_long=racks_long,
        racks_trans=racks_trans,
        piso=piso_lista,
        racks_detalle_json=json.dumps(racks),
        piso_detalle_json=json.dumps(piso),
        capacidad_pallet=CAJAS_POR_PALLET_ESTANDAR,
        entradas=entradas,
        salidas=salidas,
        total_entradas=total_entradas,
        total_salidas=total_salidas,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        rotacion_lista=rotacion_lista,
        pct_rot=pct_rot
    )


# ---------------------------------------------------------------
# Mantenedor de Productos
# ---------------------------------------------------------------

@app.route("/productos", methods=["GET", "POST"])
@login_requerido
def productos():
    conn = get_connection()
    cursor = conn.cursor()

    mensaje = None

    if request.method == "POST":
        codigo = request.form.get("codigo") or None
        nombre = request.form["nombre"]
        unidad = request.form.get("unidad") or None

        cursor.execute(
            "INSERT INTO tbl_productos (codigo, nombre, unidad) VALUES (%s, %s, %s)",
            (codigo, nombre, unidad)
        )
        conn.commit()
        mensaje = f"Producto '{nombre}' agregado correctamente."

    cursor.execute(
        "SELECT id_producto, codigo, nombre, unidad, activo FROM tbl_productos ORDER BY nombre"
    )
    lista_productos = cursor.fetchall()
    conn.close()

    return render_template("productos.html", productos=lista_productos, mensaje=mensaje)


@app.route("/productos/editar/<int:id_producto>", methods=["GET", "POST"])
@admin_requerido
def editar_producto(id_producto):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        codigo = request.form.get("codigo") or None
        nombre = request.form["nombre"]
        unidad = request.form.get("unidad") or None
        activo = True if request.form.get("activo") else False

        cursor.execute(
            """
            UPDATE tbl_productos
            SET codigo = %s, nombre = %s, unidad = %s, activo = %s
            WHERE id_producto = %s
            """,
            (codigo, nombre, unidad, activo, id_producto)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("productos"))

    cursor.execute(
        "SELECT id_producto, codigo, nombre, unidad, activo FROM tbl_productos WHERE id_producto = %s",
        (id_producto,)
    )
    producto = cursor.fetchone()
    conn.close()

    return render_template("producto_editar.html", producto=producto)


@app.route("/productos/eliminar/<int:id_producto>")
@admin_requerido
def eliminar_producto(id_producto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tbl_productos WHERE id_producto = %s", (id_producto,))
    conn.commit()
    conn.close()
    return redirect(url_for("productos"))


# ---------------------------------------------------------------
# Mantenedor de Empresas (Proveedores y/o Clientes)
# ---------------------------------------------------------------

@app.route("/empresas", methods=["GET", "POST"])
@login_requerido
def empresas():
    conn = get_connection()
    cursor = conn.cursor()

    mensaje = None

    if request.method == "POST":
        nombre = request.form["nombre"]
        rut = request.form.get("rut") or None
        telefono = request.form.get("telefono") or None
        correo = request.form.get("correo") or None
        direccion = request.form.get("direccion") or None
        es_proveedor = True if request.form.get("es_proveedor") else False
        es_cliente = True if request.form.get("es_cliente") else False

        cursor.execute(
            """
            INSERT INTO tbl_empresas
                (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente)
        )
        conn.commit()
        mensaje = f"Empresa '{nombre}' agregada correctamente."

    cursor.execute(
        """
        SELECT id_empresa, nombre, rut, telefono, correo, direccion,
               es_proveedor, es_cliente, activo
        FROM tbl_empresas ORDER BY nombre
        """
    )
    lista_empresas = cursor.fetchall()
    conn.close()

    return render_template("empresas.html", empresas=lista_empresas, mensaje=mensaje)


@app.route("/empresas/editar/<int:id_empresa>", methods=["GET", "POST"])
@admin_requerido
def editar_empresa(id_empresa):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        rut = request.form.get("rut") or None
        telefono = request.form.get("telefono") or None
        correo = request.form.get("correo") or None
        direccion = request.form.get("direccion") or None
        es_proveedor = True if request.form.get("es_proveedor") else False
        es_cliente = True if request.form.get("es_cliente") else False
        activo = True if request.form.get("activo") else False

        cursor.execute(
            """
            UPDATE tbl_empresas
            SET nombre = %s, rut = %s, telefono = %s, correo = %s, direccion = %s,
                es_proveedor = %s, es_cliente = %s, activo = %s
            WHERE id_empresa = %s
            """,
            (nombre, rut, telefono, correo, direccion, es_proveedor, es_cliente, activo, id_empresa)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("empresas"))

    cursor.execute(
        """
        SELECT id_empresa, nombre, rut, telefono, correo, direccion,
               es_proveedor, es_cliente, activo
        FROM tbl_empresas WHERE id_empresa = %s
        """,
        (id_empresa,)
    )
    empresa = cursor.fetchone()
    conn.close()

    return render_template("empresa_editar.html", empresa=empresa)


@app.route("/empresas/eliminar/<int:id_empresa>")
@admin_requerido
def eliminar_empresa(id_empresa):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tbl_empresas WHERE id_empresa = %s", (id_empresa,))
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()
    return redirect(url_for("empresas"))


# ---------------------------------------------------------------
# Ingreso de Pallet
# ---------------------------------------------------------------

@app.route("/pallets/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo_pallet():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        id_proveedor = request.form["id_proveedor"]
        factura = request.form.get("factura") or None

        ids_producto = request.form.getlist("id_producto[]")
        cantidades = request.form.getlist("cantidad[]")
        fechas_elaboracion = request.form.getlist("fecha_elaboracion[]")
        fechas_vencimiento = request.form.getlist("fecha_vencimiento[]")

        def recargar_formulario(mensaje_error):
            cursor.execute(
                "SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE ORDER BY nombre"
            )
            productos = cursor.fetchall()
            cursor.execute(
                "SELECT id_empresa AS id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = TRUE AND activo = TRUE ORDER BY nombre"
            )
            proveedores = cursor.fetchall()
            conn.close()
            return render_template(
                "pallet_nuevo.html",
                productos=productos,
                proveedores=proveedores,
                error=mensaje_error
            )

        # Validar que el total de cajas no supere la capacidad estimada del pallet
        try:
            total_cajas = sum(int(c) for c in cantidades if c)
        except ValueError:
            total_cajas = 0
        if total_cajas > CAJAS_POR_PALLET_ESTANDAR:
            return recargar_formulario(
                f"El pallet supera la capacidad estimada ({total_cajas} cajas, maximo {CAJAS_POR_PALLET_ESTANDAR}). "
                f"Reduce la cantidad o reparte en otro pallet."
            )

        # Buscar la primera ubicacion libre en RACKS (excluyendo el rack 'P' que es zona de piso/picking).
        # Almacenaje caotico: cualquier posicion libre sirve, el orden se respeta despues
        # en el picking por FEFO. Se ordena por el NUMERO de rack/nivel/posicion (no como texto),
        # para que quede R1, R2, R3...R10...R20 y no R1, R10, R11...R2, R20...
        cursor.execute(
            """
            SELECT id_ubicacion, rack, nivel, posicion
            FROM tbl_ubicaciones
            WHERE estado = 'Libre' AND rack LIKE 'R%'
            ORDER BY
                CAST(SUBSTRING(rack FROM 2) AS INTEGER),
                CAST(SUBSTRING(nivel FROM 2) AS INTEGER),
                CAST(posicion AS INTEGER)
            LIMIT 1
            """
        )
        ubicacion = cursor.fetchone()

        if ubicacion is None:
            return recargar_formulario("No hay ubicaciones libres en la bodega.")

        id_ubicacion, rack, nivel, posicion = ubicacion
        codigo_qr = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO tbl_pallets (id_proveedor, codigo_qr, factura)
            VALUES (%s, %s, %s)
            RETURNING id_pallet
            """,
            (id_proveedor, codigo_qr, factura)
        )
        id_pallet = cursor.fetchone()[0]

        for id_producto, cantidad, fecha_elab, fecha_venc in zip(
            ids_producto, cantidades, fechas_elaboracion, fechas_vencimiento
        ):
            cursor.execute(
                """
                INSERT INTO tbl_pallet_producto
                    (id_pallet, id_producto, cantidad, cantidad_original,
                     fecha_elaboracion, fecha_vencimiento)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (id_pallet, id_producto, cantidad, cantidad, fecha_elab or None, fecha_venc or None)
            )

        cursor.execute(
            "INSERT INTO tbl_pallet_ubicacion (id_pallet, id_ubicacion, vigente) VALUES (%s, %s, TRUE)",
            (id_pallet, id_ubicacion)
        )

        cursor.execute(
            "UPDATE tbl_ubicaciones SET estado = 'Ocupada' WHERE id_ubicacion = %s",
            (id_ubicacion,)
        )

        cursor.execute(
            """
            INSERT INTO tbl_movimientos (id_pallet, tipo_movimiento, observacion)
            VALUES (%s, 'Ingreso', %s)
            """,
            (id_pallet, f"Asignado a {rack}-{nivel}-{posicion}")
        )

        conn.commit()
        conn.close()

        # Generar imagen QR en memoria (base64) para mostrarla directo en el navegador.
        # El QR contiene un link directo a la consulta de este pallet, asi al escanearlo
        # con la camara del celular se abre directamente la informacion del pallet.
        url_consulta = request.host_url.rstrip("/") + url_for(
            "consulta_pallet_detalle", codigo_qr=codigo_qr
        )
        img = qrcode.make(url_consulta)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return render_template(
            "pallet_creado.html",
            id_pallet=id_pallet,
            rack=rack,
            nivel=nivel,
            posicion=posicion,
            codigo_qr=codigo_qr,
            qr_base64=qr_base64,
            url_consulta=url_consulta
        )

    cursor.execute(
        "SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE ORDER BY nombre"
    )
    productos = cursor.fetchall()
    cursor.execute(
        "SELECT id_empresa AS id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = TRUE AND activo = TRUE ORDER BY nombre"
    )
    proveedores = cursor.fetchall()
    conn.close()

    return render_template("pallet_nuevo.html", productos=productos, proveedores=proveedores)


# ---------------------------------------------------------------
# Consulta de Pallet por QR
# ---------------------------------------------------------------

@app.route("/pallets/consulta", methods=["GET", "POST"])
@login_requerido
def consulta_pallet():
    if request.method == "POST":
        codigo = request.form["codigo_qr"].strip()
        return redirect(url_for("consulta_pallet_detalle", codigo_qr=codigo))

    return render_template("consulta_pallet.html")


@app.route("/pallets/consulta/<codigo_qr>")
@login_requerido
def consulta_pallet_detalle(codigo_qr):
    conn = get_connection()
    cursor = conn.cursor()
    pallet, items = obtener_pallet_y_items(cursor, "pa.codigo_qr = %s", codigo_qr)

    if pallet is None:
        conn.close()
        return render_template(
            "consulta_pallet.html",
            error="No se encontro ningun pallet con ese codigo."
        )

    cursor.execute(
        "SELECT id_empresa AS id_cliente, nombre FROM tbl_empresas WHERE es_cliente = TRUE AND activo = TRUE ORDER BY nombre"
    )
    clientes = cursor.fetchall()
    conn.close()

    return render_template("pallet_detalle.html", pallet=pallet, items=items, clientes=clientes)


def obtener_pallet_y_items(cursor, condicion_sql, parametro):
    """
    Funcion auxiliar: busca un pallet (por codigo_qr o por id_pallet)
    junto con sus productos asociados. Devuelve (pallet, items) o (None, None).
    """
    cursor.execute(
        f"""
        SELECT
            pa.id_pallet, pa.id_proveedor, pa.factura, pa.fecha_ingreso, pa.estado,
            pv.nombre AS proveedor,
            u.rack, u.nivel, u.posicion
        FROM tbl_pallets pa
        JOIN tbl_empresas pv ON pv.id_empresa = pa.id_proveedor
        LEFT JOIN tbl_pallet_ubicacion pu
            ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
        LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
        WHERE {condicion_sql}
        """,
        (parametro,)
    )
    pallet = cursor.fetchone()

    if pallet is None:
        return None, None

    cursor.execute(
        """
        SELECT
            pp.id_pallet_producto, pp.id_producto,
            pr.nombre AS producto, pp.cantidad, pp.cantidad_original,
            pp.fecha_elaboracion, pp.fecha_vencimiento
        FROM tbl_pallet_producto pp
        JOIN tbl_productos pr ON pr.id_producto = pp.id_producto
        WHERE pp.id_pallet = %s
        """,
        (pallet.id_pallet,)
    )
    items = cursor.fetchall()

    return pallet, items


@app.route("/pallets/detalle/<int:id_pallet>")
@login_requerido
def ver_pallet(id_pallet):
    conn = get_connection()
    cursor = conn.cursor()
    pallet, items = obtener_pallet_y_items(cursor, "pa.id_pallet = %s", id_pallet)

    if pallet is None:
        conn.close()
        return render_template("consulta_pallet.html", error="Pallet no encontrado.")

    cursor.execute(
        "SELECT id_empresa AS id_cliente, nombre FROM tbl_empresas WHERE es_cliente = TRUE AND activo = TRUE ORDER BY nombre"
    )
    clientes = cursor.fetchall()
    conn.close()

    return render_template("pallet_detalle.html", pallet=pallet, items=items, clientes=clientes)


@app.route("/pallets/buscar")
@login_requerido
def buscar_pallets():
    conn = get_connection()
    cursor = conn.cursor()

    id_proveedor = request.args.get("id_proveedor") or ""
    id_producto = request.args.get("id_producto") or ""
    factura = request.args.get("factura") or ""
    estado = request.args.get("estado") or ""

    hay_filtros = any([id_proveedor, id_producto, factura, estado])

    resultados = None
    if hay_filtros or request.args:
        condiciones = ["1=1"]
        parametros = []

        if id_proveedor:
            condiciones.append("pa.id_proveedor = %s")
            parametros.append(id_proveedor)

        if factura:
            condiciones.append("pa.factura LIKE %s")
            parametros.append(f"%{factura}%")

        if estado:
            condiciones.append("pa.estado = %s")
            parametros.append(estado)

        if id_producto:
            condiciones.append(
                "pa.id_pallet IN (SELECT id_pallet FROM tbl_pallet_producto WHERE id_producto = %s)"
            )
            parametros.append(id_producto)

        consulta = f"""
            SELECT
                pa.id_pallet, pa.factura, pa.fecha_ingreso, pa.estado,
                pv.nombre AS proveedor,
                u.rack, u.nivel, u.posicion
            FROM tbl_pallets pa
            JOIN tbl_empresas pv ON pv.id_empresa = pa.id_proveedor
            LEFT JOIN tbl_pallet_ubicacion pu
                ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
            LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
            WHERE {" AND ".join(condiciones)}
            ORDER BY pa.fecha_ingreso DESC
        """
        cursor.execute(consulta, tuple(parametros))
        resultados = cursor.fetchall()

    cursor.execute("SELECT id_empresa AS id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = TRUE ORDER BY nombre")
    proveedores = cursor.fetchall()
    cursor.execute("SELECT id_producto, nombre FROM tbl_productos ORDER BY nombre")
    productos = cursor.fetchall()
    conn.close()

    filtros = {
        "id_proveedor": id_proveedor,
        "id_producto": id_producto,
        "factura": factura,
        "estado": estado,
    }

    return render_template(
        "buscar_pallets.html",
        proveedores=proveedores,
        productos=productos,
        resultados=resultados,
        filtros=filtros
    )


# ---------------------------------------------------------------
# Picking (salida de producto, con FEFO y priorizacion de parciales)
# ---------------------------------------------------------------

@app.route("/picking", methods=["GET", "POST"])
@login_requerido
def picking():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        accion = request.form.get("accion", "picking")

        if accion == "picking":
            # ============================================
            # PICKING: sacar del RACK y llevar al PISO
            # ============================================
            id_producto = request.form.get("id_producto")
            cantidad_raw = request.form.get("cantidad")

            if not id_producto or not cantidad_raw:
                conn.close()
                return redirect(url_for("picking"))

            cantidad_solicitada = int(cantidad_raw)

            # FEFO solo entre pallets en RACKS (no en piso)
            cursor.execute(
                """
                SELECT pp.id_pallet_producto, pp.id_pallet, pp.cantidad,
                       pp.fecha_vencimiento,
                       u.rack, u.nivel, u.posicion, pu.id_ubicacion
                FROM tbl_pallet_producto pp
                JOIN tbl_pallets pa ON pa.id_pallet = pp.id_pallet
                LEFT JOIN tbl_pallet_ubicacion pu
                    ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
                LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
                WHERE pp.id_producto = %s AND pp.cantidad > 0 AND pa.estado != 'Consumido'
                    AND (u.rack LIKE 'R%%' OR u.rack IS NULL)
                ORDER BY
                    CASE WHEN pp.fecha_vencimiento IS NULL THEN 1 ELSE 0 END,
                    pp.fecha_vencimiento ASC
                """,
                (id_producto,)
            )
            candidatos = cursor.fetchall()

            capacidad_piso = CAJAS_POR_PALLET_ESTANDAR

            cursor.execute(
                """
                SELECT id_ubicacion, rack, nivel, posicion
                FROM tbl_ubicaciones
                WHERE rack = 'P' AND estado = 'Libre'
                ORDER BY CAST(posicion AS INTEGER)
                """
            )
            posiciones_piso_libres = cursor.fetchall()
            piso_idx = 0

            restante = cantidad_solicitada
            movimientos = []

            for c in candidatos:
                if restante <= 0:
                    break

                tomado = min(c.cantidad, restante)
                nueva_cantidad = c.cantidad - tomado
                restante -= tomado

                # Descontar del pallet en el rack
                cursor.execute(
                    "UPDATE tbl_pallet_producto SET cantidad = %s WHERE id_pallet_producto = %s",
                    (nueva_cantidad, c.id_pallet_producto)
                )

                # Revisar si el pallet quedo totalmente vacio
                cursor.execute(
                    "SELECT COALESCE(SUM(cantidad), 0) FROM tbl_pallet_producto WHERE id_pallet = %s",
                    (c.id_pallet,)
                )
                total_restante_pallet = cursor.fetchone()[0]

                if total_restante_pallet == 0:
                    cursor.execute(
                        "UPDATE tbl_pallets SET estado = 'Consumido' WHERE id_pallet = %s",
                        (c.id_pallet,)
                    )
                    cursor.execute(
                        "UPDATE tbl_pallet_ubicacion SET vigente = FALSE WHERE id_pallet = %s AND vigente = TRUE",
                        (c.id_pallet,)
                    )
                    if c.id_ubicacion:
                        cursor.execute(
                            "UPDATE tbl_ubicaciones SET estado = 'Libre' WHERE id_ubicacion = %s",
                            (c.id_ubicacion,)
                        )

                # Las cajas sacadas van al piso
                cantidad_a_colocar = tomado
                venc = c.fecha_vencimiento
                detalle_destinos = []

                while cantidad_a_colocar > 0:
                    # Buscar posicion de piso con espacio para este producto
                    cursor.execute(
                        """
                        SELECT sp.id_ubicacion,
                               u.rack, u.nivel, u.posicion,
                               (SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso
                                WHERE id_ubicacion = sp.id_ubicacion) AS total_en_pos
                        FROM tbl_stock_piso sp
                        JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
                        WHERE sp.id_producto = %s
                        GROUP BY sp.id_ubicacion, u.rack, u.nivel, u.posicion
                        HAVING (SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso
                                WHERE id_ubicacion = sp.id_ubicacion) < %s
                        ORDER BY u.rack
                        LIMIT 1
                    """,
                        (id_producto, capacidad_piso)
                    )
                    pos_existente = cursor.fetchone()

                    if pos_existente:
                        espacio = capacidad_piso - pos_existente.total_en_pos
                        a_meter = min(espacio, cantidad_a_colocar)
                        cursor.execute(
                            """
                            INSERT INTO tbl_stock_piso
                                (id_ubicacion, id_producto, id_pallet_origen, cantidad, fecha_vencimiento)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (pos_existente.id_ubicacion, id_producto, c.id_pallet, a_meter, venc)
                        )
                        detalle_destinos.append(f"P-N1-Pos {pos_existente.posicion} (+{a_meter})")
                        cantidad_a_colocar -= a_meter
                    elif piso_idx < len(posiciones_piso_libres):
                        pos = posiciones_piso_libres[piso_idx]
                        a_meter = min(capacidad_piso, cantidad_a_colocar)
                        cursor.execute(
                            """
                            INSERT INTO tbl_stock_piso
                                (id_ubicacion, id_producto, id_pallet_origen, cantidad, fecha_vencimiento)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (pos.id_ubicacion, id_producto, c.id_pallet, a_meter, venc)
                        )
                        cursor.execute(
                            "UPDATE tbl_ubicaciones SET estado = 'Ocupada' WHERE id_ubicacion = %s",
                            (pos.id_ubicacion,)
                        )
                        detalle_destinos.append(f"P-N1-Pos {pos.posicion} (+{a_meter})")
                        cantidad_a_colocar -= a_meter
                        piso_idx += 1
                    else:
                        detalle_destinos.append(f"SIN ESPACIO en piso para {cantidad_a_colocar} unidades")
                        cantidad_a_colocar = 0

                destino_str = ", ".join(detalle_destinos)

                cursor.execute(
                    """
                    INSERT INTO tbl_movimientos
                        (id_pallet, tipo_movimiento, observacion, destino_tipo)
                    VALUES (%s, 'Picking', %s, 'Piso')
                    """,
                    (c.id_pallet,
                     f"Se retiraron {tomado} cajas del rack {c.rack}-{c.nivel}-Pos {c.posicion}. "
                     f"Quedan {nueva_cantidad} en el pallet. Llevadas a piso: {destino_str}.")
                )

                movimientos.append({
                    "id_pallet": c.id_pallet,
                    "origen": f"Rack {c.rack}-{c.nivel}-Pos {c.posicion}",
                    "tomado": tomado,
                    "restante_origen": nueva_cantidad,
                    "fecha_vencimiento": c.fecha_vencimiento,
                    "posicion_destino": destino_str
                })

            conn.commit()
            conn.close()

            return render_template(
                "picking_resultado.html",
                movimientos=movimientos,
                faltante=restante,
                destino_tipo="Zona de piso",
                cliente_nombre=None,
                tipo_accion="picking"
            )

        elif accion == "despacho":
            # ============================================
            # DESPACHO: sacar del PISO y enviar afuera
            # ============================================
            id_stock = request.form.get("id_stock_piso")
            cantidad_raw = request.form.get("cantidad_despacho")
            destino_tipo = request.form.get("destino_tipo", "Produccion1")

            if not id_stock or not cantidad_raw:
                conn.close()
                return redirect(url_for("picking"))

            cantidad_despacho = int(cantidad_raw)

            cursor.execute(
                """
                SELECT sp.id_stock_piso, sp.cantidad, sp.id_pallet_origen, sp.id_producto,
                       sp.fecha_vencimiento,
                       u.rack, u.nivel, u.posicion, u.id_ubicacion
                FROM tbl_stock_piso sp
                JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
                WHERE sp.id_stock_piso = %s
                """,
                (id_stock,)
            )
            stock = cursor.fetchone()

            if stock is None or stock.cantidad <= 0:
                conn.close()
                return redirect(url_for("picking"))

            tomado = min(stock.cantidad, cantidad_despacho)
            nueva_cantidad = stock.cantidad - tomado

            cursor.execute(
                "UPDATE tbl_stock_piso SET cantidad = %s WHERE id_stock_piso = %s",
                (nueva_cantidad, stock.id_stock_piso)
            )

            # Si se vacio esa posicion, liberarla
            if nueva_cantidad == 0:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso
                    WHERE id_ubicacion = %s AND cantidad > 0
                    """,
                    (stock.id_ubicacion,)
                )
                queda = cursor.fetchone()[0]
                if queda == 0:
                    cursor.execute(
                        "UPDATE tbl_ubicaciones SET estado = 'Libre' WHERE id_ubicacion = %s",
                        (stock.id_ubicacion,)
                    )

            destino_texto = destino_tipo
            if destino_tipo == "Produccion1":
                destino_texto = "Sala de produccion 1"
            elif destino_tipo == "Produccion2":
                destino_texto = "Sala de produccion 2"
            elif destino_tipo == "PlantaPrincipal":
                destino_texto = "Planta principal HC Alimentos"

            if stock.id_pallet_origen:
                cursor.execute(
                    """
                    INSERT INTO tbl_movimientos
                        (id_pallet, tipo_movimiento, observacion, destino_tipo)
                    VALUES (%s, 'Despacho', %s, %s)
                    """,
                    (stock.id_pallet_origen,
                     f"Se despacharon {tomado} cajas desde piso P-N1-Pos {stock.posicion}. "
                     f"Quedan {nueva_cantidad} en piso. Destino: {destino_texto}.",
                     destino_tipo)
                )

            conn.commit()
            conn.close()

            movimientos = [{
                "id_pallet": stock.id_pallet_origen,
                "origen": f"Piso P-N1-Pos {stock.posicion}",
                "tomado": tomado,
                "restante_origen": nueva_cantidad,
                "fecha_vencimiento": stock.fecha_vencimiento,
                "posicion_destino": destino_texto
            }]

            return render_template(
                "picking_resultado.html",
                movimientos=movimientos,
                faltante=max(0, cantidad_despacho - tomado),
                destino_tipo=destino_tipo,
                cliente_nombre=None,
                tipo_accion="despacho"
            )

    # GET: formulario
    cursor.execute(
        "SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE ORDER BY nombre"
    )
    productos = cursor.fetchall()

    cursor.execute(
        "SELECT id_empresa AS id_cliente, nombre FROM tbl_empresas WHERE es_cliente = TRUE AND activo = TRUE ORDER BY nombre"
    )
    clientes = cursor.fetchall()

    # Stock suelto en piso (para despachar)
    cursor.execute(
        """
        SELECT sp.id_stock_piso, sp.id_pallet_origen AS id_pallet,
               pr.nombre AS producto,
               sp.cantidad, sp.fecha_vencimiento,
               u.rack, u.nivel, u.posicion
        FROM tbl_stock_piso sp
        JOIN tbl_productos pr ON pr.id_producto = sp.id_producto
        JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
        WHERE sp.cantidad > 0
        ORDER BY sp.fecha_vencimiento ASC
        """
    )
    stock_piso = cursor.fetchall()
    conn.close()

    return render_template("picking.html", productos=productos, clientes=clientes, stock_piso=stock_piso)


# ---------------------------------------------------------------
# Edicion de Pallet (solo Administrador)
# ---------------------------------------------------------------

@app.route("/pallets/editar/<int:id_pallet>", methods=["GET", "POST"])
@admin_requerido
def editar_pallet(id_pallet):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        id_proveedor = request.form["id_proveedor"]
        factura = request.form.get("factura") or None

        ids_pallet_producto = request.form.getlist("id_pallet_producto[]")
        ids_producto = request.form.getlist("id_producto[]")
        cantidades = request.form.getlist("cantidad[]")
        cantidades_originales = request.form.getlist("cantidad_original[]")
        fechas_elaboracion = request.form.getlist("fecha_elaboracion[]")
        fechas_vencimiento = request.form.getlist("fecha_vencimiento[]")

        # Actualizar datos del pallet
        cursor.execute(
            "UPDATE tbl_pallets SET id_proveedor = %s, factura = %s WHERE id_pallet = %s",
            (id_proveedor, factura, id_pallet)
        )

        # Obtener los IDs de productos que SIGUEN en el pallet, para borrar
        # los que el admin haya quitado del formulario
        ids_que_quedan = [int(i) for i in ids_pallet_producto if i]

        if ids_que_quedan:
            placeholders = ",".join("?" * len(ids_que_quedan))
            cursor.execute(
                f"DELETE FROM tbl_pallet_producto WHERE id_pallet = %s AND id_pallet_producto NOT IN ({placeholders})",
                (id_pallet, *ids_que_quedan)
            )
        else:
            cursor.execute("DELETE FROM tbl_pallet_producto WHERE id_pallet = %s", (id_pallet,))

        # Actualizar / insertar cada producto
        for idx, id_pp in enumerate(ids_pallet_producto):
            id_producto = ids_producto[idx]
            cantidad = cantidades[idx]
            cantidad_original = cantidades_originales[idx]
            fecha_elab = fechas_elaboracion[idx] or None
            fecha_venc = fechas_vencimiento[idx] or None

            if id_pp:
                cursor.execute(
                    """
                    UPDATE tbl_pallet_producto
                    SET id_producto = %s, cantidad = %s, cantidad_original = %s,
                        fecha_elaboracion = %s, fecha_vencimiento = %s
                    WHERE id_pallet_producto = %s
                    """,
                    (id_producto, cantidad, cantidad_original, fecha_elab, fecha_venc, int(id_pp))
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO tbl_pallet_producto
                        (id_pallet, id_producto, cantidad, cantidad_original,
                         fecha_elaboracion, fecha_vencimiento)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (id_pallet, id_producto, cantidad, cantidad_original, fecha_elab, fecha_venc)
                )

        # Registrar la edicion en movimientos
        cursor.execute(
            """
            INSERT INTO tbl_movimientos (id_pallet, tipo_movimiento, observacion)
            VALUES (%s, 'Edicion', %s)
            """,
            (id_pallet, f"Editado por {session.get('nombre')}")
        )

        conn.commit()
        conn.close()
        return redirect(url_for("ver_pallet", id_pallet=id_pallet))

    pallet, items = obtener_pallet_y_items(cursor, "pa.id_pallet = %s", id_pallet)

    if pallet is None:
        conn.close()
        return "Pallet no encontrado.", 404

    cursor.execute(
        "SELECT id_producto, nombre FROM tbl_productos WHERE activo = TRUE ORDER BY nombre"
    )
    productos = cursor.fetchall()
    cursor.execute(
        "SELECT id_empresa AS id_proveedor, nombre FROM tbl_empresas WHERE es_proveedor = TRUE AND activo = TRUE ORDER BY nombre"
    )
    proveedores = cursor.fetchall()
    conn.close()

    return render_template(
        "pallet_editar.html",
        pallet=pallet, items=items, productos=productos, proveedores=proveedores
    )


# ---------------------------------------------------------------
# Mantenedor de Usuarios (solo Administrador)
# ---------------------------------------------------------------

from werkzeug.security import generate_password_hash


@app.route("/usuarios", methods=["GET", "POST"])
@admin_requerido
def usuarios():
    conn = get_connection()
    cursor = conn.cursor()

    mensaje = None
    error = None

    if request.method == "POST":
        nombre = request.form["nombre"]
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        # Por seguridad: desde la pagina solo se pueden crear Operadores.
        # Para crear otro Administrador, hay que hacerlo desde la base de datos.
        rol = "Operador"

        # Verificar que el usuario no exista
        cursor.execute("SELECT COUNT(*) FROM tbl_usuarios WHERE usuario = %s", (usuario,))
        if cursor.fetchone()[0] > 0:
            error = f"El usuario '{usuario}' ya existe."
        else:
            clave_hash = generate_password_hash(clave)
            cursor.execute(
                """
                INSERT INTO tbl_usuarios (nombre, usuario, clave, rol)
                VALUES (%s, %s, %s, %s)
                """,
                (nombre, usuario, clave_hash, rol)
            )
            conn.commit()
            mensaje = f"Operador '{usuario}' creado correctamente."

    cursor.execute(
        "SELECT id_usuario, nombre, usuario, rol, activo FROM tbl_usuarios ORDER BY usuario"
    )
    lista_usuarios = cursor.fetchall()
    conn.close()

    return render_template("usuarios.html", usuarios=lista_usuarios, mensaje=mensaje, error=error)


@app.route("/usuarios/desactivar/<int:id_usuario>")
@admin_requerido
def desactivar_usuario(id_usuario):
    if id_usuario == session.get("usuario_id"):
        return "No puedes desactivarte a ti mismo.", 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tbl_usuarios SET activo = CASE WHEN activo = TRUE THEN 0 ELSE 1 END WHERE id_usuario = %s",
        (id_usuario,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("usuarios"))


@app.route("/usuarios/cambiar_clave/<int:id_usuario>", methods=["POST"])
@admin_requerido
def cambiar_clave_usuario(id_usuario):
    nueva_clave = request.form["nueva_clave"]
    clave_hash = generate_password_hash(nueva_clave)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tbl_usuarios SET clave = %s WHERE id_usuario = %s",
        (clave_hash, id_usuario)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("usuarios"))


@app.route("/panel/detalle/<vista>")
@login_requerido
def detalle_panel(vista):
    conn = get_connection()
    cursor = conn.cursor()

    titulo = ""
    descripcion = ""
    columnas = ""
    filas = []

    if vista == "ocupacion":
        titulo = "Ocupacion de la bodega"
        descripcion = "Listado de todas las ubicaciones de racks y su estado."
        columnas = "ubicaciones"
        cursor.execute(
            """
            SELECT u.rack, u.nivel, u.posicion, u.estado, pa.id_pallet
            FROM tbl_ubicaciones u
            LEFT JOIN tbl_pallet_ubicacion pu
                ON pu.id_ubicacion = u.id_ubicacion AND pu.vigente = TRUE
            LEFT JOIN tbl_pallets pa ON pa.id_pallet = pu.id_pallet
            ORDER BY
                CAST(SUBSTRING(u.rack FROM 2) AS INTEGER),
                CAST(SUBSTRING(u.nivel FROM 2) AS INTEGER),
                CAST(u.posicion AS INTEGER)
            """
        )
        filas = cursor.fetchall()

    elif vista == "activos":
        titulo = "Pallets activos"
        descripcion = "Pallets que estan dentro de la bodega y aun no se han consumido completamente."
        columnas = "pallets"
        cursor.execute(
            """
            SELECT pa.id_pallet, pa.estado, pa.fecha_ingreso,
                   pv.nombre AS proveedor,
                   u.rack, u.nivel, u.posicion
            FROM tbl_pallets pa
            JOIN tbl_empresas pv ON pv.id_empresa = pa.id_proveedor
            LEFT JOIN tbl_pallet_ubicacion pu
                ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
            LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
            WHERE pa.estado != 'Consumido'
            ORDER BY pa.fecha_ingreso DESC
            """
        )
        filas = cursor.fetchall()

    elif vista == "parciales":
        titulo = "Stock suelto en zona de piso"
        descripcion = "Cajas sueltas que se sacaron de pallets y estan en la zona de piso. Se consumen primero por FEFO."
        columnas = "stock_piso"
        cursor.execute(
            """
            SELECT sp.id_pallet_origen AS id_pallet, pr.nombre AS producto,
                   sp.cantidad, sp.fecha_vencimiento,
                   u.rack, u.nivel, u.posicion
            FROM tbl_stock_piso sp
            JOIN tbl_productos pr ON pr.id_producto = sp.id_producto
            JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
            WHERE sp.cantidad > 0
            ORDER BY sp.fecha_vencimiento ASC
            """
        )
        filas = cursor.fetchall()

    elif vista == "por_vencer":
        titulo = "Productos por vencer en los proximos 7 dias"
        descripcion = "Productos que ya estan vencidos (en rojo) o vencen pronto (en naranja). Conviene priorizarlos para picking."
        columnas = "vencer"
        cursor.execute(
            """
            SELECT pr.nombre AS producto, pa.id_pallet, pp.cantidad, pp.fecha_vencimiento,
                u.rack, u.nivel, u.posicion,
                (pp.fecha_vencimiento - CURRENT_DATE) AS dias_para_vencer
            FROM tbl_pallet_producto pp
            JOIN tbl_productos pr ON pr.id_producto = pp.id_producto
            JOIN tbl_pallets pa ON pa.id_pallet = pp.id_pallet
            LEFT JOIN tbl_pallet_ubicacion pu
                ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
            LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
            WHERE pp.cantidad > 0
                AND pp.fecha_vencimiento IS NOT NULL
                AND pp.fecha_vencimiento <= NOW() + INTERVAL '7 days'
            ORDER BY pp.fecha_vencimiento ASC
            """
        )
        filas = cursor.fetchall()

    else:
        conn.close()
        return redirect(url_for("dashboard"))

    conn.close()

    return render_template(
        "detalle_panel.html",
        titulo=titulo, descripcion=descripcion, columnas=columnas, filas=filas
    )


# ---------------------------------------------------------------
# Disponibilidad en vivo (para el formulario de picking)
# ---------------------------------------------------------------

@app.route("/picking/disponibilidad/<int:id_producto>")
@login_requerido
def disponibilidad_producto(id_producto):
    """
    Devuelve en JSON los pallets que tienen stock de este producto,
    en el ORDEN exacto en que el picking los va a tomar (FEFO + parciales primero).
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            pa.id_pallet, pp.cantidad, pp.cantidad_original, pp.fecha_vencimiento,
            u.rack, u.nivel, u.posicion,
            CASE WHEN EXISTS (
                SELECT 1 FROM tbl_movimientos m
                WHERE m.id_pallet = pa.id_pallet AND m.tipo_movimiento = 'Picking'
            ) THEN 1 ELSE 0 END AS es_parcial
        FROM tbl_pallet_producto pp
        JOIN tbl_pallets pa ON pa.id_pallet = pp.id_pallet
        LEFT JOIN tbl_pallet_ubicacion pu
            ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
        LEFT JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
        WHERE pp.id_producto = %s AND pp.cantidad > 0 AND pa.estado != 'Consumido'
            AND (u.rack LIKE 'R%%' OR u.rack IS NULL)
        ORDER BY
            CASE WHEN pp.cantidad < pp.cantidad_original
                      AND EXISTS (SELECT 1 FROM tbl_movimientos m
                                  WHERE m.id_pallet = pa.id_pallet AND m.tipo_movimiento = 'Picking')
                 THEN 0 ELSE 1 END,
            CASE WHEN pp.fecha_vencimiento IS NULL THEN 1 ELSE 0 END,
            pp.fecha_vencimiento ASC
        """,
        (id_producto,)
    )
    pallets = cursor.fetchall()

    # Tambien traer stock suelto en piso de este producto
    cursor.execute(
        """
        SELECT sp.cantidad, sp.fecha_vencimiento, u.posicion
        FROM tbl_stock_piso sp
        JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
        WHERE sp.id_producto = %s AND sp.cantidad > 0
        """,
        (id_producto,)
    )
    en_piso = cursor.fetchall()
    total_piso = sum(p.cantidad for p in en_piso)

    conn.close()

    resultado = []
    total = 0
    for p in pallets:
        ubicacion = (
            f"{p.rack}-{p.nivel}-Pos {p.posicion}"
            if p.rack else "Sin ubicacion"
        )
        resultado.append({
            "id_pallet": p.id_pallet,
            "cantidad": p.cantidad,
            "cantidad_original": p.cantidad_original,
            "fecha_vencimiento": str(p.fecha_vencimiento) if p.fecha_vencimiento else None,
            "ubicacion": ubicacion,
            "es_parcial": bool(p.es_parcial)
        })
        total += p.cantidad

    return jsonify({
        "disponible": total > 0 or total_piso > 0,
        "total_en_racks": total,
        "total_en_piso": total_piso,
        "total_disponible": total + total_piso,
        "pallets": resultado
    })




@app.route("/pallets/historial/<int:id_pallet>")
@login_requerido
def historial_pallet(id_pallet):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.fecha, m.tipo_movimiento, m.observacion, m.destino_tipo,
               e.nombre AS cliente_nombre
        FROM tbl_movimientos m
        LEFT JOIN tbl_empresas e ON e.id_empresa = m.id_cliente
        WHERE m.id_pallet = %s
        ORDER BY m.fecha ASC
        """,
        (id_pallet,)
    )
    movimientos = cursor.fetchall()

    cursor.execute(
        """
        SELECT pu.fecha_asignacion, pu.vigente, u.rack, u.nivel, u.posicion
        FROM tbl_pallet_ubicacion pu
        JOIN tbl_ubicaciones u ON u.id_ubicacion = pu.id_ubicacion
        WHERE pu.id_pallet = %s
        ORDER BY pu.fecha_asignacion ASC
        """,
        (id_pallet,)
    )
    ubicaciones = cursor.fetchall()
    conn.close()

    return render_template(
        "historial_pallet.html",
        id_pallet=id_pallet,
        movimientos=movimientos,
        ubicaciones=ubicaciones
    )


@app.route("/pallets/qr/<int:id_pallet>")
@login_requerido
def descargar_qr(id_pallet):
    """Genera una pagina imprimible con el QR del pallet."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT codigo_qr FROM tbl_pallets WHERE id_pallet = %s",
        (id_pallet,)
    )
    fila = cursor.fetchone()
    conn.close()

    if fila is None:
        return "Pallet no encontrado.", 404

    url_consulta = request.host_url.rstrip("/") + url_for(
        "consulta_pallet_detalle", codigo_qr=fila.codigo_qr
    )
    img = qrcode.make(url_consulta)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"""
    <!DOCTYPE html>
    <html><head>
        <title>QR Pallet {id_pallet}</title>
        <style>
            body {{ font-family: Arial; text-align: center; padding: 40px; }}
            @media print {{
                button {{ display: none; }}
            }}
        </style>
    </head><body>
        <h2>Pallet N {id_pallet}</h2>
        <img src="data:image/png;base64,{qr_base64}" width="300">
        <p style="font-size:12px; color:#888;">{url_consulta}</p>
        <br>
        <button onclick="window.print()" style="padding:10px 20px; font-size:16px; cursor:pointer;">Imprimir QR</button>
    </body></html>
    """


# ---------------------------------------------------------------
# Despacho directo desde detalle del pallet
# ---------------------------------------------------------------

@app.route("/pallets/despachar/<int:id_pallet>", methods=["POST"])
@login_requerido
def despachar_pallet(id_pallet):
    conn = get_connection()
    cursor = conn.cursor()

    cantidad_raw = request.form.get("cantidad", "").strip()
    destino_tipo = request.form.get("destino_tipo", "Produccion1")

    destino_texto = destino_tipo
    if destino_tipo == "Produccion1":
        destino_texto = "Sala de produccion 1"
    elif destino_tipo == "Produccion2":
        destino_texto = "Sala de produccion 2"
    elif destino_tipo == "PlantaPrincipal":
        destino_texto = "Planta principal HC Alimentos"

    # Obtener datos del pallet
    cursor.execute(
        """
        SELECT pa.id_pallet, pa.estado, pu.id_ubicacion
        FROM tbl_pallets pa
        LEFT JOIN tbl_pallet_ubicacion pu
            ON pu.id_pallet = pa.id_pallet AND pu.vigente = TRUE
        WHERE pa.id_pallet = %s AND pa.estado != 'Consumido'
        """,
        (id_pallet,)
    )
    pallet = cursor.fetchone()

    if pallet is None:
        conn.close()
        return redirect(url_for("ver_pallet", id_pallet=id_pallet))

    # Obtener productos del pallet
    cursor.execute(
        "SELECT id_pallet_producto, id_producto, cantidad, fecha_vencimiento FROM tbl_pallet_producto WHERE id_pallet = %s AND cantidad > 0",
        (id_pallet,)
    )
    productos = cursor.fetchall()

    total_en_pallet = sum(p.cantidad for p in productos)

    if not cantidad_raw:
        # ============================================
        # DESPACHO COMPLETO: se va todo el pallet
        # ============================================
        for p in productos:
            cursor.execute(
                "UPDATE tbl_pallet_producto SET cantidad = 0 WHERE id_pallet_producto = %s",
                (p.id_pallet_producto,)
            )

        cursor.execute(
            "UPDATE tbl_pallets SET estado = 'Consumido' WHERE id_pallet = %s",
            (id_pallet,)
        )
        cursor.execute(
            "UPDATE tbl_pallet_ubicacion SET vigente = FALSE WHERE id_pallet = %s AND vigente = TRUE",
            (id_pallet,)
        )
        if pallet.id_ubicacion:
            cursor.execute(
                "UPDATE tbl_ubicaciones SET estado = 'Libre' WHERE id_ubicacion = %s",
                (pallet.id_ubicacion,)
            )

        cursor.execute(
            """
            INSERT INTO tbl_movimientos
                (id_pallet, tipo_movimiento, observacion, destino_tipo)
            VALUES (%s, 'Despacho', %s, %s)
            """,
            (id_pallet,
             f"Pallet completo despachado ({total_en_pallet} cajas). Destino: {destino_texto}.",
             destino_tipo)
        )

        conn.commit()
        conn.close()

        return render_template(
            "picking_resultado.html",
            movimientos=[{
                "id_pallet": id_pallet,
                "origen": "Pallet completo",
                "tomado": total_en_pallet,
                "restante_origen": 0,
                "fecha_vencimiento": None,
                "posicion_destino": destino_texto + " (pallet completo despachado)"
            }],
            faltante=0,
            destino_tipo=destino_tipo,
            cliente_nombre=None,
            tipo_accion="despacho"
        )

    else:
        # ============================================
        # PICKING PARCIAL: cajas van al piso
        # ============================================
        cantidad_solicitada = int(cantidad_raw)
        capacidad_piso = CAJAS_POR_PALLET_ESTANDAR

        cursor.execute(
            """
            SELECT id_ubicacion, rack, nivel, posicion
            FROM tbl_ubicaciones
            WHERE rack = 'P' AND estado = 'Libre'
            ORDER BY CAST(posicion AS INTEGER)
            """
        )
        posiciones_piso_libres = cursor.fetchall()
        piso_idx = 0

        restante = cantidad_solicitada
        movimientos = []

        # Tomar de los productos por FEFO
        productos_ordenados = sorted(productos, key=lambda p: p.fecha_vencimiento or "9999-12-31")

        for p in productos_ordenados:
            if restante <= 0:
                break

            tomado = min(p.cantidad, restante)
            nueva_cantidad = p.cantidad - tomado
            restante -= tomado

            cursor.execute(
                "UPDATE tbl_pallet_producto SET cantidad = %s WHERE id_pallet_producto = %s",
                (nueva_cantidad, p.id_pallet_producto)
            )

            # Colocar en piso
            cantidad_a_colocar = tomado
            venc = p.fecha_vencimiento
            detalle_destinos = []

            while cantidad_a_colocar > 0:
                cursor.execute(
                    """
                    SELECT sp.id_ubicacion,
                           u.rack, u.nivel, u.posicion,
                           (SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso
                            WHERE id_ubicacion = sp.id_ubicacion) AS total_en_pos
                    FROM tbl_stock_piso sp
                    JOIN tbl_ubicaciones u ON u.id_ubicacion = sp.id_ubicacion
                    WHERE sp.id_producto = %s
                    GROUP BY sp.id_ubicacion, u.rack, u.nivel, u.posicion
                    HAVING (SELECT COALESCE(SUM(cantidad),0) FROM tbl_stock_piso
                            WHERE id_ubicacion = sp.id_ubicacion) < %s
                    ORDER BY u.rack
                    LIMIT 1
                    """,
                    (p.id_producto, capacidad_piso)
                )
                pos_existente = cursor.fetchone()

                if pos_existente:
                    espacio = capacidad_piso - pos_existente.total_en_pos
                    a_meter = min(espacio, cantidad_a_colocar)
                    cursor.execute(
                        """
                        INSERT INTO tbl_stock_piso
                            (id_ubicacion, id_producto, id_pallet_origen, cantidad, fecha_vencimiento)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (pos_existente.id_ubicacion, p.id_producto, id_pallet, a_meter, venc)
                    )
                    detalle_destinos.append(f"P-N1-Pos {pos_existente.posicion} (+{a_meter})")
                    cantidad_a_colocar -= a_meter
                elif piso_idx < len(posiciones_piso_libres):
                    pos = posiciones_piso_libres[piso_idx]
                    a_meter = min(capacidad_piso, cantidad_a_colocar)
                    cursor.execute(
                        """
                        INSERT INTO tbl_stock_piso
                            (id_ubicacion, id_producto, id_pallet_origen, cantidad, fecha_vencimiento)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (pos.id_ubicacion, p.id_producto, id_pallet, a_meter, venc)
                    )
                    cursor.execute(
                        "UPDATE tbl_ubicaciones SET estado = 'Ocupada' WHERE id_ubicacion = %s",
                        (pos.id_ubicacion,)
                    )
                    detalle_destinos.append(f"P-N1-Pos {pos.posicion} (+{a_meter})")
                    cantidad_a_colocar -= a_meter
                    piso_idx += 1
                else:
                    detalle_destinos.append(f"SIN ESPACIO en piso para {cantidad_a_colocar}")
                    cantidad_a_colocar = 0

            destino_str = ", ".join(detalle_destinos)
            movimientos.append({
                "id_pallet": id_pallet,
                "origen": "Pallet " + str(id_pallet),
                "tomado": tomado,
                "restante_origen": nueva_cantidad,
                "fecha_vencimiento": venc,
                "posicion_destino": destino_str
            })

        # Revisar si el pallet quedo vacio
        cursor.execute(
            "SELECT COALESCE(SUM(cantidad), 0) FROM tbl_pallet_producto WHERE id_pallet = %s",
            (id_pallet,)
        )
        total_restante = cursor.fetchone()[0]
        if total_restante == 0:
            cursor.execute(
                "UPDATE tbl_pallets SET estado = 'Consumido' WHERE id_pallet = %s",
                (id_pallet,)
            )
            cursor.execute(
                "UPDATE tbl_pallet_ubicacion SET vigente = FALSE WHERE id_pallet = %s AND vigente = TRUE",
                (id_pallet,)
            )
            if pallet.id_ubicacion:
                cursor.execute(
                    "UPDATE tbl_ubicaciones SET estado = 'Libre' WHERE id_ubicacion = %s",
                    (pallet.id_ubicacion,)
                )

        cursor.execute(
            """
            INSERT INTO tbl_movimientos
                (id_pallet, tipo_movimiento, observacion, destino_tipo, id_cliente)
            VALUES (%s, 'Picking', %s, 'Piso', NULL)
            """,
            (id_pallet,
             f"Se retiraron {cantidad_solicitada - restante} cajas del pallet. Llevadas a piso.")
        )

        conn.commit()
        conn.close()

        return render_template(
            "picking_resultado.html",
            movimientos=movimientos,
            faltante=restante,
            destino_tipo="Zona de piso",
            cliente_nombre=None,
            tipo_accion="picking"
        )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
