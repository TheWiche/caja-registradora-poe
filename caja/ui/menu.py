"""Menú principal: losetas grandes, todo accesible con teclas F
(plan.md §3, §4)."""

from tkinter import ttk

from .. import db
from .estilos import BarraSuperior


class PantallaMenu(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app
        es_admin = app.usuario["rol"] == "administrador"

        BarraSuperior(self, app,
                      db.obtener_config("nombre_negocio", "SISTEMA DE CAJA"),
                      entrenamiento=db.config_activa("modo_entrenamiento"))

        centro = ttk.Frame(self, style="Fondo.TFrame", padding=30)
        centro.pack(expand=True)

        opciones = (
            ("F1", "🛒", "Nueva venta", app.mostrar_venta, True),
            ("F2", "📦", "Productos", app.mostrar_productos, True),
            ("F3", "🧾", "Historial", app.mostrar_historial, True),
            ("F4", "📊", "Reportes", app.mostrar_reportes, es_admin),
            ("F5", "⚙", "Configuración", app.mostrar_config, es_admin),
            ("F6", "👤", "Usuarios", app.mostrar_usuarios, es_admin),
            ("F8", "🚪", "Cerrar sesión", app.cerrar_sesion_usuario, True),
        )

        fila = columna = 0
        for tecla, icono, texto, accion, permitido in opciones:
            boton = ttk.Button(centro, text=f"{icono}\n{texto}\n{tecla}",
                               style="Tile.TButton", command=accion, width=16)
            if not permitido:
                boton.state(["disabled"])
            boton.grid(row=fila, column=columna, padx=10, pady=10, sticky="nsew")
            if permitido:
                app.atajo(f"<{tecla}>", lambda e, a=accion: a())
            columna += 1
            if columna == 4:
                columna = 0
                fila += 1

        pie = ttk.Frame(self, style="Fondo.TFrame", padding=(30, 0, 30, 16))
        pie.pack(fill="x", side="bottom")
        nota = ("Reportes, Configuración y Usuarios están reservados al "
                "administrador." if not es_admin else
                "Todo el sistema se opera con el teclado: use las teclas F "
                "indicadas en cada botón.")
        ttk.Label(pie, text=nota, style="Sub.TLabel").pack(side="left")
