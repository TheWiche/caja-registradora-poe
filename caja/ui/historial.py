"""Historial de ventas: búsqueda por fecha (con mini calendario) y por
número de factura, reimpresión y PDF (plan.md §1.6).

Teclas:  F4/↓ en fecha abre calendario · F5 Buscar · F6 Reimprimir ·
         F7 Guardar PDF · F8 Incluir/excluir entrenamiento · Esc Menú
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from .. import db, recibos
from ..util import fmt_dinero, fecha_legible
from . import estilos
from .calendario import EntradaFecha
from .estilos import BarraSuperior


class PantallaHistorial(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app
        self.venta_actual = None

        BarraSuperior(self, app, "Historial de ventas", volver=True)
        app.atajo("<Escape>", lambda e: app.mostrar_menu())
        app.atajo("<F5>", lambda e: self._buscar())
        app.atajo("<F6>", lambda e: self._reimprimir())
        app.atajo("<F7>", lambda e: self._guardar_pdf())
        app.atajo("<F8>", lambda e: self._alternar_entrenamiento())

        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 14, 24, 20))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=2)
        cuerpo.rowconfigure(1, weight=1)

        # ---- filtros
        filtros = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=14)
        filtros.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        hoy = datetime.now().strftime("%d/%m/%Y")

        ttk.Label(filtros, text="Desde:", style="Campo.TLabel").pack(
            side="left", padx=(0, 4))
        self.desde = EntradaFecha(filtros, inicial=hoy,
                                  al_cambiar=self._buscar)
        self.desde.pack(side="left", padx=(0, 14))
        self.desde.bind_enter(self._buscar)

        ttk.Label(filtros, text="Hasta:", style="Campo.TLabel").pack(
            side="left", padx=(0, 4))
        self.hasta = EntradaFecha(filtros, inicial=hoy,
                                  al_cambiar=self._buscar)
        self.hasta.pack(side="left", padx=(0, 14))
        self.hasta.bind_enter(self._buscar)

        ttk.Label(filtros, text="N.º factura:", style="Campo.TLabel").pack(
            side="left", padx=(0, 4))
        self.numero = tk.Entry(filtros, font=(estilos.FUENTE, 12), width=12,
                               relief="solid", bd=1)
        self.numero.pack(side="left", padx=(0, 14), ipady=3)
        self.numero.bind("<Return>", lambda e: self._buscar())

        self.incluir_entrenamiento = tk.BooleanVar(value=True)
        ttk.Checkbutton(filtros, text="Incluir entrenamiento (F8)",
                        variable=self.incluir_entrenamiento,
                        command=self._buscar).pack(side="left", padx=(0, 14))
        ttk.Button(filtros, text="Buscar (F5)", style="Primario.TButton",
                   command=self._buscar).pack(side="left")

        # ---- lista de ventas
        panel_lista = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=12)
        panel_lista.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        panel_lista.rowconfigure(0, weight=1)
        panel_lista.columnconfigure(0, weight=1)

        columnas = ("factura", "fecha", "cajero", "metodo", "total")
        self.tabla = ttk.Treeview(panel_lista, columns=columnas, show="headings",
                                  selectmode="browse")
        for col, titulo, ancho, ancla in (
                ("factura", "Factura", 100, "w"), ("fecha", "Fecha", 140, "w"),
                ("cajero", "Cajero", 160, "w"), ("metodo", "Pago", 110, "w"),
                ("total", "Total", 100, "e")):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor=ancla)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(panel_lista, orient="vertical",
                              command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.grid(row=0, column=1, sticky="ns")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._mostrar_detalle())

        self.resumen = ttk.Label(panel_lista, text="", style="SubTarjeta.TLabel")
        self.resumen.grid(row=1, column=0, sticky="w", pady=(8, 0))

        # el número de factura salta a la lista con ↓ para navegar con flechas
        self.numero.bind("<Down>", lambda e: self._foco_tabla())

        # ---- detalle del recibo
        panel_detalle = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=12)
        panel_detalle.grid(row=1, column=1, sticky="nsew")
        panel_detalle.rowconfigure(0, weight=1)
        panel_detalle.columnconfigure(0, weight=1)

        self.detalle = tk.Text(panel_detalle, font=(estilos.MONO, 10), width=44,
                               relief="flat", bg="#fbfbf7", state="disabled")
        self.detalle.grid(row=0, column=0, sticky="nsew")

        fila_botones = ttk.Frame(panel_detalle, style="Tarjeta.TFrame")
        fila_botones.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(fila_botones, text="Reimprimir (F6)", style="Primario.TButton",
                   command=self._reimprimir).pack(side="left", expand=True,
                                                  fill="x", padx=(0, 6))
        ttk.Button(fila_botones, text="Guardar PDF (F7)", style="Plano.TButton",
                   command=self._guardar_pdf).pack(side="left", expand=True,
                                                   fill="x")
        self._buscar()

    def _foco_tabla(self):
        hijos = self.tabla.get_children()
        if hijos:
            self.tabla.focus_set()
            self.tabla.selection_set(hijos[0])
            self.tabla.focus(hijos[0])

    def _alternar_entrenamiento(self):
        self.incluir_entrenamiento.set(not self.incluir_entrenamiento.get())
        self._buscar()

    def _buscar(self):
        ventas = db.buscar_ventas(desde=self.desde.iso() or "",
                                  hasta=self.hasta.iso() or "",
                                  numero=self.numero.get(),
                                  incluir_entrenamiento=
                                  self.incluir_entrenamiento.get())
        self.tabla.delete(*self.tabla.get_children())
        for venta in ventas:
            self.tabla.insert("", "end", iid=str(venta["id"]),
                              values=(venta["numero_factura"],
                                      fecha_legible(venta["fecha"]),
                                      venta["nombre_cajero"],
                                      venta["metodo_pago"],
                                      fmt_dinero(venta["total"])))
        total = sum(v["total"] for v in ventas if not v["entrenamiento"])
        self.resumen.configure(
            text=f"{len(ventas)} venta(s) encontradas · "
                 f"Total real (sin entrenamiento): {fmt_dinero(total)}")
        self.venta_actual = None
        self._pintar_detalle("Seleccione una venta (↓ desde el nº de factura "
                             "y flechas) para ver su recibo.")

    def _mostrar_detalle(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        self.venta_actual = db.obtener_venta(int(seleccion[0]))
        if self.venta_actual:
            self._pintar_detalle(recibos.texto_recibo(self.venta_actual))

    def _pintar_detalle(self, texto):
        self.detalle.configure(state="normal")
        self.detalle.delete("1.0", "end")
        self.detalle.insert("1.0", texto)
        self.detalle.configure(state="disabled")

    def _reimprimir(self):
        if not self.venta_actual:
            messagebox.showwarning("Historial", "Seleccione primero una venta.",
                                   parent=self.app)
            return
        try:
            recibos.imprimir(self.venta_actual)
            messagebox.showinfo("Historial", "Recibo enviado a la impresora.",
                                parent=self.app)
        except OSError:
            messagebox.showwarning(
                "Historial", "No se pudo imprimir. El recibo quedó guardado en "
                "datos/tickets.", parent=self.app)

    def _guardar_pdf(self):
        if not self.venta_actual:
            messagebox.showwarning("Historial", "Seleccione primero una venta.",
                                   parent=self.app)
            return
        sugerida = recibos.ruta_pdf_sugerida(self.venta_actual)
        ruta = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".pdf",
            initialdir=str(sugerida.parent), initialfile=sugerida.name,
            filetypes=[("Archivo PDF", "*.pdf")])
        if ruta:
            recibos.generar_pdf(self.venta_actual, ruta)
            messagebox.showinfo("Historial", f"PDF guardado en:\n{ruta}",
                                parent=self.app)