"""Generador de códigos de barras EAN-13 y Code 39 en Python puro (sin
librerías externas).

EAN-13 se usa para códigos generados por el sistema (prefijo 20-29,
reservado por el estándar real para uso interno de tienda / productos
sin marca) y para cualquier código ya guardado que tenga forma válida de
EAN-13. Code 39 es el respaldo universal: cualquier valor que no sea un
EAN-13 válido —por ejemplo los 7 dígitos de los productos de ejemplo,
"7701001".."7701020"— se renderiza en Code 39, que acepta letras,
números y unos pocos símbolos sin necesitar dígito verificador.

Las tablas de codificación son las del estándar público EAN-13/UPC-A y
Code 39. `autotest()` valida por autoconsistencia matemática (dígito
verificador, invariantes estructurales de las tablas) pero —igual que
con qr.py, ver memoria "nota-generador-qr"— NO prueba que un lector real
decodifique el código: eso se verificó con pyzbar instalado
temporalmente durante el desarrollo, nunca como dependencia del
producto (ver plan.md, decisión de códigos de barras).
"""

import secrets
from dataclasses import dataclass, field

from . import db, recibos
from .util import fmt_dinero

MM = 72 / 25.4  # 1 mm en puntos PDF

# ---------------------------------------------------------------- EAN-13

# Codificación "L" (paridad impar), 7 módulos por dígito 0-9. Tabla
# pública del estándar EAN-13/UPC-A. R = complemento bit a bit de L;
# G = R invertido (reflejado) — se derivan en código en vez de
# transcribir tres tablas, para no arriesgar un error de tipeo.
_EAN_L = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101",
    "4": "0100011", "5": "0110001", "6": "0101111", "7": "0111011",
    "8": "0110111", "9": "0001011",
}


def _ean_r(d: str) -> str:
    return "".join("1" if b == "0" else "0" for b in _EAN_L[d])


def _ean_g(d: str) -> str:
    return _ean_r(d)[::-1]


# Patrón L/G de los dígitos 2..7 según el primer dígito (implícito, no
# se dibuja) del código. Tabla pública estándar EAN-13.
_EAN_PARIDAD = {
    "0": "LLLLLL", "1": "LLGLGG", "2": "LLGGLG", "3": "LLGGGL",
    "4": "LGLLGG", "5": "LGGLLG", "6": "LGGGLL", "7": "LGLGLG",
    "8": "LGLGGL", "9": "LGGLGL",
}

_GUARDA_LATERAL = "101"    # 3 módulos: inicio y fin
_GUARDA_CENTRAL = "01010"  # 5 módulos: entre las dos mitades

PREFIJO_USO_INTERNO = range(20, 30)  # reservado de verdad por el estándar


def digito_verificador_ean13(doce_digitos: str) -> int:
    """Mod10 estándar EAN/UPC: peso 1 en posiciones impares (1ª, 3ª, ...
    contando desde la izquierda), peso 3 en las pares."""
    if len(doce_digitos) != 12 or not doce_digitos.isdigit():
        raise ValueError("Se requieren 12 dígitos para calcular el "
                         "verificador EAN-13.")
    total = sum(int(c) * (1 if i % 2 == 0 else 3)
               for i, c in enumerate(doce_digitos))
    return (10 - total % 10) % 10


def es_ean13_valido(codigo: str) -> bool:
    return (len(codigo) == 13 and codigo.isdigit()
            and digito_verificador_ean13(codigo[:12]) == int(codigo[12]))


def completar_ean13(codigo: str):
    """12 dígitos -> agrega el verificador correcto. 13 dígitos -> los
    devuelve solo si el verificador YA es correcto (si el dígito 13
    grabado está mal, no se corrige: el código impreso debe decodificar
    exactamente al mismo texto que quedó guardado en la base de datos, o
    escanear la etiqueta buscaría un producto distinto). None si no
    tiene forma de EAN-13 en absoluto."""
    codigo = codigo.strip()
    if len(codigo) == 12 and codigo.isdigit():
        return codigo + str(digito_verificador_ean13(codigo))
    if len(codigo) == 13 and es_ean13_valido(codigo):
        return codigo
    return None


def _modulos_ean13(codigo13: str) -> str:
    mitad_izquierda = codigo13[1:7]
    mitad_derecha = codigo13[7:13]
    paridad = _EAN_PARIDAD[codigo13[0]]
    izquierda = "".join(
        _EAN_L[d] if p == "L" else _ean_g(d)
        for d, p in zip(mitad_izquierda, paridad)
    )
    derecha = "".join(_ean_r(d) for d in mitad_derecha)
    return _GUARDA_LATERAL + izquierda + _GUARDA_CENTRAL + derecha + _GUARDA_LATERAL


# índices (inclusive) de los tramos de guarda dentro de los 95 módulos:
# se dibujan más altos que las barras de dígitos, como en un EAN-13 real.
_GUARDAS_EAN13 = ((0, 2), (45, 49), (92, 94))


# ---------------------------------------------------------------- Code 39

# 43 caracteres: 0-9, A-Z, - . $ / + % y espacio, más '*' de inicio/fin.
# Cada carácter son 9 elementos alternando barra/espacio (empieza y
# termina en barra): 5 barras + 4 espacios. '0' = módulo angosto (1
# unidad), '1' = módulo ancho (3 unidades) — de ahí "3 de 9": exactamente
# 3 de los 9 elementos son anchos en cada carácter válido (invariante
# verificado en autotest()). Tabla pública estándar Code 39.
_CODE39 = {
    "0": "000110100", "1": "100100001", "2": "001100001", "3": "101100000",
    "4": "000110001", "5": "100110000", "6": "001110000", "7": "000100101",
    "8": "100100100", "9": "001100100",
    "A": "100001001", "B": "001001001", "C": "101001000", "D": "000011001",
    "E": "100011000", "F": "001011000", "G": "000001101", "H": "100001100",
    "I": "001001100", "J": "000011100", "K": "100000011", "L": "001000011",
    "M": "101000010", "N": "000010011", "O": "100010010", "P": "001010010",
    "Q": "000000111", "R": "100000110", "S": "001000110", "T": "000010110",
    "U": "110000001", "V": "011000001", "W": "111000000", "X": "010010001",
    "Y": "110010000", "Z": "011010000",
    "-": "010000101", ".": "110000100", " ": "011000100", "$": "010101000",
    "/": "010100010", "+": "010001010", "%": "000101010", "*": "010010100",
}
_CODE39_NARROW, _CODE39_WIDE, _CODE39_GAP = 1, 3, 1  # unidades de módulo


def _barras_code39(texto: str):
    """Devuelve (lista de Barra sin marcar como altas, ancho total en
    módulos). Antepone/agrega los '*' de inicio y fin obligatorios."""
    texto = texto.upper()
    invalidos = sorted(set(texto) - set(_CODE39) - {"*"})
    if invalidos:
        raise ValueError(
            f"El código «{texto}» tiene caracteres que Code 39 no admite: "
            f"{', '.join(invalidos)}. Solo letras, números y - . $ / + %.")
    barras_out = []
    cursor = 0.0
    for caracter in f"*{texto}*":
        patron = _CODE39[caracter]
        for indice, elemento in enumerate(patron):
            ancho = _CODE39_WIDE if elemento == "1" else _CODE39_NARROW
            if indice % 2 == 0:  # posiciones pares = barra; impares = espacio
                barras_out.append(Barra(cursor, ancho, False))
            cursor += ancho
        cursor += _CODE39_GAP  # separación angosta entre caracteres
    return barras_out, cursor - _CODE39_GAP


# ---------------------------------------------------------------- estructura

@dataclass
class Barra:
    inicio: float   # posición en módulos desde el borde izquierdo
    ancho: float
    alta: bool = False  # True = tramo de guarda EAN-13 (se dibuja más alto)


@dataclass
class CodigoBarras:
    simbologia: str        # "EAN13" | "CODE39"
    codigo: str             # valor codificado (13 dígitos, o texto Code39)
    texto: str               # texto legible para mostrar bajo las barras
    ancho_modulos: float
    barras: list = field(default_factory=list)


def generar_codigo_barras(codigo_barras: str) -> CodigoBarras:
    """Punto de entrada único: EAN-13 si el código son 12-13 dígitos
    completables/válidos; si no, Code 39. Lanza ValueError (en español)
    si Code 39 tampoco puede representarlo."""
    codigo_barras = (codigo_barras or "").strip()
    if not codigo_barras:
        raise ValueError("El producto no tiene código de barras.")

    ean13 = completar_ean13(codigo_barras)
    if ean13:
        modulos = _modulos_ean13(ean13)
        barras_out = []
        cursor = 0
        for indice, modulo in enumerate(modulos):
            if modulo == "1":
                alta = any(desde <= indice <= hasta
                          for desde, hasta in _GUARDAS_EAN13)
                barras_out.append(Barra(cursor, 1, alta))
            cursor += 1
        texto = f"{ean13[0]} {ean13[1:7]} {ean13[7:13]}"
        return CodigoBarras("EAN13", ean13, texto, 95, barras_out)

    barras_out, ancho = _barras_code39(codigo_barras)
    return CodigoBarras("CODE39", codigo_barras.upper(), codigo_barras.upper(),
                        ancho, barras_out)


def sugerir_codigo_ean13() -> str:
    """EAN-13 nuevo, único frente a TODOS los codigo_barras ya usados
    (activos e inactivos: la columna es UNIQUE en toda la tabla), con
    prefijo 20-29 (uso interno de tienda) y verificador válido."""
    existentes = db.obtener_codigos_barras()
    for _ in range(1000):
        prefijo = secrets.choice(PREFIJO_USO_INTERNO)
        cuerpo = f"{prefijo}{secrets.randbelow(10 ** 10):010d}"
        candidato = cuerpo + str(digito_verificador_ean13(cuerpo))
        if candidato not in existentes:
            return candidato
    raise RuntimeError("No se pudo generar un código EAN-13 único.")


# ---------------------------------------------------------------- PDF

ETIQUETA_ANCHO = round(50 * MM)   # 142 pt (50 mm)
ETIQUETA_ALTO = round(30 * MM)    # 85 pt  (30 mm)

_ALTO_BARRA = 26
_ALTO_BARRA_GUARDA = 30
_BASE_BARRAS = 32
_MARGEN = 6


def _escapar_pdf(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _texto_centrado_pdf(texto: str, ancho_caracter: float, ancho_area: float):
    """Aproxima el ancho de un texto para centrarlo (fuentes estándar sin
    métricas exactas embebidas; suficiente para una etiqueta pequeña)."""
    ancho_texto = len(texto) * ancho_caracter
    return max(0, (ancho_area - ancho_texto) / 2)


def _dibujar_etiqueta(operadores: list, x0: float, y0: float,
                      producto: dict, codigo: CodigoBarras):
    """Agrega a `operadores` el texto y los rectángulos 'x y w h re f' de
    una etiqueta completa, desplazados a partir de (x0, y0)."""
    ancho_disponible = ETIQUETA_ANCHO - 2 * _MARGEN
    nombre = producto["nombre"][:26]

    operadores.append("BT")
    operadores.append("/F1 8 Tf")
    dx = _texto_centrado_pdf(nombre, 4.4, ancho_disponible)
    operadores.append(f"1 0 0 1 {x0 + _MARGEN + dx:.1f} {y0 + 71} Tm")
    operadores.append(f"({_escapar_pdf(nombre)}) Tj")
    operadores.append("ET")

    escala = ancho_disponible / codigo.ancho_modulos
    for barra in codigo.barras:
        alto = _ALTO_BARRA_GUARDA if barra.alta else _ALTO_BARRA
        x = x0 + _MARGEN + barra.inicio * escala
        w = max(0.5, barra.ancho * escala)
        y = y0 + _BASE_BARRAS
        operadores.append(f"{x:.2f} {y} {w:.2f} {alto} re f")

    operadores.append("BT")
    operadores.append("/F2 7 Tf")
    dx = _texto_centrado_pdf(codigo.texto, 4.2, ancho_disponible)
    operadores.append(f"1 0 0 1 {x0 + _MARGEN + dx:.1f} {y0 + 22} Tm")
    operadores.append(f"({_escapar_pdf(codigo.texto)}) Tj")
    operadores.append("ET")

    precio = fmt_dinero(producto["precio"])
    operadores.append("BT")
    operadores.append("/F1 9 Tf")
    dx = _texto_centrado_pdf(precio, 5.2, ancho_disponible)
    operadores.append(f"1 0 0 1 {x0 + _MARGEN + dx:.1f} {y0 + 8} Tm")
    operadores.append(f"({_escapar_pdf(precio)}) Tj")
    operadores.append("ET")


_FUENTES = (
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
    b"/Encoding /WinAnsiEncoding >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
    b"/Encoding /WinAnsiEncoding >>",
)


def generar_pdf_etiqueta(producto: dict, ruta) -> str:
    """Etiqueta individual: página del tamaño exacto de la etiqueta."""
    codigo = generar_codigo_barras(producto["codigo_barras"])
    operadores = []
    _dibujar_etiqueta(operadores, 0, 0, producto, codigo)
    flujo = "\n".join(operadores).encode("cp1252", "replace")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R "
         f"/MediaBox [0 0 {ETIQUETA_ANCHO} {ETIQUETA_ALTO}] "
         f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> "
         f"/Contents 6 0 R >>").encode(),
        _FUENTES[0],
        _FUENTES[1],
        b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo
        + b"\nendstream",
    ]
    return recibos.ensamblar_pdf(objetos, ruta)


def ruta_etiqueta_sugerida(producto: dict):
    return db.CARPETA_ETIQUETAS / f"{producto['codigo_barras']}.pdf"


# --- hoja de varias etiquetas (página carta) ---

PAGINA_ANCHO, PAGINA_ALTO = 612, 792  # carta/letter, en puntos
_MARGEN_HOJA = 36
COLUMNAS, FILAS = 3, 7  # 21 etiquetas por hoja
_GUTTER = 9

_BLOQUE_ANCHO = COLUMNAS * ETIQUETA_ANCHO + (COLUMNAS - 1) * _GUTTER
_BLOQUE_ALTO = FILAS * ETIQUETA_ALTO + (FILAS - 1) * _GUTTER
_OFFSET_X = _MARGEN_HOJA + (PAGINA_ANCHO - 2 * _MARGEN_HOJA - _BLOQUE_ANCHO) / 2
_OFFSET_Y = _MARGEN_HOJA + (PAGINA_ALTO - 2 * _MARGEN_HOJA - _BLOQUE_ALTO) / 2

POR_HOJA = COLUMNAS * FILAS


def _pagina_de_etiquetas(productos_pagina: list) -> str:
    operadores = []
    if not productos_pagina:
        operadores += ["BT", "/F1 14 Tf", "1 0 0 1 200 400 Tm",
                       "(No hay productos para imprimir) Tj", "ET"]
    for indice, producto in enumerate(productos_pagina):
        fila, columna = divmod(indice, COLUMNAS)
        x0 = _OFFSET_X + columna * (ETIQUETA_ANCHO + _GUTTER)
        y0 = (PAGINA_ALTO - _OFFSET_Y - ETIQUETA_ALTO
              - fila * (ETIQUETA_ALTO + _GUTTER))
        try:
            codigo = generar_codigo_barras(producto["codigo_barras"])
            _dibujar_etiqueta(operadores, x0, y0, producto, codigo)
        except ValueError:
            continue  # producto con código no representable: se omite su celda
    return "\n".join(operadores)


def generar_pdf_hoja_etiquetas(productos: list, ruta) -> str:
    """Hoja(s) tamaño carta con hasta 21 etiquetas cada una. Nunca falla
    en silencio: si `productos` está vacía, igual genera una página con
    el aviso correspondiente."""
    paginas = [productos[i:i + POR_HOJA]
              for i in range(0, len(productos), POR_HOJA)] or [[]]

    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
              _FUENTES[0], _FUENTES[1]]
    hijos = []
    for pagina in paginas:
        flujo = _pagina_de_etiquetas(pagina).encode("cp1252", "replace")
        num_pagina = len(objetos) + 1
        objetos.append(
            (f"<< /Type /Page /Parent 2 0 R "
             f"/MediaBox [0 0 {PAGINA_ANCHO} {PAGINA_ALTO}] "
             f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
             f"/Contents {num_pagina + 1} 0 R >>").encode())
        objetos.append(
            b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n"
            + flujo + b"\nendstream")
        hijos.append(f"{num_pagina} 0 R")

    objetos[1] = (f"<< /Type /Pages /Kids [{' '.join(hijos)}] "
                 f"/Count {len(hijos)} >>").encode()
    return recibos.ensamblar_pdf(objetos, ruta)


def ruta_hoja_sugerida():
    from datetime import date
    return db.CARPETA_ETIQUETAS / f"hoja-etiquetas-{date.today():%Y%m%d}.pdf"


# ---------------------------------------------------------------- impresión

def imprimir_etiqueta(producto: dict) -> str:
    """Mismo patrón que recibos.imprimir: genera el archivo y lo manda
    con el verbo 'print' del shell. El archivo queda guardado aunque no
    haya impresora; OSError se propaga para que la pantalla lo capture."""
    import os
    ruta = ruta_etiqueta_sugerida(producto)
    generar_pdf_etiqueta(producto, ruta)
    os.startfile(str(ruta), "print")
    return str(ruta)


# ---------------------------------------------------------------- autoprueba

def autotest() -> list:
    """Verificaciones matemáticas internas. No sustituye una prueba real
    con un lector de código de barras — ver plan.md."""
    fallos = []

    for cuerpo, esperado in (("590123412345", 7), ("400638133393", 1)):
        if digito_verificador_ean13(cuerpo) != esperado:
            fallos.append(f"verificador EAN-13 incorrecto para {cuerpo}")

    for caracter, patron in _CODE39.items():
        if len(patron) != 9 or patron.count("1") != 3:
            fallos.append(f"Code 39 «{caracter}»: patrón inválido "
                          f"(no es 3-de-9): {patron}")

    codigo = generar_codigo_barras("7701001")
    if codigo.simbologia != "CODE39":
        fallos.append("7701001 debería codificarse en Code 39")

    codigo = generar_codigo_barras("590123412345")
    if codigo.simbologia != "EAN13" or codigo.codigo != "5901234123457":
        fallos.append("código de 12 dígitos no se completó a EAN-13 "
                      "correctamente")

    codigo_malo = "5901234123450"  # verificador incorrecto a propósito
    if generar_codigo_barras(codigo_malo).simbologia != "CODE39":
        fallos.append("un EAN-13 con verificador incorrecto no debería "
                      "'corregirse' solo: debe caer a Code 39")

    try:
        generar_codigo_barras("PRODUCTO#1")
        fallos.append("un carácter no soportado por Code 39 debería "
                      "lanzar ValueError")
    except ValueError:
        pass

    return fallos
