"""Gestión de perfiles de usuario (solo administrador).

El administrador crea cajeros y otros administradores, cambia roles,
restablece contraseñas y activa/desactiva perfiles. Los usuarios nunca
se borran físicamente: las ventas registradas conservan su trazabilidad
(plan.md §6.9).

Teclas:  F5 Nuevo · F6 Guardar · F8 Activar/Desactivar · Esc Menú
"""

import tkinter as tk
from tkinter import ttk, messagebox

from .. import db
from . import estilos
from .estilos import BarraSuperior


class PantallaUsuarios(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app
        self.id_editando = None

        BarraSuperior(self, app, "Perfiles de usuario", volver=True)
        app.atajo("<Escape>", lambda e: app.mostrar_menu())
        app.atajo("<F5>", lambda e: self._nuevo())
        app.atajo("<F6>", lambda e: self._guardar())
        app.atajo("<F8>", lambda e: self._alternar_activo())

        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 14, 24, 20))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=2)
        cuerpo.rowconfigure(0, weight=1)

        # ---- lista de usuarios
        panel_lista = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=16)
        panel_lista.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel_lista.rowconfigure(0, weight=1)
        panel_lista.columnconfigure(0, weight=1)

        columnas = ("nombre", "usuario", "rol", "estado")
        self.tabla = ttk.Treeview(panel_lista, columns=columnas, show="headings",
                                  selectmode="browse")
        for col, titulo, ancho, ancla in (
                ("nombre", "Nombre completo", 220, "w"),
                ("usuario", "Ingreso", 120, "w"),
                ("rol", "Rol", 130, "w"),
                ("estado", "Estado", 90, "center")):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor=ancla)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._cargar_seleccion())
        self.tabla.tag_configure("inactivo", foreground=estilos.GRIS)

        ttk.Label(panel_lista,
                  text="Los perfiles no se borran: se desactivan, para que "
                       "las ventas conserven su cajero.",
                  style="SubTarjeta.TLabel").grid(row=1, column=0, sticky="w",
                                                  pady=(8, 0))

        # ---- formulario
        formulario = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=18)
        formulario.grid(row=0, column=1, sticky="nsew")
        formulario.columnconfigure(0, weight=1)

        self.titulo_form = ttk.Label(formulario, text="Nuevo perfil",
                                     style="TituloTarjeta.TLabel")
        self.titulo_form.grid(row=0, column=0, sticky="w", pady=(0, 12))

        def campo(fila, texto, mostrar=None):
            ttk.Label(formulario, text=texto, style="Campo.TLabel").grid(
                row=fila, column=0, sticky="w")
            entrada = tk.Entry(formulario, font=(estilos.FUENTE, 13),
                               relief="solid", bd=1, show=mostrar or "")
            entrada.grid(row=fila + 1, column=0, sticky="ew", pady=(2, 10))
            return entrada

        self.campo_nombre = campo(1, "Nombre completo:")
        self.campo_usuario = campo(3, "Usuario de ingreso:")
        self.campo_clave = campo(5, "Contraseña (mín. 6; vacía = no cambiar):",
                                 mostrar="●")

        ttk.Label(formulario, text="Rol:", style="Campo.TLabel").grid(
            row=7, column=0, sticky="w")
        self.rol = tk.StringVar(value="cajero")
        fila_rol = ttk.Frame(formulario, style="Tarjeta.TFrame")
        fila_rol.grid(row=8, column=0, sticky="w", pady=(2, 8))
        for valor, texto in (("cajero", "Cajero"),
                             ("administrador", "Administrador")):
            ttk.Radiobutton(fila_rol, text=texto, value=valor,
                            variable=self.rol).pack(side="left", padx=(0, 16))

        self.activo = tk.BooleanVar(value=True)
        ttk.Checkbutton(formulario, text="Perfil activo (puede iniciar sesión)",
                        variable=self.activo).grid(row=9, column=0, sticky="w",
                                                   pady=(0, 12))

        ttk.Button(formulario, text="Guardar  (F6)", style="Exito.TButton",
                   command=self._guardar).grid(row=10, column=0, sticky="ew",
                                               pady=(0, 6))
        ttk.Button(formulario, text="Nuevo perfil  (F5)", style="Plano.TButton",
                   command=self._nuevo).grid(row=11, column=0, sticky="ew",
                                             pady=(0, 6))
        ttk.Button(formulario, text="Activar / Desactivar  (F8)",
                   style="Peligro.TButton",
                   command=self._alternar_activo).grid(row=12, column=0,
                                                       sticky="ew")

        self._refrescar()
        self.campo_nombre.focus_set()

    # ------------------------------------------------------------ datos

    def _refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for usuario in db.listar_usuarios():
            self.tabla.insert(
                "", "end", iid=str(usuario["id"]),
                values=(usuario["nombre"], usuario["usuario"],
                        usuario["rol"].capitalize(),
                        "Activo" if usuario["activo"] else "Inactivo"),
                tags=() if usuario["activo"] else ("inactivo",))

    def _cargar_seleccion(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        usuario = next((u for u in db.listar_usuarios()
                        if u["id"] == int(seleccion[0])), None)
        if not usuario:
            return
        self.id_editando = usuario["id"]
        self.titulo_form.configure(text=f"Editar: {usuario['usuario']}")
        self.campo_nombre.delete(0, "end")
        self.campo_nombre.insert(0, usuario["nombre"])
        self.campo_usuario.delete(0, "end")
        self.campo_usuario.insert(0, usuario["usuario"])
        self.campo_usuario.configure(state="disabled")  # el ingreso no cambia
        self.campo_clave.delete(0, "end")
        self.rol.set(usuario["rol"])
        self.activo.set(bool(usuario["activo"]))

    def _nuevo(self):
        self.id_editando = None
        self.titulo_form.configure(text="Nuevo perfil")
        self.campo_usuario.configure(state="normal")
        for entrada in (self.campo_nombre, self.campo_usuario, self.campo_clave):
            entrada.delete(0, "end")
        self.rol.set("cajero")
        self.activo.set(True)
        seleccion = self.tabla.selection()
        if seleccion:
            self.tabla.selection_remove(seleccion)
        self.campo_nombre.focus_set()

    def _guardar(self):
        nombre = self.campo_nombre.get().strip()
        clave = self.campo_clave.get()
        if not nombre:
            messagebox.showwarning("Usuarios", "Escriba el nombre completo.",
                                   parent=self.app)
            return
        try:
            if self.id_editando is None:
                usuario = self.campo_usuario.get().strip().lower()
                if not usuario:
                    raise ValueError("Escriba el usuario de ingreso.")
                if len(clave) < 6:
                    raise ValueError("La contraseña debe tener al menos "
                                     "6 caracteres.")
                db.crear_usuario(nombre, usuario, clave, self.rol.get())
                mensaje = f"Perfil «{usuario}» creado."
            else:
                if (self.id_editando == self.app.usuario["id"]
                        and not self.activo.get()):
                    raise ValueError("No puede desactivar su propio perfil "
                                     "mientras lo está usando.")
                db.actualizar_usuario(self.id_editando, nombre, self.rol.get(),
                                      self.activo.get())
                if clave:
                    if len(clave) < 6:
                        raise ValueError("La contraseña debe tener al menos "
                                         "6 caracteres.")
                    db.cambiar_clave(self.id_editando, clave)
                mensaje = "Perfil actualizado."
        except ValueError as error:
            messagebox.showwarning("Usuarios", str(error), parent=self.app)
            return
        self._refrescar()
        self._nuevo()
        messagebox.showinfo("Usuarios", mensaje, parent=self.app)

    def _alternar_activo(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Usuarios", "Seleccione primero un perfil "
                                   "en la lista.", parent=self.app)
            return
        usuario = next((u for u in db.listar_usuarios()
                        if u["id"] == int(seleccion[0])), None)
        if not usuario:
            return
        if (usuario["id"] == self.app.usuario["id"] and usuario["activo"]):
            messagebox.showwarning("Usuarios", "No puede desactivar su propio "
                                   "perfil mientras lo está usando.",
                                   parent=self.app)
            return
        try:
            db.actualizar_usuario(usuario["id"], usuario["nombre"],
                                  usuario["rol"], not usuario["activo"])
        except ValueError as error:
            messagebox.showwarning("Usuarios", str(error), parent=self.app)
            return
        self._refrescar()
        self._nuevo()