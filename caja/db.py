"""Capa de datos: SQLite local, sin servidores, sin Internet (plan.md §2, §6.1).

Garantías que implementa este módulo:
- WAL: un apagado repentino no corrompe la base de datos (plan.md §4).
- Cada venta se registra en una transacción atómica: o queda completa
  con su detalle, o no queda nada.
- Diario de venta en curso: si la aplicación se cierra a mitad de una
  venta, el carrito se recupera al volver a entrar.
- Respaldos automáticos con la API de copia de SQLite.
- Los detalles de venta guardan el nombre y precio del producto en el
  momento de la venta, así el historial sobrevive a ediciones o
  eliminaciones de productos.
"""

import json
import logging
import sqlite3
from pathlib import Path

from . import seguridad
from .rutas import RAIZ
from .util import ahora_iso

DATOS = RAIZ / "datos"
RUTA_BD = DATOS / "caja.db"
RUTA_DIARIO = DATOS / "venta_en_curso.json"
CARPETA_RESPALDOS = DATOS / "respaldos"
CARPETA_TICKETS = DATOS / "tickets"
RUTA_LOG = DATOS / "eventos.log"

_MAX_RESPALDOS = 15

_con = None

log = logging.getLogger("caja")


# ---------------------------------------------------------------- conexión

def conexion() -> sqlite3.Connection:
    global _con
    if _con is None:
        DATOS.mkdir(exist_ok=True)
        _con = sqlite3.connect(RUTA_BD)
        _con.row_factory = sqlite3.Row
        _con.execute("PRAGMA journal_mode=WAL")
        _con.execute("PRAGMA synchronous=NORMAL")
        _con.execute("PRAGMA foreign_keys=ON")
    return _con


def cerrar():
    global _con
    if _con is not None:
        _con.close()
        _con = None


# ---------------------------------------------------------------- esquema

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL,
    usuario     TEXT NOT NULL UNIQUE,
    clave_hash  TEXT NOT NULL,
    sal         TEXT NOT NULL,
    rol         TEXT NOT NULL CHECK (rol IN ('administrador', 'cajero')),
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS productos (
    id            INTEGER PRIMARY KEY,
    codigo_barras TEXT NOT NULL UNIQUE,
    nombre        TEXT NOT NULL,
    precio        INTEGER NOT NULL CHECK (precio >= 0),
    categoria     TEXT NOT NULL DEFAULT 'General',
    stock         INTEGER NOT NULL DEFAULT 0,
    activo        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ventas (
    id             INTEGER PRIMARY KEY,
    numero_factura TEXT NOT NULL UNIQUE,
    fecha          TEXT NOT NULL,
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id),
    nombre_cajero  TEXT NOT NULL,
    subtotal       INTEGER NOT NULL,
    iva_porcentaje INTEGER NOT NULL DEFAULT 0,
    iva            INTEGER NOT NULL DEFAULT 0,
    total          INTEGER NOT NULL,
    metodo_pago    TEXT NOT NULL,
    recibido       INTEGER NOT NULL,
    cambio         INTEGER NOT NULL,
    entrenamiento  INTEGER NOT NULL DEFAULT 0,
    cliente_nombre TEXT,
    cliente_nit    TEXT,
    codigo_autorizacion TEXT
);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id          INTEGER PRIMARY KEY,
    id_venta    INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    id_producto INTEGER,
    codigo      TEXT NOT NULL,
    nombre      TEXT NOT NULL,
    cantidad    INTEGER NOT NULL,
    precio      INTEGER NOT NULL,
    subtotal    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sesiones (
    id            INTEGER PRIMARY KEY,
    id_usuario    INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_ingreso TEXT NOT NULL,
    fecha_salida  TEXT
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ventas_fecha   ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_detalle_venta  ON detalle_venta(id_venta);
CREATE INDEX IF NOT EXISTS idx_productos_nom  ON productos(nombre);
"""

_CONFIG_DEFECTO = {
    "iva_porcentaje": "0",
    "modo_entrenamiento": "0",
    "imprimir_auto": "0",
    "controlar_stock": "0",
    "consecutivo_factura": "0",
    "nombre_negocio": "SISTEMA DE CAJA DIDÁCTICO",
}

# Productos de ejemplo para empezar a practicar (plan.md §1.8).
_PRODUCTOS_EJEMPLO = [
    ("7701001", "Arroz Diana 500g", 4500, "Granos", 50),
    ("7701002", "Azúcar Manuelita 1kg", 5200, "Granos", 40),
    ("7701003", "Aceite Premier 1L", 14000, "Aceites", 30),
    ("7701004", "Leche Alquería 1L", 4800, "Lácteos", 60),
    ("7701005", "Pan tajado Bimbo", 6500, "Panadería", 25),
    ("7701006", "Huevos AA x12", 12000, "Huevos", 35),
    ("7701007", "Café Sello Rojo 250g", 9800, "Café", 45),
    ("7701008", "Chocolate Corona 500g", 8200, "Café", 30),
    ("7701009", "Panela redonda", 3500, "Endulzantes", 55),
    ("7701010", "Sal Refisal 500g", 1800, "Condimentos", 70),
    ("7701011", "Pasta Doria 250g", 3200, "Pastas", 48),
    ("7701012", "Atún Van Camps lomo", 7500, "Enlatados", 32),
    ("7701013", "Jabón Rey barra", 2900, "Aseo", 44),
    ("7701014", "Detergente Fab 1kg", 11500, "Aseo", 28),
    ("7701015", "Papel higiénico x4", 9200, "Aseo", 36),
    ("7701016", "Gaseosa Coca-Cola 1.5L", 6800, "Bebidas", 50),
    ("7701017", "Agua Cristal 600ml", 2000, "Bebidas", 80),
    ("7701018", "Galletas Festival", 2500, "Snacks", 65),
    ("7701019", "Arepas blancas x5", 4200, "Panadería", 22),
    ("7701020", "Mantequilla Rama 250g", 5600, "Lácteos", 26),
]

_USUARIOS_EJEMPLO = [
    ("Administrador del Curso", "admin", "admin123", "administrador"),
    ("Cajero de Práctica", "cajero", "cajero123", "cajero"),
]


def _migrar(con):
    """Agrega columnas nuevas a bases de datos creadas por versiones
    anteriores, sin tocar los datos existentes."""
    columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(ventas)")}
    extras = {
        "cliente_nombre": "TEXT",
        "cliente_nit": "TEXT",
        "codigo_autorizacion": "TEXT",
    }
    for columna, tipo in extras.items():
        if columna not in columnas:
            con.execute(f"ALTER TABLE ventas ADD COLUMN {columna} {tipo}")


def iniciar():
    """Crea la base de datos, las carpetas y los datos semilla si no existen."""
    DATOS.mkdir(exist_ok=True)
    CARPETA_RESPALDOS.mkdir(exist_ok=True)
    CARPETA_TICKETS.mkdir(exist_ok=True)
    con = conexion()
    con.executescript(_ESQUEMA)
    _migrar(con)
    for clave, valor in _CONFIG_DEFECTO.items():
        con.execute(
            "INSERT OR IGNORE INTO configuracion(clave, valor) VALUES (?, ?)",
            (clave, valor),
        )
    # Opción retirada del sistema (el quiz de cambio no existe en un POS real)
    con.execute("DELETE FROM configuracion WHERE clave = 'practicar_cambio'")
    if con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        _sembrar_usuarios(con)
    if con.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
        _sembrar_productos(con)
    con.commit()


def _sembrar_usuarios(con):
    for nombre, usuario, clave, rol in _USUARIOS_EJEMPLO:
        sal = seguridad.nueva_sal()
        con.execute(
            "INSERT INTO usuarios(nombre, usuario, clave_hash, sal, rol) "
            "VALUES (?, ?, ?, ?, ?)",
            (nombre, usuario, seguridad.hash_clave(clave, sal), sal, rol),
        )


def _sembrar_productos(con):
    con.executemany(
        "INSERT INTO productos(codigo_barras, nombre, precio, categoria, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        _PRODUCTOS_EJEMPLO,
    )


# ---------------------------------------------------------------- configuración

def obtener_config(clave: str, defecto: str = "") -> str:
    fila = conexion().execute(
        "SELECT valor FROM configuracion WHERE clave = ?", (clave,)
    ).fetchone()
    return fila["valor"] if fila else defecto


def guardar_config(clave: str, valor: str):
    con = conexion()
    con.execute(
        "INSERT INTO configuracion(clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, str(valor)),
    )
    con.commit()


def config_activa(clave: str) -> bool:
    return obtener_config(clave, "0") == "1"


# ---------------------------------------------------------------- usuarios

def autenticar(usuario: str, clave: str):
    """Devuelve el usuario como dict si las credenciales son válidas."""
    fila = conexion().execute(
        "SELECT * FROM usuarios WHERE usuario = ? AND activo = 1",
        (usuario.strip().lower(),),
    ).fetchone()
    if fila and seguridad.verificar_clave(clave, fila["sal"], fila["clave_hash"]):
        return dict(fila)
    return None


def listar_usuarios():
    filas = conexion().execute(
        "SELECT id, nombre, usuario, rol, activo FROM usuarios ORDER BY nombre"
    ).fetchall()
    return [dict(f) for f in filas]


def crear_usuario(nombre: str, usuario: str, clave: str, rol: str):
    usuario = usuario.strip().lower()
    con = conexion()
    if con.execute("SELECT 1 FROM usuarios WHERE usuario = ?",
                   (usuario,)).fetchone():
        raise ValueError(f"Ya existe un usuario con el ingreso «{usuario}».")
    sal = seguridad.nueva_sal()
    con.execute(
        "INSERT INTO usuarios(nombre, usuario, clave_hash, sal, rol) "
        "VALUES (?, ?, ?, ?, ?)",
        (nombre.strip(), usuario, seguridad.hash_clave(clave, sal), sal, rol),
    )
    con.commit()
    log.info("Usuario creado: %s (%s)", usuario, rol)


def actualizar_usuario(id_usuario: int, nombre: str, rol: str, activo: bool):
    """Actualiza nombre, rol y estado. Nunca permite quedarse sin un
    administrador activo (plan.md §6.9)."""
    con = conexion()
    actual = con.execute("SELECT rol, activo FROM usuarios WHERE id = ?",
                         (id_usuario,)).fetchone()
    if actual is None:
        raise ValueError("El usuario no existe.")
    pierde_admin = (actual["rol"] == "administrador" and actual["activo"]
                    and (rol != "administrador" or not activo))
    if pierde_admin:
        otros = con.execute(
            "SELECT COUNT(*) FROM usuarios WHERE rol = 'administrador' "
            "AND activo = 1 AND id != ?", (id_usuario,)).fetchone()[0]
        if otros == 0:
            raise ValueError("Debe existir al menos un administrador activo.")
    con.execute(
        "UPDATE usuarios SET nombre = ?, rol = ?, activo = ? WHERE id = ?",
        (nombre.strip(), rol, 1 if activo else 0, id_usuario),
    )
    con.commit()
    log.info("Usuario %s actualizado (rol=%s activo=%s)", id_usuario, rol, activo)


def cambiar_clave(id_usuario: int, clave_nueva: str):
    sal = seguridad.nueva_sal()
    con = conexion()
    con.execute(
        "UPDATE usuarios SET clave_hash = ?, sal = ? WHERE id = ?",
        (seguridad.hash_clave(clave_nueva, sal), sal, id_usuario),
    )
    con.commit()


def abrir_sesion(id_usuario: int) -> int:
    con = conexion()
    cur = con.execute(
        "INSERT INTO sesiones(id_usuario, fecha_ingreso) VALUES (?, ?)",
        (id_usuario, ahora_iso()),
    )
    con.commit()
    return cur.lastrowid


def cerrar_sesion(id_sesion: int):
    con = conexion()
    con.execute(
        "UPDATE sesiones SET fecha_salida = ? WHERE id = ?",
        (ahora_iso(), id_sesion),
    )
    con.commit()


# ---------------------------------------------------------------- productos

def buscar_por_codigo(codigo: str):
    fila = conexion().execute(
        "SELECT * FROM productos WHERE codigo_barras = ? AND activo = 1",
        (codigo.strip(),),
    ).fetchone()
    return dict(fila) if fila else None


def buscar_por_nombre(texto: str, limite: int = 30):
    filas = conexion().execute(
        "SELECT * FROM productos WHERE activo = 1 AND "
        "(nombre LIKE ? OR categoria LIKE ?) ORDER BY nombre LIMIT ?",
        (f"%{texto.strip()}%", f"%{texto.strip()}%", limite),
    ).fetchall()
    return [dict(f) for f in filas]


def listar_productos(filtro: str = ""):
    if filtro.strip():
        filas = conexion().execute(
            "SELECT * FROM productos WHERE activo = 1 AND "
            "(nombre LIKE ? OR codigo_barras LIKE ? OR categoria LIKE ?) "
            "ORDER BY nombre",
            (f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"),
        ).fetchall()
    else:
        filas = conexion().execute(
            "SELECT * FROM productos WHERE activo = 1 ORDER BY nombre"
        ).fetchall()
    return [dict(f) for f in filas]


def crear_producto(codigo: str, nombre: str, precio: int, categoria: str, stock: int):
    """Crea un producto. Si existe uno inactivo con el mismo código, lo reactiva."""
    con = conexion()
    existente = con.execute(
        "SELECT id, activo FROM productos WHERE codigo_barras = ?", (codigo,)
    ).fetchone()
    if existente:
        if existente["activo"]:
            raise ValueError(f"Ya existe un producto con el código {codigo}.")
        con.execute(
            "UPDATE productos SET nombre=?, precio=?, categoria=?, stock=?, activo=1 "
            "WHERE id=?",
            (nombre, precio, categoria, stock, existente["id"]),
        )
    else:
        con.execute(
            "INSERT INTO productos(codigo_barras, nombre, precio, categoria, stock) "
            "VALUES (?, ?, ?, ?, ?)",
            (codigo, nombre, precio, categoria, stock),
        )
    con.commit()


def actualizar_producto(id_prod: int, codigo, nombre, precio, categoria, stock):
    con = conexion()
    duplicado = con.execute(
        "SELECT id FROM productos WHERE codigo_barras = ? AND id != ?",
        (codigo, id_prod),
    ).fetchone()
    if duplicado:
        raise ValueError(f"Otro producto ya usa el código {codigo}.")
    con.execute(
        "UPDATE productos SET codigo_barras=?, nombre=?, precio=?, categoria=?, "
        "stock=? WHERE id=?",
        (codigo, nombre, precio, categoria, stock, id_prod),
    )
    con.commit()


def eliminar_producto(id_prod: int):
    """Baja lógica: el historial de ventas conserva su propia copia de los datos."""
    con = conexion()
    con.execute("UPDATE productos SET activo = 0 WHERE id = ?", (id_prod,))
    con.commit()


# ---------------------------------------------------------------- ventas

def registrar_venta(usuario: dict, items: list, iva_porcentaje: int,
                    metodo_pago: str, recibido: int, entrenamiento: bool,
                    controlar_stock: bool, codigo_autorizacion: str = None,
                    cliente_nombre: str = "", cliente_nit: str = "") -> dict:
    """Registra la venta completa en una sola transacción atómica.

    `items`: lista de dicts con id, codigo, nombre, precio, cantidad.
    `cliente_nombre`/`cliente_nit`: datos opcionales de facturación a
    nombre de una empresa (plan.md). `codigo_autorizacion`: código que
    entrega el datáfono simulado o la pasarela de transferencia.
    Devuelve la venta completa (con número de factura y detalles) para el recibo.
    """
    subtotal = sum(it["precio"] * it["cantidad"] for it in items)
    iva = round(subtotal * iva_porcentaje / 100)
    total = subtotal + iva
    cambio = recibido - total
    fecha = ahora_iso()

    con = conexion()
    try:
        con.execute("BEGIN IMMEDIATE")
        consecutivo = int(con.execute(
            "SELECT valor FROM configuracion WHERE clave = 'consecutivo_factura'"
        ).fetchone()["valor"]) + 1
        prefijo = "E" if entrenamiento else "F"
        numero = f"{prefijo}-{consecutivo:06d}"

        cur = con.execute(
            "INSERT INTO ventas(numero_factura, fecha, id_usuario, nombre_cajero, "
            "subtotal, iva_porcentaje, iva, total, metodo_pago, recibido, cambio, "
            "entrenamiento, cliente_nombre, cliente_nit, codigo_autorizacion) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (numero, fecha, usuario["id"], usuario["nombre"], subtotal,
             iva_porcentaje, iva, total, metodo_pago, recibido, cambio,
             1 if entrenamiento else 0, cliente_nombre.strip() or None,
             cliente_nit.strip() or None, codigo_autorizacion),
        )
        id_venta = cur.lastrowid

        for it in items:
            con.execute(
                "INSERT INTO detalle_venta(id_venta, id_producto, codigo, nombre, "
                "cantidad, precio, subtotal) VALUES (?,?,?,?,?,?,?)",
                (id_venta, it["id"], it["codigo"], it["nombre"], it["cantidad"],
                 it["precio"], it["precio"] * it["cantidad"]),
            )
            # El modo entrenamiento nunca toca el inventario (plan.md §1.8).
            if controlar_stock and not entrenamiento:
                con.execute(
                    "UPDATE productos SET stock = stock - ? WHERE id = ?",
                    (it["cantidad"], it["id"]),
                )

        con.execute(
            "UPDATE configuracion SET valor = ? WHERE clave = 'consecutivo_factura'",
            (str(consecutivo),),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise

    log.info("Venta %s registrada: total=%s metodo=%s cajero=%s",
             numero, total, metodo_pago, usuario["usuario"])
    return obtener_venta(id_venta)


def obtener_venta(id_venta: int):
    con = conexion()
    venta = con.execute("SELECT * FROM ventas WHERE id = ?", (id_venta,)).fetchone()
    if not venta:
        return None
    venta = dict(venta)
    venta["detalles"] = [
        dict(f) for f in con.execute(
            "SELECT * FROM detalle_venta WHERE id_venta = ? ORDER BY id",
            (id_venta,),
        ).fetchall()
    ]
    return venta


def buscar_ventas(desde: str = "", hasta: str = "", numero: str = "",
                  incluir_entrenamiento: bool = True):
    """Busca ventas por rango de fechas ISO (AAAA-MM-DD) o número de factura."""
    condiciones, parametros = [], []
    if numero.strip():
        condiciones.append("numero_factura LIKE ?")
        parametros.append(f"%{numero.strip().upper()}%")
    else:
        if desde:
            condiciones.append("fecha >= ?")
            parametros.append(desde + " 00:00:00")
        if hasta:
            condiciones.append("fecha <= ?")
            parametros.append(hasta + " 23:59:59")
    if not incluir_entrenamiento:
        condiciones.append("entrenamiento = 0")
    sql = "SELECT * FROM ventas"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY fecha DESC, id DESC LIMIT 500"
    return [dict(f) for f in conexion().execute(sql, parametros).fetchall()]


# ---------------------------------------------------------------- reportes

def reporte_resumen(desde: str, hasta: str):
    fila = conexion().execute(
        "SELECT COUNT(*) AS numero_ventas, COALESCE(SUM(total), 0) AS total_vendido "
        "FROM ventas WHERE entrenamiento = 0 AND fecha >= ? AND fecha <= ?",
        (desde + " 00:00:00", hasta + " 23:59:59"),
    ).fetchone()
    return dict(fila)


def reporte_por_dia(desde: str, hasta: str):
    filas = conexion().execute(
        "SELECT substr(fecha, 1, 10) AS dia, COUNT(*) AS ventas, "
        "SUM(total) AS total FROM ventas "
        "WHERE entrenamiento = 0 AND fecha >= ? AND fecha <= ? "
        "GROUP BY dia ORDER BY dia DESC",
        (desde + " 00:00:00", hasta + " 23:59:59"),
    ).fetchall()
    return [dict(f) for f in filas]


def reporte_top_productos(desde: str, hasta: str, limite: int = 10):
    filas = conexion().execute(
        "SELECT dv.nombre, SUM(dv.cantidad) AS unidades, SUM(dv.subtotal) AS total "
        "FROM detalle_venta dv JOIN ventas v ON v.id = dv.id_venta "
        "WHERE v.entrenamiento = 0 AND v.fecha >= ? AND v.fecha <= ? "
        "GROUP BY dv.nombre ORDER BY unidades DESC LIMIT ?",
        (desde + " 00:00:00", hasta + " 23:59:59", limite),
    ).fetchall()
    return [dict(f) for f in filas]


# ------------------------------------------------- diario de venta en curso

def guardar_diario(items: list):
    """Persiste el carrito tras cada cambio: si la app muere, nada se pierde."""
    try:
        RUTA_DIARIO.write_text(
            json.dumps({"items": items, "fecha": ahora_iso()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        log.exception("No se pudo escribir el diario de venta en curso")


def leer_diario():
    if not RUTA_DIARIO.exists():
        return None
    try:
        datos = json.loads(RUTA_DIARIO.read_text(encoding="utf-8"))
        return datos if datos.get("items") else None
    except (OSError, ValueError):
        log.exception("Diario de venta ilegible; se descarta")
        return None


def borrar_diario():
    try:
        RUTA_DIARIO.unlink(missing_ok=True)
    except OSError:
        log.exception("No se pudo borrar el diario de venta")


# ---------------------------------------------------------------- respaldos

def respaldar() -> Path:
    """Copia íntegra de la BD con la API de respaldo de SQLite."""
    CARPETA_RESPALDOS.mkdir(exist_ok=True)
    from datetime import datetime
    destino = CARPETA_RESPALDOS / f"caja-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(destino) as copia:
        conexion().backup(copia)
    copia.close()
    # Conservar solo los más recientes para no acumular archivos (plan.md §6.10).
    respaldos = sorted(CARPETA_RESPALDOS.glob("caja-*.db"))
    for viejo in respaldos[:-_MAX_RESPALDOS]:
        viejo.unlink(missing_ok=True)
    log.info("Respaldo creado: %s", destino.name)
    return destino


def reiniciar_datos():
    """Reinicio entre clases (plan.md §1.8): borra ventas, sesiones e
    historial, restaura los productos de ejemplo y el consecutivo.
    Conserva usuarios y configuración. Hace respaldo previo."""
    respaldar()
    con = conexion()
    con.executescript(
        "DELETE FROM detalle_venta; DELETE FROM ventas; DELETE FROM sesiones; "
        "DELETE FROM productos;"
    )
    _sembrar_productos(con)
    con.execute(
        "UPDATE configuracion SET valor = '0' WHERE clave = 'consecutivo_factura'"
    )
    con.commit()
    con.execute("VACUUM")
    borrar_diario()
    log.info("Base de datos reiniciada para nueva clase")
