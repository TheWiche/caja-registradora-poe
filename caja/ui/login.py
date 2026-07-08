"""Pantalla de inicio de sesión (plan.md §1.1)."""

import tkinter as tk
from tkinter import ttk

from .. import db
from . import estilos


class PantallaLogin(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app

        tarjeta = ttk.Frame(self, style="Tarjeta.TFrame", padding=40)
        tarjeta.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(tarjeta, text="SISTEMA DE CAJA",
                  style="TituloTarjeta.TLabel").pack()
        ttk.Label(tarjeta, text="Herramienta didáctica de caja registradora",
                  style="SubTarjeta.TLabel").pack(pady=(2, 24))

        ttk.Label(tarjeta, text="Usuario", style="Campo.TLabel").pack(anchor="w")
        self.usuario = estilos.entrada_grande(tarjeta, width=22)
        self.usuario.pack(pady=(4, 14))

        ttk.Label(tarjeta, text="Contraseña", style="Campo.TLabel").pack(anchor="w")
        self.clave = estilos.entrada_grande(tarjeta, width=22, show="●")
        self.clave.pack(pady=(4, 6))

        self.error = tk.Label(tarjeta, text="", font=(estilos.FUENTE, 11, "bold"),
                              bg=estilos.TARJETA, fg=estilos.PELIGRO)
        self.error.pack(pady=(0, 6))

        ttk.Button(tarjeta, text="Ingresar  (Enter)", style="Primario.TButton",
                   command=self._ingresar).pack(fill="x", pady=(4, 0))

        ttk.Label(tarjeta, text="Primer uso:  admin / admin123   ·   cajero / cajero123",
                  style="SubTarjeta.TLabel").pack(pady=(18, 0))

        self.usuario.bind("<Return>", lambda e: self.clave.focus_set())
        self.clave.bind("<Return>", lambda e: self._ingresar())
        self.usuario.focus_set()

    def _ingresar(self):
        usuario = db.autenticar(self.usuario.get(), self.clave.get())
        if usuario is None:
            self.error.configure(text="Usuario o contraseña incorrectos")
            self.clave.delete(0, "end")
            self.bell()
            return
        self.app.iniciar_sesion(usuario)
