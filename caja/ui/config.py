"""Configuración: IVA, modo entrenamiento, respaldos y reinicio de datos
entre clases (plan.md §1.8, §3). Solo accesible al administrador.

Teclas:  F6 Guardar · Esc Menú
"""

import tkinter as tk
from tkinter import ttk, messagebox

from .. import db
from . import estilos
from .estilos import BarraSuperior


class PantallaConfig(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app

        BarraSuperior(self, app, "Configuración", volver=True)
        app.atajo("<Escape>", lambda e: app.mostrar_menu())
        app.atajo("<F6>", lambda e: self._guardar())

        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 14, 24, 20))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.columnconfigure(1, weight=1)

        # ---- opciones de operación
        opciones = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=20)
        opciones.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(opciones, text="Operación", style="TituloTarjeta.TLabel").pack(
            anchor="w", pady=(0, 12))

        fila_negocio = ttk.Frame(opciones, style="Tarjeta.TFrame")
        fila_negocio.pack(fill="x", pady=(0, 10))
        ttk.Label(fila_negocio, text="Nombre en el recibo:",
                  style="Campo.TLabel").pack(anchor="w")
        self.nombre_negocio = tk.Entry(fila_negocio, font=(estilos.FUENTE, 13),
                                       relief="solid", bd=1)
        self.nombre_negocio.insert(0, db.obtener_config("nombre_negocio"))
        self.nombre_negocio.pack(fill="x", pady=(2, 0))

        fila_iva = ttk.Frame(opciones, style="Tarjeta.TFrame")
        fila_iva.pack(fill="x", pady=(0, 10))
        ttk.Label(fila_iva, text="IVA (%):  0 = sin IVA",
                  style="Campo.TLabel").pack(side="left")
        self.iva = tk.Entry(fila_iva, font=(estilos.FUENTE, 13), width=6,
                            relief="solid", bd=1, justify="center")
        self.iva.insert(0, db.obtener_config("iva_porcentaje", "0"))
        self.iva.pack(side="left", padx=10)

        self.variables = {}
        casillas = (
            ("modo_entrenamiento",
             "Modo entrenamiento: las ventas se marcan como práctica,\n"
             "no afectan el inventario ni los reportes"),
            ("imprimir_auto",
             "Imprimir el recibo automáticamente al finalizar cada venta\n"
             "(como en una caja real con impresora de tickets)"),
            ("controlar_stock",
             "Controlar stock: descontar inventario en cada venta real"),
        )
        for clave, texto in casillas:
            variable = tk.BooleanVar(value=db.config_activa(clave))
            ttk.Checkbutton(opciones, text=texto, variable=variable).pack(
                anchor="w", pady=6)
            self.variables[clave] = variable

        ttk.Button(opciones, text="Guardar configuración  (F6)",
                   style="Exito.TButton",
                   command=self._guardar).pack(fill="x", pady=(16, 0))

        # ---- mantenimiento
        mantenimiento = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=20)
        mantenimiento.grid(row=0, column=1, sticky="nsew")
        ttk.Label(mantenimiento, text="Mantenimiento",
                  style="TituloTarjeta.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(
            mantenimiento,
            text=f"Base de datos local:\n{db.RUTA_BD}\n\n"
                 f"Respaldos automáticos al iniciar la aplicación en:\n"
                 f"{db.CARPETA_RESPALDOS}\n\n"
                 f"Registro de eventos y errores:\n{db.RUTA_LOG}",
            style="SubTarjeta.TLabel", justify="left").pack(anchor="w",
                                                            pady=(0, 14))

        ttk.Button(mantenimiento, text="Crear respaldo ahora",
                   style="Primario.TButton",
                   command=self._respaldar).pack(fill="x", pady=(0, 8))
        ttk.Button(mantenimiento, text="Cambiar mi contraseña",
                   style="Plano.TButton",
                   command=self._cambiar_clave).pack(fill="x", pady=(0, 8))
        ttk.Button(mantenimiento,
                   text="Reiniciar datos para una nueva clase",
                   style="Peligro.TButton",
                   command=self._reiniciar).pack(fill="x")
        ttk.Label(mantenimiento,
                  text="El reinicio borra ventas y sesiones, restaura los\n"
                       "productos de ejemplo y hace un respaldo previo.\n"
                       "Los usuarios y esta configuración se conservan.",
                  style="SubTarjeta.TLabel", justify="left").pack(anchor="w",
                                                                  pady=(8, 0))

    def _guardar(self):
        iva_texto = self.iva.get().strip()
        if not iva_texto.isdigit() or not 0 <= int(iva_texto) <= 50:
            messagebox.showwarning("Configuración",
                                   "El IVA debe ser un número entre 0 y 50.",
                                   parent=self.app)
            return
        db.guardar_config("iva_porcentaje", iva_texto)
        db.guardar_config("nombre_negocio",
                          self.nombre_negocio.get().strip() or
                          "SISTEMA DE CAJA DIDÁCTICO")
        for clave, variable in self.variables.items():
            db.guardar_config(clave, "1" if variable.get() else "0")
        messagebox.showinfo("Configuración", "Configuración guardada.",
                            parent=self.app)

    def _respaldar(self):
        destino = db.respaldar()
        messagebox.showinfo("Respaldo", f"Respaldo creado:\n{destino}",
                            parent=self.app)

    def _cambiar_clave(self):
        dialogo = DialogoClave(self.app)
        if dialogo.resultado:
            db.cambiar_clave(self.app.usuario["id"], dialogo.resultado)
            messagebox.showinfo("Contraseña", "Contraseña actualizada.",
                                parent=self.app)

    def _reiniciar(self):
        dialogo = DialogoConfirmarReinicio(self.app)
        if dialogo.confirmado:
            db.reiniciar_datos()
            messagebox.showinfo(
                "Reinicio", "Datos reiniciados para una nueva clase.\n"
                "Se creó un respaldo previo en la carpeta de respaldos.",
                parent=self.app)


class DialogoClave(tk.Toplevel):
    def __init__(self, padre):
        super().__init__(padre)
        self.title("Cambiar contraseña")
        self.resultado = None
        self.configure(bg=estilos.TARJETA, padx=24, pady=18)
        self.transient(padre)
        self.resizable(False, False)

        tk.Label(self, text="Nueva contraseña (mínimo 6 caracteres):",
                 font=(estilos.FUENTE, 12), bg=estilos.TARJETA).pack(anchor="w")
        self.clave1 = estilos.entrada_grande(self, width=18, show="●")
        self.clave1.pack(pady=(4, 10))
        tk.Label(self, text="Repita la contraseña:",
                 font=(estilos.FUENTE, 12), bg=estilos.TARJETA).pack(anchor="w")
        self.clave2 = estilos.entrada_grande(self, width=18, show="●")
        self.clave2.pack(pady=(4, 12))

        ttk.Button(self, text="Guardar", style="Exito.TButton",
                   command=self._aceptar).pack(fill="x")
        self.bind("<Return>", lambda e: self._aceptar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.clave1.focus_set()
        self.grab_set()
        self.wait_window()

    def _aceptar(self):
        clave = self.clave1.get()
        if len(clave) < 6:
            messagebox.showwarning("Contraseña", "Debe tener al menos 6 "
                                   "caracteres.", parent=self)
            return
        if clave != self.clave2.get():
            messagebox.showwarning("Contraseña", "Las contraseñas no "
                                   "coinciden.", parent=self)
            return
        self.resultado = clave
        self.destroy()


class DialogoConfirmarReinicio(tk.Toplevel):
    """Para evitar borrados accidentales exige escribir REINICIAR (plan.md §6.5)."""

    def __init__(self, padre):
        super().__init__(padre)
        self.title("Confirmar reinicio")
        self.confirmado = False
        self.configure(bg=estilos.TARJETA, padx=24, pady=18)
        self.transient(padre)
        self.resizable(False, False)

        tk.Label(self,
                 text="Esta acción borra TODAS las ventas y sesiones\n"
                      "y restaura los productos de ejemplo.\n\n"
                      "Escriba REINICIAR para confirmar:",
                 font=(estilos.FUENTE, 12), bg=estilos.TARJETA,
                 justify="left").pack(anchor="w")
        self.entrada = estilos.entrada_grande(self, width=16, justify="center")
        self.entrada.pack(pady=12)

        ttk.Button(self, text="Reiniciar datos", style="Peligro.TButton",
                   command=self._aceptar).pack(fill="x")
        self.bind("<Return>", lambda e: self._aceptar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.entrada.focus_set()
        self.grab_set()
        self.wait_window()

    def _aceptar(self):
        if self.entrada.get().strip().upper() == "REINICIAR":
            self.confirmado = True
            self.destroy()
        else:
            self.bell()
            self.entrada.delete(0, "end")
