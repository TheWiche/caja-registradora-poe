"""Punto de entrada para el ejecutable empaquetado (PyInstaller).

Usar `python -m caja.main` para desarrollo; este archivo solo existe
para que PyInstaller tenga un script de nivel superior que importe el
paquete `caja` correctamente (evita problemas con imports relativos
cuando el módulo se ejecuta como __main__ dentro del paquete).
"""

from caja.main import principal

if __name__ == "__main__":
    principal()
