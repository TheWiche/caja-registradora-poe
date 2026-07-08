"""Utilidades compartidas: formato de dinero y fechas.

El dinero se maneja siempre como enteros (pesos), con punto como
separador de miles al estilo colombiano: 28200 -> "28.200".
"""

from datetime import datetime


def fmt_dinero(valor) -> str:
    """Formatea un entero como dinero: 28200 -> '28.200'."""
    return f"{int(round(valor)):,}".replace(",", ".")


def parse_dinero(texto: str):
    """Convierte texto a entero de pesos. Acepta '28.200', '$28200', '28 200'.

    Devuelve None si el texto no es un monto válido.
    """
    limpio = (
        texto.strip()
        .replace("$", "")
        .replace(".", "")
        .replace(",", "")
        .replace(" ", "")
    )
    if not limpio or not limpio.isdigit():
        return None
    return int(limpio)


def ahora_iso() -> str:
    """Fecha y hora actual en formato ISO para la base de datos."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hoy_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def fecha_legible(iso: str) -> str:
    """'2026-07-07 14:32:05' -> '07/07/2026 14:32'."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def parse_fecha_usuario(texto: str):
    """'07/07/2026' -> '2026-07-07'. Devuelve None si es inválida."""
    texto = texto.strip()
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
