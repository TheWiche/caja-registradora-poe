"""Configuración: IVA, modo entrenamiento, respaldos y reinicio de datos
entre clases (plan.md §1.8, §3). Solo accesible al administrador.

Teclas:  F6 Guardar · Esc Menú
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

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
            ("impresion_termica",
             "Impresora térmica de tickets (ESC/POS): tickets y etiquetas\n"
             "salen directo, con código de barras y corte de papel"),
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

        ttk.Button(mantenimiento, text="Imprimir página de prueba",
                   style="Primario.TButton",
                   command=self._probar_impresora).pack(fill="x", pady=(0, 8))
        ttk.Button(mantenimiento, text="Crear respaldo ahora",
                   style="Primario.TButton",
                   command=self._respaldar).pack(fill="x", pady=(0, 8))
        ttk.Button(mantenimiento, text="Cambiar mi contraseña",
                   style="Plano.TButton",
                   command=self._cambiar_clave).pack(fill="x", pady=(0, 8))

        fila_transferencia = ttk.Frame(mantenimiento, style="Tarjeta.TFrame")
        fila_transferencia.pack(fill="x", pady=(0, 8))
        fila_transferencia.columnconfigure(0, weight=1)
        fila_transferencia.columnconfigure(1, weight=1)
        ttk.Button(fila_transferencia, text="Exportar datos…",
                   style="Primario.TButton",
                   command=self._exportar).grid(row=0, column=0, sticky="ew",
                                                padx=(0, 4))
        ttk.Button(fila_transferencia, text="Importar datos…",
                   style="Plano.TButton",
                   command=self._importar).grid(row=0, column=1, sticky="ew",
                                                padx=(4, 0))
        ttk.Label(mantenimiento,
                  text="Exportar guarda TODO (productos, usuarios, ventas y\n"
                       "configuración) en un solo archivo para llevarlo a\n"
                       "otro computador e importarlo allá.",
                  style="SubTarjeta.TLabel", justify="left").pack(anchor="w",
                                                                  pady=(0, 10))

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

    def _probar_impresora(self):
        from .. import impresion
        try:
            nombre = impresion.impresora_predeterminada()
            impresion.imprimir_raw(
                impresion.pagina_prueba(db.obtener_config("nombre_negocio")),
                documento="Página de prueba")
            messagebox.showinfo(
                "Impresora",
                f"Página de prueba enviada a:\n{nombre}\n\n"
                "Debe salir el texto con acentos, una regla de 40\n"
                "columnas y un código de barras escaneable.",
                parent=self.app)
        except OSError as error:
            messagebox.showwarning(
                "Impresora",
                f"No se pudo imprimir la página de prueba.\n\n{error}",
                parent=self.app)

    def _respaldar(self):
        destino = db.respaldar()
        messagebox.showinfo("Respaldo", f"Respaldo creado:\n{destino}",
                            parent=self.app)

    def _exportar(self):
        ruta = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".db",
            initialfile=f"caja-exportacion-{date.today():%Y%m%d}.db",
            filetypes=[("Datos de Caja Registradora", "*.db")])
        if not ruta:
            return
        db.exportar_datos(ruta)
        messagebox.showinfo(
            "Exportar datos",
            f"Datos exportados a:\n{ruta}\n\n"
            "Lleve este archivo al otro computador (memoria USB, por\n"
            "ejemplo) y úselo allá con «Importar datos».", parent=self.app)

    def _importar(self):
        ruta = filedialog.askopenfilename(
            parent=self.app,
            filetypes=[("Datos de Caja Registradora", "*.db"),
                       ("Todos los archivos", "*.*")])
        if not ruta:
            return
        dialogo = DialogoConfirmarPalabra(
            self.app, "IMPORTAR",
            "Importar reemplaza TODOS los datos de este computador\n"
            "(productos, usuarios, ventas y configuración) por los del\n"
            "archivo elegido. Se hará un respaldo automático de los\n"
            "datos actuales antes de continuar.\n\n"
            "Escriba IMPORTAR para confirmar:")
        if not dialogo.confirmado:
            return
        try:
            db.importar_datos(ruta)
        except ValueError as error:
            messagebox.showwarning("Importar datos", str(error),
                                   parent=self.app)
            return
        messagebox.showinfo(
            "Importar datos",
            "Datos importados correctamente.\n\n"
            "Los datos anteriores quedaron respaldados en la carpeta de\n"
            "respaldos. Inicie sesión de nuevo con un usuario del archivo\n"
            "importado.", parent=self.app)
        self.app.usuario = None
        self.app.id_sesion = None
        self.app.mostrar_login()

    def _cambiar_clave(self):
        dialogo = DialogoClave(self.app)
        if dialogo.resultado:
            db.cambiar_clave(self.app.usuario["id"], dialogo.resultado)
            messagebox.showinfo("Contraseña", "Contraseña actualizada.",
                                parent=self.app)

    def _reiniciar(self):
        dialogo = DialogoConfirmarPalabra(
            self.app, "REINICIAR",
            "Esta acción borra TODAS las ventas y sesiones\n"
            "y restaura los productos de ejemplo.\n\n"
            "Escriba REINICIAR para confirmar:")
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


class DialogoConfirmarPalabra(tk.Toplevel):
    """Confirmación de acciones destructivas escribiendo una palabra
    (REINICIAR, IMPORTAR...) para evitar clics accidentales (plan.md §6.5)."""

    def __init__(self, padre, palabra: str, mensaje: str):
        super().__init__(padre)
        self.title("Confirmación")
        self.confirmado = False
        self.palabra = palabra
        self.configure(bg=estilos.TARJETA, padx=24, pady=18)
        self.transient(padre)
        self.resizable(False, False)

        tk.Label(self, text=mensaje,
                 font=(estilos.FUENTE, 12), bg=estilos.TARJETA,
                 justify="left").pack(anchor="w")
        self.entrada = estilos.entrada_grande(self, width=16, justify="center")
        self.entrada.pack(pady=12)

        ttk.Button(self, text="Confirmar", style="Peligro.TButton",
                   command=self._aceptar).pack(fill="x")
        self.bind("<Return>", lambda e: self._aceptar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.entrada.focus_set()
        self.grab_set()
        self.wait_window()

    def _aceptar(self):
        if self.entrada.get().strip().upper() == self.palabra:
            self.confirmado = True
            self.destroy()
        else:
            self.bell()
            self.entrada.delete(0, "end")
