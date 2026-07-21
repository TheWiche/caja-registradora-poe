"""Impresión térmica directa (ESC/POS) por el spooler de Windows.

Envía bytes RAW a la cola de impresión con la API winspool (ctypes,
librería estándar): sin driver especial, sin márgenes de página y sin
que Notepad parta las líneas — el problema clásico de imprimir tickets
de 40 columnas con el driver "Generic / Text Only" en papel de rollo.
Al hablar ESC/POS nativo, la térmica además imprime códigos de barras
escaneables y corta el papel sola.

Los comandos son el estándar ESC/POS (Epson y compatibles, incluida la
Xprinter del curso). La fuente B (ESC ! 1) da ~42 columnas en rollo de
58 mm, suficiente para los tickets de 40 columnas de recibos.py sin
reformatear nada.
"""

import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger("caja")

ESC = b"\x1b"
GS = b"\x1d"

# Página de códigos WPC1252 en la tabla ESC t de Epson/Xprinter: permite
# imprimir tildes y ñ codificando el texto en cp1252.
_PAGINA_CODIGOS = 16

_winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)


class _DOC_INFO_1W(ctypes.Structure):
    _fields_ = [("pDocName", wintypes.LPWSTR),
                ("pOutputFile", wintypes.LPWSTR),
                ("pDatatype", wintypes.LPWSTR)]


_winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR,
                                   ctypes.POINTER(wintypes.HANDLE),
                                   ctypes.c_void_p]
_winspool.OpenPrinterW.restype = wintypes.BOOL
_winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
_winspool.ClosePrinter.restype = wintypes.BOOL
_winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                       ctypes.POINTER(_DOC_INFO_1W)]
_winspool.StartDocPrinterW.restype = wintypes.DWORD
_winspool.EndDocPrinter.argtypes = [wintypes.HANDLE]
_winspool.EndDocPrinter.restype = wintypes.BOOL
_winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
_winspool.StartPagePrinter.restype = wintypes.BOOL
_winspool.EndPagePrinter.argtypes = [wintypes.HANDLE]
_winspool.EndPagePrinter.restype = wintypes.BOOL
_winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_char_p,
                                   wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD)]
_winspool.WritePrinter.restype = wintypes.BOOL
_winspool.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR,
                                         ctypes.POINTER(wintypes.DWORD)]
_winspool.GetDefaultPrinterW.restype = wintypes.BOOL


def impresora_predeterminada() -> str:
    tamano = wintypes.DWORD(0)
    _winspool.GetDefaultPrinterW(None, ctypes.byref(tamano))
    if tamano.value == 0:
        raise OSError("No hay impresora predeterminada configurada.")
    nombre = ctypes.create_unicode_buffer(tamano.value)
    if not _winspool.GetDefaultPrinterW(nombre, ctypes.byref(tamano)):
        raise OSError("No se pudo leer la impresora predeterminada.")
    return nombre.value


def imprimir_raw(datos: bytes, impresora: str = None, documento="Ticket"):
    """Manda los bytes tal cual (datatype RAW) a la cola indicada o a la
    predeterminada. Lanza OSError con mensaje claro si algo falla, para
    que las pantallas lo capturen igual que hoy capturan la impresión
    por Windows (plan.md §4 tolerancia a fallos)."""
    impresora = impresora or impresora_predeterminada()
    manejador = wintypes.HANDLE()
    if not _winspool.OpenPrinterW(impresora, ctypes.byref(manejador), None):
        raise OSError(f"No se pudo abrir la impresora «{impresora}» "
                      f"(error {ctypes.get_last_error()}).")
    try:
        info = _DOC_INFO_1W(documento, None, "RAW")
        if _winspool.StartDocPrinterW(manejador, 1, ctypes.byref(info)) == 0:
            raise OSError(f"No se pudo iniciar el documento en «{impresora}» "
                          f"(error {ctypes.get_last_error()}).")
        try:
            _winspool.StartPagePrinter(manejador)
            escritos = wintypes.DWORD(0)
            ok = _winspool.WritePrinter(manejador, datos, len(datos),
                                        ctypes.byref(escritos))
            _winspool.EndPagePrinter(manejador)
            if not ok or escritos.value != len(datos):
                raise OSError(f"Escritura incompleta en «{impresora}»: "
                              f"{escritos.value} de {len(datos)} bytes.")
        finally:
            _winspool.EndDocPrinter(manejador)
    finally:
        _winspool.ClosePrinter(manejador)
    log.info("Impresión RAW enviada a «%s» (%d bytes)", impresora, len(datos))


# ------------------------------------------------------------- ESC/POS

def _texto(cadena: str) -> bytes:
    return cadena.encode("cp1252", "replace")


def _cabecera() -> bytes:
    return (ESC + b"@"                                # reiniciar
            + ESC + b"t" + bytes([_PAGINA_CODIGOS]))  # tildes y ñ


def _pie_con_corte() -> bytes:
    return b"\n\n\n\n" + GS + b"V\x42\x03"  # avanzar y corte parcial


def ticket_texto(lineas: list) -> bytes:
    """Ticket de solo texto (recibos): fuente B para que las 40 columnas
    de recibos.py quepan en un rollo de 58 mm."""
    datos = bytearray(_cabecera())
    datos += ESC + b"!" + bytes([1])  # fuente B (comprimida)
    for linea in lineas:
        datos += _texto(linea) + b"\n"
    datos += _pie_con_corte()
    return bytes(datos)


def ticket_etiqueta(nombre: str, precio_texto: str, codigo: str,
                    simbologia: str) -> bytes:
    """Etiqueta individual con el código de barras impreso por la propia
    térmica (comandos GS k): queda escaneable con el lector, igual que
    la etiqueta de góndola de un supermercado real."""
    datos = bytearray(_cabecera())
    datos += ESC + b"a" + bytes([1])           # centrar
    datos += ESC + b"!" + bytes([8])            # fuente A en negrilla
    datos += _texto(nombre[:32]) + b"\n"
    datos += ESC + b"!" + bytes([0])
    datos += _texto(precio_texto) + b"\n\n"
    datos += GS + b"h" + bytes([80])            # altura de barras
    datos += GS + b"w" + bytes([2])             # ancho de módulo
    datos += GS + b"H" + bytes([2])             # número legible debajo
    if simbologia == "EAN13":
        datos += GS + b"k" + bytes([2]) + codigo.encode("ascii") + b"\x00"
    else:
        datos += GS + b"k" + bytes([4]) + codigo.encode("ascii") + b"\x00"
    datos += _pie_con_corte()
    return bytes(datos)


def pagina_prueba(nombre_negocio: str) -> bytes:
    """Página de prueba de Configuración: texto, acentos, ancho y un
    código de barras — todo lo que la caja necesita de la impresora."""
    datos = bytearray(_cabecera())
    datos += ESC + b"a" + bytes([1])
    datos += ESC + b"!" + bytes([8])
    datos += _texto("PRUEBA DE IMPRESORA") + b"\n"
    datos += ESC + b"!" + bytes([0])
    datos += _texto(nombre_negocio[:32]) + b"\n\n"
    datos += _texto("Acentos: áéíóú ñÑ ¡! $") + b"\n"
    datos += ESC + b"!" + bytes([1])
    datos += _texto("1234567890" * 4) + b"\n"   # regla de 40 columnas
    datos += ESC + b"!" + bytes([0]) + b"\n"
    datos += GS + b"h" + bytes([70]) + GS + b"w" + bytes([2])
    datos += GS + b"H" + bytes([2])
    datos += GS + b"k" + bytes([4]) + b"7701001" + b"\x00"
    datos += b"\n" + _texto("Si el código se lee con la pistola,") + b"\n"
    datos += _texto("todo quedó bien configurado.") + b"\n"
    datos += _pie_con_corte()
    return bytes(datos)
