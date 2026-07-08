"""Reportes básicos: total por día, número de ventas, producto más
vendido (plan.md §1.7). Las ventas de entrenamiento quedan excluidas.

Teclas:  F1 Hoy · F2 Últimos 7 días · F3 Este mes · F4 Todo · Esc Menú
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from .. import db
from ..util import fmt_dinero
from . import estilos
from .estilos import BarraSuperior

_PERIODOS = ("Hoy", "Últimos 7 días", "Este mes", "Todo")


class PantallaReportes(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app

        BarraSuperior(self, app, "Reportes", volver=True)
        app.atajo("<Escape>", lambda e: app.mostrar_menu())
        for indice, nombre in enumerate(_PERIODOS, start=1):
            app.atajo(f"<F{indice}>",
                      lambda e, n=nombre: (self.periodo.set(n),
                                           self._refrescar()))

        # ---- selector de periodo
        selector = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 12, 24, 8))
        selector.pack(fill="x")
        self.periodo = tk.StringVar(value="Hoy")
        for indice, texto in enumerate(_PERIODOS, start=1):
            ttk.Radiobutton(selector, text=f"{texto}  (F{indice})", value=texto,
                            variable=self.periodo, style="Fondo.TCheckbutton",
                            command=self._refrescar).pack(side="left",
                                                          padx=(0, 18))
        ttk.Label(selector, text="Las ventas de entrenamiento no se cuentan.",
                  style="Sub.TLabel").pack(side="right")

        # ---- tarjetas de resumen
        tarjetas = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 4, 24, 8))
        tarjetas.pack(fill="x")
        self.tarjetas = {}
        for clave, titulo in (("total", "Total vendido"),
                              ("ventas", "Número de ventas"),
                              ("promedio", "Ticket promedio"),
                              ("top", "Producto más vendido")):
            tarjeta = ttk.Frame(tarjetas, style="Tarjeta.TFrame", padding=16)
            tarjeta.pack(side="left", expand=True, fill="x", padx=(0, 12))
            ttk.Label(tarjeta, text=titulo, style="SubTarjeta.TLabel").pack(anchor="w")
            valor = ttk.Label(tarjeta, text="—", style="TituloTarjeta.TLabel")
            valor.pack(anchor="w")
            self.tarjetas[clave] = valor

        # ---- tablas
        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 8, 24, 20))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(1, weight=1)

        ttk.Label(cuerpo, text="Ventas por día", style="Campo.TLabel",
                  background=estilos.FONDO).grid(row=0, column=0, sticky="w")
        self.tabla_dias = self._tabla(cuerpo, 0, (
            ("dia", "Día", 120, "w"), ("ventas", "Ventas", 90, "center"),
            ("total", "Total", 120, "e")))

        ttk.Label(cuerpo, text="Productos más vendidos", style="Campo.TLabel",
                  background=estilos.FONDO).grid(row=0, column=1, sticky="w",
                                                 padx=(12, 0))
        self.tabla_top = self._tabla(cuerpo, 1, (
            ("nombre", "Producto", 220, "w"), ("unidades", "Unidades", 90, "center"),
            ("total", "Total", 120, "e")), padx=(12, 0))

        self._refrescar()

    def _tabla(self, padre, columna, definicion, padx=(0, 0)):
        marco = ttk.Frame(padre, style="Tarjeta.TFrame", padding=8)
        marco.grid(row=1, column=columna, sticky="nsew", padx=padx, pady=(4, 0))
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        tabla = ttk.Treeview(marco, columns=[c[0] for c in definicion],
                             show="headings", selectmode="none")
        for col, titulo, ancho, ancla in definicion:
            tabla.heading(col, text=titulo)
            tabla.column(col, width=ancho, anchor=ancla)
        tabla.grid(row=0, column=0, sticky="nsew")
        return tabla

    def _rango(self):
        hoy = datetime.now().date()
        periodo = self.periodo.get()
        if periodo == "Hoy":
            return str(hoy), str(hoy)
        if periodo == "Últimos 7 días":
            return str(hoy - timedelta(days=6)), str(hoy)
        if periodo == "Este mes":
            return str(hoy.replace(day=1)), str(hoy)
        return "0000-01-01", str(hoy)

    def _refrescar(self):
        desde, hasta = self._rango()
        resumen = db.reporte_resumen(desde, hasta)
        numero = resumen["numero_ventas"]
        total = resumen["total_vendido"]
        self.tarjetas["total"].configure(text=fmt_dinero(total))
        self.tarjetas["ventas"].configure(text=str(numero))
        self.tarjetas["promedio"].configure(
            text=fmt_dinero(total // numero) if numero else "—")

        top = db.reporte_top_productos(desde, hasta)
        self.tarjetas["top"].configure(text=top[0]["nombre"] if top else "—")

        self.tabla_dias.delete(*self.tabla_dias.get_children())
        for fila in db.reporte_por_dia(desde, hasta):
            dia = datetime.strptime(fila["dia"], "%Y-%m-%d").strftime("%d/%m/%Y")
            self.tabla_dias.insert("", "end", values=(
                dia, fila["ventas"], fmt_dinero(fila["total"])))

        self.tabla_top.delete(*self.tabla_top.get_children())
        for fila in top:
            self.tabla_top.insert("", "end", values=(
                fila["nombre"], fila["unidades"], fmt_dinero(fila["total"])))
