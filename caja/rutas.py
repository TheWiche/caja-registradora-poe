"""Resolución de rutas base: código fuente vs. ejecutable empaquetado.

Los datos del usuario (base de datos, tickets, respaldos, registro de
eventos) siempre se guardan junto al .exe — o junto al proyecto, en
desarrollo — para que sobrevivan a actualizaciones del programa
(plan.md §4 confiabilidad). Los recursos empaquetados (el ícono) se
leen desde la carpeta temporal de extracción de PyInstaller cuando la
app corre como ejecutable.
"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    RAIZ = Path(sys.executable).resolve().parent
    RECURSOS = Path(getattr(sys, "_MEIPASS", RAIZ))
else:
    RAIZ = Path(__file__).resolve().parent.parent
    RECURSOS = RAIZ

RUTA_ICONO = RECURSOS / "assets" / "icono.ico"
