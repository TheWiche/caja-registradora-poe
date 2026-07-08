"""Mini calendario emergente y campo de fecha, sin librerías externas.

Pensado primero para el teclado (plan.md §4 usabilidad):
  ←/→        día anterior / siguiente
  ↑/↓        semana anterior / siguiente
  RePág/AvPág  mes anterior / siguiente
  Inicio     hoy
  Enter      elegir la fecha
  Esc        cerrar sin elegir
También funciona con un clic sobre el día.
"""

import calendar
import tkinter as tk
from datetime import date, timedelta

from ..util import parse_fecha_usuario
from . import estilos

_MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
          "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
_DIAS = ("Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do")


class MiniCalendario(tk.Toplevel):
    def __init__(self, ancla: tk.Widget, inicial: date, al_elegir):
        super().__init__(ancla)
        self.al_elegir = al_elegir
        self.fecha = inicial
        self.overrideredirect(True)  # ventana emergente sin bordes
        self.configure(bg=estilos.TARJETA, highlightthickness=1,
                       highlightbackground=estilos.BORDE, padx=10, pady=8)

        cabecera = tk.Frame(self, bg=estilos.TARJETA)
        cabecera.pack(fill="x", pady=(0, 6))
        tk.Button(cabecera, text="◀", relief="flat", bg=estilos.TARJETA,
                  font=(estilos.FUENTE, 11, "bold"), cursor="hand2",
                  command=lambda: self._mover_mes(-1)).pack(side="left")
        self.lbl_mes = tk.Label(cabecera, bg=estilos.TARJETA,
                                fg=estilos.PRIMARIO_OSCURO,
                                font=(estilos.FUENTE, 12, "bold"))
        self.lbl_mes.pack(side="left", expand=True)
        tk.Button(cabecera, text="▶", relief="flat", bg=estilos.TARJETA,
                  font=(estilos.FUENTE, 11, "bold"), cursor="hand2",
                  command=lambda: self._mover_mes(1)).pack(side="right")

        self.malla = tk.Frame(self, bg=estilos.TARJETA)
        self.malla.pack()

        pie = tk.Label(self, text="←↑↓→ mover · RePág/AvPág mes · Enter elegir",
                       bg=estilos.TARJETA, fg=estilos.GRIS,
                       font=(estilos.FUENTE, 8))
        pie.pack(pady=(6, 0))

        self.bind("<Left>", lambda e: self._mover_dias(-1))
        self.bind("<Right>", lambda e: self._mover_dias(1))
        self.bind("<Up>", lambda e: self._mover_dias(-7))
        self.bind("<Down>", lambda e: self._mover_dias(7))
        self.bind("<Prior>", lambda e: self._mover_mes(-1))
        self.bind("<Next>", lambda e: self._mover_mes(1))
        self.bind("<Home>", lambda e: self._ir_hoy())
        self.bind("<Return>", lambda e: self._elegir(self.fecha))
        self.bind("<Escape>", lambda e: self.destroy())
        # clic fuera del calendario: cerrar (la ventana tiene el grab)
        self.bind("<ButtonPress-1>", self._clic_global, add=True)

        self._pintar()
        # posicionar bajo el campo ancla, sin salirse de la pantalla
        self.update_idletasks()
        x = ancla.winfo_rootx()
        y = ancla.winfo_rooty() + ancla.winfo_height() + 2
        x = min(x, self.winfo_screenwidth() - self.winfo_width() - 8)
        y = min(y, self.winfo_screenheight() - self.winfo_height() - 8)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_set()
        self.grab_set()

    # ------------------------------------------------------------ navegación

    def _mover_dias(self, dias: int):
        self.fecha += timedelta(days=dias)
        self._pintar()

    def _mover_mes(self, meses: int):
        anio, mes = self.fecha.year, self.fecha.month + meses
        if mes < 1:
            anio, mes = anio - 1, 12
        elif mes > 12:
            anio, mes = anio + 1, 1
        dia = min(self.fecha.day, calendar.monthrange(anio, mes)[1])
        self.fecha = date(anio, mes, dia)
        self._pintar()

    def _ir_hoy(self):
        self.fecha = date.today()
        self._pintar()

    def _elegir(self, dia: date):
        elegir, self.al_elegir = self.al_elegir, None
        self.destroy()
        if elegir:
            elegir(dia)

    def _clic_global(self, evento):
        # con grab_set, los clics fuera de la ventana también llegan aquí
        if not (0 <= evento.x_root - self.winfo_rootx() <= self.winfo_width()
                and 0 <= evento.y_root - self.winfo_rooty() <= self.winfo_height()):
            self.destroy()

    # ------------------------------------------------------------ dibujo

    def _pintar(self):
        for widget in self.malla.winfo_children():
            widget.destroy()
        self.lbl_mes.configure(text=f"{_MESES[self.fecha.month - 1]} "
                                    f"{self.fecha.year}")
        for columna, nombre in enumerate(_DIAS):
            tk.Label(self.malla, text=nombre, width=4, bg=estilos.TARJETA,
                     fg=estilos.GRIS, font=(estilos.FUENTE, 9, "bold")).grid(
                row=0, column=columna)

        hoy = date.today()
        semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.fecha.year, self.fecha.month)
        for fila, semana in enumerate(semanas, start=1):
            for columna, dia in enumerate(semana):
                if dia == self.fecha:
                    bg, fg, peso = estilos.PRIMARIO, "white", "bold"
                elif dia == hoy:
                    bg, fg, peso = estilos.FONDO, estilos.PRIMARIO_OSCURO, "bold"
                elif dia.month != self.fecha.month:
                    bg, fg, peso = estilos.TARJETA, estilos.BORDE, "normal"
                else:
                    bg, fg, peso = estilos.TARJETA, estilos.TEXTO, "normal"
                celda = tk.Label(self.malla, text=str(dia.day), width=4, pady=3,
                                 bg=bg, fg=fg, cursor="hand2",
                                 font=(estilos.FUENTE, 10, peso))
                celda.grid(row=fila, column=columna)
                celda.bind("<ButtonPress-1>",
                           lambda e, d=dia: self._elegir(d))


class EntradaFecha(tk.Frame):
    """Campo de fecha dd/mm/aaaa con calendario emergente.

    Teclado: F4 o flecha ↓ abren el calendario; también se puede escribir
    la fecha directamente. `al_cambiar` se llama al elegir en el calendario.
    """

    def __init__(self, padre, inicial="", al_cambiar=None, ancho=11):
        super().__init__(padre, bg=estilos.TARJETA)
        self.al_cambiar = al_cambiar
        self.entrada = tk.Entry(self, font=(estilos.FUENTE, 12), width=ancho,
                                relief="solid", bd=1)
        self.entrada.pack(side="left", ipady=3)
        self.entrada.insert(0, inicial)
        boton = tk.Button(self, text="📅", relief="flat", bg=estilos.TARJETA,
                          cursor="hand2", font=(estilos.FUENTE, 11),
                          command=self.abrir)
        boton.pack(side="left", padx=(2, 0))
        self.entrada.bind("<Down>", lambda e: self.abrir())
        self.entrada.bind("<F4>", lambda e: self.abrir())

    def abrir(self):
        iso = parse_fecha_usuario(self.entrada.get())
        inicial = date.fromisoformat(iso) if iso else date.today()
        MiniCalendario(self.entrada, inicial, self._poner)

    def _poner(self, dia: date):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, dia.strftime("%d/%m/%Y"))
        if self.al_cambiar:
            self.al_cambiar()

    def get(self) -> str:
        return self.entrada.get()

    def iso(self):
        """Fecha en formato ISO o None si el texto no es válido."""
        return parse_fecha_usuario(self.entrada.get())

    def bind_enter(self, funcion):
        self.entrada.bind("<Return>", lambda e: funcion())