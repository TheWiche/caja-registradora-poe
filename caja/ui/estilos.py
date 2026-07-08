"""Estilos compartidos: colores planos, tipografía grande, cero animaciones.

Cumple plan.md §6.3: sin efectos visuales, sin transiciones, sin multimedia.
Botones grandes y alto contraste para uso rápido en mostrador (plan.md §4).
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
from datetime import datetime

# Paleta sobria de alto contraste
FONDO = "#eef1f5"
TARJETA = "#ffffff"
PRIMARIO = "#1d4ed8"
PRIMARIO_OSCURO = "#1e3a8a"
EXITO = "#15803d"
EXITO_OSCURO = "#14532d"
PELIGRO = "#b91c1c"
PELIGRO_OSCURO = "#7f1d1d"
AVISO = "#c2410c"
TEXTO = "#111827"
GRIS = "#6b7280"
BORDE = "#cbd5e1"
FILA_ALTERNA = "#f8fafc"

FUENTE = "Segoe UI"
MONO = "Consolas"

# Visor de totales estilo pantalla de cliente de un POS real
DISPLAY_FONDO = "#0f172a"
DISPLAY_VERDE = "#4ade80"
DISPLAY_AMBAR = "#fbbf24"
DISPLAY_GRIS = "#94a3b8"


def aplicar_estilos(raiz: tk.Tk):
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")

    for nombre in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
        tkfont.nametofont(nombre).configure(family=FUENTE, size=11)

    raiz.configure(bg=FONDO)
    estilo.configure(".", background=FONDO, foreground=TEXTO,
                     font=(FUENTE, 11))

    # --- marcos y etiquetas
    estilo.configure("Fondo.TFrame", background=FONDO)
    estilo.configure("Tarjeta.TFrame", background=TARJETA, relief="flat")
    estilo.configure("TLabel", background=FONDO, foreground=TEXTO)
    estilo.configure("Tarjeta.TLabel", background=TARJETA)
    estilo.configure("Titulo.TLabel", font=(FUENTE, 22, "bold"),
                     background=FONDO, foreground=PRIMARIO_OSCURO)
    estilo.configure("TituloTarjeta.TLabel", font=(FUENTE, 20, "bold"),
                     background=TARJETA, foreground=PRIMARIO_OSCURO)
    estilo.configure("Sub.TLabel", font=(FUENTE, 11), background=FONDO,
                     foreground=GRIS)
    estilo.configure("SubTarjeta.TLabel", font=(FUENTE, 11),
                     background=TARJETA, foreground=GRIS)
    estilo.configure("Campo.TLabel", font=(FUENTE, 12, "bold"),
                     background=TARJETA, foreground=TEXTO)
    estilo.configure("TotalGrande.TLabel", font=(FUENTE, 30, "bold"),
                     background=TARJETA, foreground=PRIMARIO_OSCURO)
    estilo.configure("CambioGrande.TLabel", font=(FUENTE, 26, "bold"),
                     background=TARJETA, foreground=EXITO)

    # --- visor tipo POS (panel oscuro con dígitos grandes)
    estilo.configure("Display.TFrame", background=DISPLAY_FONDO)
    estilo.configure("DisplayTitulo.TLabel", background=DISPLAY_FONDO,
                     foreground=DISPLAY_GRIS, font=(FUENTE, 12, "bold"))
    estilo.configure("DisplayTotal.TLabel", background=DISPLAY_FONDO,
                     foreground=DISPLAY_VERDE, font=(MONO, 38, "bold"))
    estilo.configure("DisplayCambio.TLabel", background=DISPLAY_FONDO,
                     foreground=DISPLAY_AMBAR, font=(MONO, 32, "bold"))
    estilo.configure("DisplaySub.TLabel", background=DISPLAY_FONDO,
                     foreground=DISPLAY_GRIS, font=(FUENTE, 11))

    # --- barra superior unificada (todas las pantallas)
    estilo.configure("BarraTitulo.TLabel", background=DISPLAY_FONDO,
                     foreground="white", font=(FUENTE, 17, "bold"))
    estilo.configure("BarraInfo.TLabel", background=DISPLAY_FONDO,
                     foreground=DISPLAY_GRIS, font=(FUENTE, 11))
    estilo.configure("Entrenamiento.TLabel", font=(FUENTE, 12, "bold"),
                     background=AVISO, foreground="white", padding=(10, 4))

    # --- botones grandes (plan.md §4 usabilidad)
    def boton(nombre, color, color_activo):
        estilo.configure(nombre, font=(FUENTE, 13, "bold"),
                         background=color, foreground="white",
                         borderwidth=0, focusthickness=2, padding=(18, 12))
        estilo.map(nombre,
                   background=[("active", color_activo),
                               ("disabled", BORDE)],
                   foreground=[("disabled", GRIS)])

    boton("Primario.TButton", PRIMARIO, PRIMARIO_OSCURO)
    boton("Exito.TButton", EXITO, EXITO_OSCURO)
    boton("Peligro.TButton", PELIGRO, PELIGRO_OSCURO)
    estilo.configure("Plano.TButton", font=(FUENTE, 11), background=TARJETA,
                     foreground=PRIMARIO_OSCURO, borderwidth=1, padding=(10, 8))
    estilo.map("Plano.TButton", background=[("active", FONDO)])

    # Losetas del menú principal: tarjetas blancas que se encienden al pasar
    estilo.configure("Tile.TButton", font=(FUENTE, 14, "bold"),
                     background=TARJETA, foreground=TEXTO,
                     borderwidth=0, padding=(22, 24), anchor="center")
    estilo.map("Tile.TButton",
               background=[("active", PRIMARIO), ("disabled", FONDO)],
               foreground=[("active", "white"), ("disabled", BORDE)])

    # --- entradas y tablas
    estilo.configure("TEntry", fieldbackground="white", padding=6)
    estilo.configure("Treeview", font=(FUENTE, 12), rowheight=34,
                     fieldbackground="white", background="white")
    estilo.configure("Treeview.Heading", font=(FUENTE, 11, "bold"),
                     background=PRIMARIO_OSCURO, foreground="white",
                     padding=(6, 8))
    estilo.map("Treeview", background=[("selected", PRIMARIO)],
               foreground=[("selected", "white")])

    estilo.configure("TRadiobutton", background=TARJETA, font=(FUENTE, 12))
    estilo.configure("TCheckbutton", background=TARJETA, font=(FUENTE, 12))
    estilo.configure("Fondo.TCheckbutton", background=FONDO, font=(FUENTE, 12))


def entrada_grande(padre, **kwargs):
    """Entrada de texto con letra grande, pensada para el lector de códigos."""
    return tk.Entry(padre, font=(FUENTE, 18), relief="solid", bd=1,
                    highlightthickness=2, highlightcolor=PRIMARIO, **kwargs)


class DialogoNumero(tk.Toplevel):
    """Diálogo modal con letra grande para pedir un número (cantidad/monto)."""

    def __init__(self, padre, titulo, mensaje, inicial="", solo_entero=True):
        super().__init__(padre)
        self.title(titulo)
        self.resultado = None
        self._solo_entero = solo_entero
        self.configure(bg=TARJETA, padx=24, pady=18)
        self.resizable(False, False)
        self.transient(padre)

        tk.Label(self, text=mensaje, font=(FUENTE, 13), bg=TARJETA,
                 fg=TEXTO).pack(anchor="w")
        self.entrada = entrada_grande(self, width=14, justify="center")
        self.entrada.pack(pady=12)
        self.entrada.insert(0, str(inicial))
        self.entrada.select_range(0, "end")

        fila = tk.Frame(self, bg=TARJETA)
        fila.pack(fill="x")
        ttk.Button(fila, text="Aceptar", style="Exito.TButton",
                   command=self._aceptar).pack(side="left", expand=True,
                                               fill="x", padx=(0, 6))
        ttk.Button(fila, text="Cancelar", style="Plano.TButton",
                   command=self.destroy).pack(side="left", expand=True, fill="x")

        self.bind("<Return>", lambda e: self._aceptar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.entrada.focus_set()
        self.grab_set()
        # Centrar sobre la ventana padre
        self.update_idletasks()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.wait_window()

    def _aceptar(self):
        from ..util import parse_dinero
        valor = parse_dinero(self.entrada.get())
        if valor is None or (self._solo_entero and valor <= 0):
            self.entrada.configure(highlightcolor=PELIGRO,
                                   highlightbackground=PELIGRO)
            self.bell()
            return
        self.resultado = valor
        self.destroy()


def pedir_numero(padre, titulo, mensaje, inicial=""):
    """Devuelve el número ingresado o None si se canceló."""
    return DialogoNumero(padre, titulo, mensaje, inicial).resultado


class BarraSuperior(ttk.Frame):
    """Barra oscura unificada de todas las pantallas: título, badge de
    entrenamiento, cajero y reloj en vivo. `self.extra` es un hueco a la
    derecha donde cada pantalla puede colgar sus propios indicadores."""

    def __init__(self, padre, app, titulo, entrenamiento=False, volver=False):
        super().__init__(padre, style="Display.TFrame", padding=(24, 12))
        self.pack(fill="x", side="top")
        ttk.Label(self, text=titulo, style="BarraTitulo.TLabel").pack(side="left")
        if entrenamiento:
            tk.Label(self, text="ENTRENAMIENTO", bg=AVISO, fg="white",
                     font=(FUENTE, 10, "bold"), padx=10, pady=3).pack(
                side="left", padx=16)
        if volver:
            tk.Button(self, text="← Menú (Esc)", command=app.mostrar_menu,
                      font=(FUENTE, 10, "bold"), bg=DISPLAY_FONDO,
                      fg=DISPLAY_GRIS, activebackground="#1e293b",
                      activeforeground="white", relief="flat",
                      cursor="hand2").pack(side="left", padx=16)
        self.reloj = ttk.Label(self, style="BarraInfo.TLabel")
        self.reloj.pack(side="right")
        if app.usuario:
            ttk.Label(self, text=f"{app.usuario['nombre']}  ·  "
                                 f"{app.usuario['rol'].capitalize()}",
                      style="BarraInfo.TLabel").pack(side="right", padx=(0, 20))
        self.extra = ttk.Frame(self, style="Display.TFrame")
        self.extra.pack(side="right", padx=(0, 20))
        self._tic()

    def _tic(self):
        try:
            if not self.winfo_exists():
                return
            self.reloj.configure(
                text=datetime.now().strftime("%d/%m/%Y   %H:%M:%S"))
            self.after(1000, self._tic)
        except tk.TclError:
            pass
