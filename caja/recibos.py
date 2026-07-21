"""Generación de recibos: texto (impresora térmica de 40 columnas),
PDF (generador propio, sin dependencias externas) e impresión vía Windows.

El PDF se escribe a mano siguiendo la especificación mínima de PDF 1.4
con fuente Courier incorporada en todo visor: cero librerías, cero
Internet, cumple plan.md §6.1.
"""

import os
import logging

from . import db, impresion
from .util import fmt_dinero, fecha_legible

ANCHO = 40  # columnas del recibo (papel térmico de 80 mm)

log = logging.getLogger("caja")


# ---------------------------------------------------------------- texto

def _linea(car="-"):
    return car * ANCHO


def _fila(izquierda: str, derecha: str) -> str:
    espacio = ANCHO - len(izquierda) - len(derecha)
    return izquierda + " " * max(1, espacio) + derecha


def lineas_recibo(venta: dict) -> list:
    """Construye el recibo como lista de líneas de máximo 40 caracteres."""
    negocio = db.obtener_config("nombre_negocio", "SISTEMA DE CAJA")
    lineas = [
        _linea("="),
        negocio[:ANCHO].center(ANCHO),
        "RECIBO DE VENTA".center(ANCHO),
        _linea("="),
        f"Factura: {venta['numero_factura']}",
        f"Fecha:   {fecha_legible(venta['fecha'])}",
        f"Cajero:  {venta['nombre_cajero'][:31]}",
    ]
    if venta.get("cliente_nombre"):
        linea_cliente = f"Cliente: {venta['cliente_nombre'][:31]}"
        lineas.append(linea_cliente)
        if venta.get("cliente_nit"):
            lineas.append(f"NIT/CC:  {venta['cliente_nit'][:31]}")
    lineas += [
        _linea(),
        f"{'Producto':<18}{'Cant':>4}{'Precio':>8}{'Subtot':>10}",
        _linea(),
    ]
    for det in venta["detalles"]:
        lineas.append(
            f"{det['nombre'][:18]:<18}{det['cantidad']:>4}"
            f"{fmt_dinero(det['precio']):>8}{fmt_dinero(det['subtotal']):>10}"
        )
    lineas.append(_linea())
    lineas.append(_fila("SUBTOTAL:", fmt_dinero(venta["subtotal"])))
    if venta["iva_porcentaje"]:
        lineas.append(
            _fila(f"IVA ({venta['iva_porcentaje']}%):", fmt_dinero(venta["iva"]))
        )
    lineas.append(_fila("TOTAL:", fmt_dinero(venta["total"])))
    lineas.append("")
    lineas.append(_fila(f"Pago ({venta['metodo_pago']}):",
                        fmt_dinero(venta["recibido"])))
    lineas.append(_fila("CAMBIO:", fmt_dinero(venta["cambio"])))
    if venta.get("codigo_autorizacion"):
        lineas.append(_fila("Autorización:", venta["codigo_autorizacion"]))
    lineas.append(_linea("="))
    lineas.append("¡Gracias por su compra!".center(ANCHO))
    if venta.get("entrenamiento"):
        lineas.append("* VENTA DE ENTRENAMIENTO *".center(ANCHO))
        lineas.append("* SIN VALOR COMERCIAL *".center(ANCHO))
    lineas.append(_linea("="))
    return lineas


def texto_recibo(venta: dict) -> str:
    return "\n".join(lineas_recibo(venta))


# ---------------------------------------------------------------- PDF

def _escapar_pdf(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def ensamblar_pdf(objetos: list, ruta) -> str:
    """Ensambla objetos PDF ya serializados (bytes, uno por número de
    objeto empezando en 1) en un archivo PDF 1.4 válido: numera, arma la
    tabla xref y el trailer a mano. Compartido por generar_pdf y por
    caja.barras (etiquetas de productos), para no duplicar el formato de
    bajo nivel del PDF (plan.md §6.10)."""
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"

    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode()
    salida += b"0000000000 65535 f \n"
    for pos in posiciones:
        salida += f"{pos:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()

    ruta = str(ruta)
    with open(ruta, "wb") as archivo:
        archivo.write(salida)
    log.info("PDF generado: %s", ruta)
    return ruta


def generar_pdf(venta: dict, ruta) -> str:
    """Escribe el recibo como PDF mínimo válido (una página, Courier)."""
    lineas = lineas_recibo(venta)
    alto = max(220, 50 + 13 * len(lineas))
    ancho_pagina = 270  # ~ ancho de tirilla térmica en puntos

    contenido = ["BT", "/F1 9 Tf", "13 TL", f"1 0 0 1 20 {alto - 30} Tm"]
    for ln in lineas:
        contenido.append(f"({_escapar_pdf(ln)}) Tj T*")
    contenido.append("ET")
    flujo = "\n".join(contenido).encode("cp1252", "replace")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho_pagina} {alto}] "
         f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo
        + b"\nendstream",
    ]

    return ensamblar_pdf(objetos, ruta)


def ruta_pdf_sugerida(venta: dict):
    return db.CARPETA_TICKETS / f"{venta['numero_factura']}.pdf"


# ---------------------------------------------------------------- impresión

def imprimir(venta: dict) -> str:
    """Envía el recibo a la impresora predeterminada.

    Siempre guarda el ticket como .txt (constancia aunque no haya
    impresora). Con la opción de impresora térmica activa (el hardware
    del curso) manda ESC/POS directo por el spooler: sin márgenes de
    página ni líneas partidas, y con corte de papel. Si esa vía falla,
    cae a la impresión normal de Windows (verbo 'print' del shell).
    """
    ruta = db.CARPETA_TICKETS / f"{venta['numero_factura']}.txt"
    ruta.write_text(texto_recibo(venta) + "\n\n\n", encoding="cp1252",
                    errors="replace")
    if db.config_activa("impresion_termica"):
        try:
            impresion.imprimir_raw(
                impresion.ticket_texto(lineas_recibo(venta)),
                documento=f"Recibo {venta['numero_factura']}")
            log.info("Recibo %s impreso en térmica",
                     venta["numero_factura"])
            return str(ruta)
        except OSError:
            log.exception("Falló la impresión térmica; se intenta la "
                          "impresión normal de Windows")
    os.startfile(str(ruta), "print")
    log.info("Recibo %s enviado a impresión", venta["numero_factura"])
    return str(ruta)
