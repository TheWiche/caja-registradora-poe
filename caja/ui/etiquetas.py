"""Diálogo modal: código de barras de un producto (ver, guardar PDF,
imprimir). Mismo patrón visual/estructural que DialogoQRTransferencia
(caja/ui/venta.py): Toplevel modal centrado sobre el padre, Canvas
dibujado a mano, degradación con gracia si algo falla (plan.md §5/§6.6:
nunca romper la pantalla por un problema de representación).
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .. import barras
from ..util import fmt_dinero
from . import estilos

log = logging.getLogger("caja")


class DialogoCodigoBarras(tk.Toplevel):
    def __init__(self, padre, producto: dict):
        super().__init__(padre)
        self.title("Código de barras")
        self.producto = producto
        self.configure(bg=estilos.TARJETA, padx=22, pady=18)
        self.transient(padre)
        self.resizable(False, False)

        try:
            self.codigo = barras.generar_codigo_barras(producto["codigo_barras"])
        except ValueError as error:
            tk.Label(self, text=str(error), bg=estilos.TARJETA,
                     fg=estilos.PELIGRO, wraplength=280,
                     justify="left").pack(pady=10)
            ttk.Button(self, text="Cerrar (Esc)", style="Plano.TButton",
                       command=self.destroy).pack(fill="x", pady=(8, 0))
            log.exception("No se pudo generar el código de barras")
            self.codigo = None
        else:
            self._construir()

        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.update_idletasks()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_set()
        self.wait_window()

    def _construir(self):
        tk.Label(self, text=self.producto["nombre"][:32],
                 font=(estilos.FUENTE, 14, "bold"),
                 bg=estilos.TARJETA, wraplength=280,
                 justify="left").pack(anchor="w")
        tk.Label(self, text=fmt_dinero(self.producto["precio"]),
                 font=(estilos.MONO, 16, "bold"), fg=estilos.PRIMARIO_OSCURO,
                 bg=estilos.TARJETA).pack(anchor="w", pady=(0, 10))

        self._dibujar_barras()

        tk.Label(self, text=self.codigo.texto,
                 font=(estilos.MONO, 12), bg=estilos.TARJETA,
                 fg=estilos.TEXTO).pack(pady=(4, 2))
        tk.Label(self, text=f"Simbología: {self.codigo.simbologia}",
                 font=(estilos.FUENTE, 9), bg=estilos.TARJETA,
                 fg=estilos.GRIS).pack(pady=(0, 12))

        fila = tk.Frame(self, bg=estilos.TARJETA)
        fila.pack(fill="x")
        ttk.Button(fila, text="Guardar PDF", style="Primario.TButton",
                   command=self._guardar_pdf).grid(row=0, column=0,
                                                    sticky="ew", padx=(0, 4))
        ttk.Button(fila, text="Imprimir", style="Exito.TButton",
                   command=self._imprimir).grid(row=0, column=1, sticky="ew",
                                                padx=(4, 0))
        fila.columnconfigure(0, weight=1)
        fila.columnconfigure(1, weight=1)
        ttk.Button(self, text="Cerrar (Esc)", style="Plano.TButton",
                   command=self.destroy).pack(fill="x", pady=(8, 0))

    def _dibujar_barras(self):
        ancho_lienzo, alto_lienzo = 280, 110
        escala = ancho_lienzo / self.codigo.ancho_modulos
        base = 90
        lienzo = tk.Canvas(self, width=ancho_lienzo, height=alto_lienzo,
                           bg="white", highlightthickness=1,
                           highlightbackground=estilos.BORDE)
        lienzo.pack(pady=(0, 6))
        for barra in self.codigo.barras:
            alto = 70 if barra.alta else 60
            x0 = barra.inicio * escala
            ancho = max(1, barra.ancho * escala)
            lienzo.create_rectangle(x0, base - alto, x0 + ancho, base,
                                    fill="black", width=0)

    def _guardar_pdf(self):
        sugerida = barras.ruta_etiqueta_sugerida(self.producto)
        ruta = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf",
            initialdir=str(sugerida.parent), initialfile=sugerida.name,
            filetypes=[("Archivo PDF", "*.pdf")])
        if ruta:
            barras.generar_pdf_etiqueta(self.producto, ruta)
            messagebox.showinfo("Código de barras",
                                f"Etiqueta guardada en:\n{ruta}", parent=self)

    def _imprimir(self):
        try:
            barras.imprimir_etiqueta(self.producto)
            messagebox.showinfo("Código de barras",
                                "Etiqueta enviada a la impresora "
                                "predeterminada.", parent=self)
        except OSError:
            messagebox.showwarning(
                "Código de barras",
                "No se pudo imprimir (¿hay una impresora instalada?).\n"
                "La etiqueta quedó guardada en la carpeta datos/etiquetas.",
                parent=self)
