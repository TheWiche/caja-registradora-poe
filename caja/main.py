"""Punto de entrada del Sistema de Caja Registradora Didáctica.

Ejecución:  python -m caja.main   (o doble clic en iniciar.bat)

Garantías de este módulo (plan.md §4, §5):
- Un error inesperado NUNCA cierra la aplicación: se registra en
  datos/eventos.log y se muestra un mensaje claro al usuario.
- Al iniciar se crea un respaldo automático de la base de datos.
- Si quedó una venta en curso (apagón, cierre forzado), al entrar se
  abre directamente la pantalla de venta con el carrito recuperado.
"""

import logging
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from . import db
from .rutas import RUTA_ICONO
from .ui import estilos
from .ui.login import PantallaLogin
from .ui.menu import PantallaMenu
from .ui.venta import PantallaVenta
from .ui.productos import PantallaProductos
from .ui.historial import PantallaHistorial
from .ui.reportes import PantallaReportes
from .ui.config import PantallaConfig
from .ui.usuarios import PantallaUsuarios

log = logging.getLogger("caja")


def configurar_registro():
    db.DATOS.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=db.RUTA_LOG, level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Caja Registradora Didáctica")
        self.minsize(1024, 640)
        try:
            self.iconbitmap(default=str(RUTA_ICONO))
        except tk.TclError:
            log.warning("No se pudo cargar el ícono de la aplicación")
        try:
            self.state("zoomed")  # pantalla completa en Windows
        except tk.TclError:
            pass
        estilos.aplicar_estilos(self)

        self.usuario = None
        self.id_sesion = None
        self._atajos_activos = []

        self.contenedor = ttk.Frame(self, style="Fondo.TFrame")
        self.contenedor.pack(fill="both", expand=True)

        # Un error en un callback no debe tumbar la aplicación (plan.md §4).
        self.report_callback_exception = self._error_global
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self.mostrar_login()

    # ------------------------------------------------------------ navegación

    def _cambiar_pantalla(self, constructor):
        self.limpiar_atajos()
        for widget in self.contenedor.winfo_children():
            widget.destroy()
        pantalla = constructor(self.contenedor, self)
        pantalla.pack(fill="both", expand=True)

    def mostrar_login(self):
        self._cambiar_pantalla(PantallaLogin)

    def mostrar_menu(self):
        self._cambiar_pantalla(PantallaMenu)

    def mostrar_venta(self):
        self._cambiar_pantalla(PantallaVenta)

    def mostrar_productos(self):
        self._cambiar_pantalla(PantallaProductos)

    def mostrar_historial(self):
        self._cambiar_pantalla(PantallaHistorial)

    def mostrar_reportes(self):
        if self._solo_admin():
            self._cambiar_pantalla(PantallaReportes)

    def mostrar_config(self):
        if self._solo_admin():
            self._cambiar_pantalla(PantallaConfig)

    def mostrar_usuarios(self):
        if self._solo_admin():
            self._cambiar_pantalla(PantallaUsuarios)

    def _solo_admin(self):
        if self.usuario and self.usuario["rol"] == "administrador":
            return True
        messagebox.showwarning(
            "Acceso restringido",
            "Esta sección está reservada al administrador.", parent=self)
        return False

    # ------------------------------------------------------------ sesión

    def iniciar_sesion(self, usuario: dict):
        self.usuario = usuario
        self.id_sesion = db.abrir_sesion(usuario["id"])
        log.info("Ingreso de %s (%s)", usuario["usuario"], usuario["rol"])
        # Recuperar venta interrumpida (plan.md §4 tolerancia a fallos).
        if db.leer_diario():
            self.mostrar_venta()
        else:
            self.mostrar_menu()

    def cerrar_sesion_usuario(self):
        if self.id_sesion:
            db.cerrar_sesion(self.id_sesion)
        self.usuario = None
        self.id_sesion = None
        self.mostrar_login()

    # ------------------------------------------------------------ atajos

    def atajo(self, secuencia: str, funcion):
        """Registra un atajo de teclado de la pantalla actual."""
        self.bind(secuencia, funcion)
        self._atajos_activos.append(secuencia)

    def limpiar_atajos(self):
        for secuencia in self._atajos_activos:
            self.unbind(secuencia)
        self._atajos_activos = []

    # ------------------------------------------------------------ errores

    def _error_global(self, tipo, valor, rastro):
        log.error("Error no controlado", exc_info=(tipo, valor, rastro))
        messagebox.showerror(
            "Error inesperado",
            "Ocurrió un error inesperado, pero puede seguir trabajando.\n"
            "Si hay una venta en curso, no se ha perdido.\n\n"
            "El detalle técnico quedó registrado en datos/eventos.log.",
            parent=self)

    def _al_cerrar(self):
        if db.leer_diario():
            if not messagebox.askyesno(
                    "Salir",
                    "Hay una venta en curso. Si sale ahora, la venta quedará "
                    "guardada y se recuperará al volver a entrar.\n\n"
                    "¿Desea salir?", parent=self):
                return
        if self.id_sesion:
            db.cerrar_sesion(self.id_sesion)
        db.cerrar()
        self.destroy()


def principal():
    configurar_registro()
    try:
        db.iniciar()
        db.respaldar()  # respaldo automático en cada arranque (plan.md §4)
    except Exception:
        log.exception("Fallo al iniciar la base de datos")
        raise
    log.info("Aplicación iniciada")
    app = App()
    app.mainloop()
    log.info("Aplicación cerrada")


if __name__ == "__main__":
    sys.exit(principal())
