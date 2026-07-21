"""Pantalla principal de caja (plan.md §1.3, §1.4, §1.5, §3).

Flujo calcado de un punto de venta real: el cajero solo escanea; el
cobro es un paso aparte (F12) con denominaciones rápidas; al terminar,
el CAMBIO queda visible en el visor y el foco vuelve al campo de código
para atender al siguiente cliente sin tocar el mouse.

Atajos:
  Enter  agrega el código escrito/escaneado («3*7701001» agrega 3)
  F2     cambiar cantidad de la línea seleccionada
  Supr   quitar la línea seleccionada
  F3     buscar producto por nombre
  F4     consultar precio sin agregar a la venta
  F6     reimprimir la última venta
  F12    cobrar
  Esc    cancelar la venta / volver al menú

Tras cada cambio el carrito se escribe en un diario en disco: si el
equipo se apaga a mitad de una venta, al volver a entrar se recupera.
"""

import logging
import secrets
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .. import db, recibos, pasarela, qr
from ..util import fmt_dinero, parse_dinero
from . import estilos
from .estilos import pedir_numero

log = logging.getLogger("caja")

METODOS = ("Efectivo", "Tarjeta", "Transferencia")
DENOMINACIONES = (10000, 20000, 50000, 100000)
TIPOS_TARJETA = ("Débito", "Crédito")


class PantallaVenta(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app
        self.items = []  # [{id, codigo, nombre, precio, cantidad}]
        self.ultima_venta = None
        self.iva_pct = int(db.obtener_config("iva_porcentaje", "0") or 0)
        self.entrenamiento = db.config_activa("modo_entrenamiento")

        self._construir()
        self._atajos()
        self._recuperar_diario()
        self._sincronizar()
        self.entrada_codigo.focus_set()

    # ------------------------------------------------------------ interfaz

    def _construir(self):
        barra = estilos.BarraSuperior(
            self, self.app,
            db.obtener_config("nombre_negocio", "SISTEMA DE CAJA"),
            entrenamiento=self.entrenamiento)
        self.lbl_ticket = tk.Label(barra.extra, text="",
                                   bg=estilos.DISPLAY_FONDO, fg="white",
                                   font=(estilos.FUENTE, 12, "bold"))
        self.lbl_ticket.pack()

        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 8, 24, 8))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=0)
        cuerpo.rowconfigure(0, weight=1)

        # ---- panel izquierdo: código + tabla de productos
        izquierda = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=18)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        izquierda.rowconfigure(2, weight=1)
        izquierda.columnconfigure(0, weight=1)

        ttk.Label(izquierda, text="Código de barras",
                  style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.entrada_codigo = estilos.entrada_grande(izquierda)
        self.entrada_codigo.grid(row=1, column=0, sticky="ew", pady=(6, 12))
        self.entrada_codigo.bind("<Return>", lambda e: self._agregar_codigo())

        columnas = ("codigo", "nombre", "cant", "precio", "subtotal")
        self.tabla = ttk.Treeview(izquierda, columns=columnas, show="headings",
                                  selectmode="browse")
        encabezados = (("codigo", "Código", 100, "w"),
                       ("nombre", "Descripción", 280, "w"),
                       ("cant", "Cant", 60, "center"),
                       ("precio", "Vlr. unit", 100, "e"),
                       ("subtotal", "Importe", 110, "e"))
        for col, titulo, ancho, ancla in encabezados:
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor=ancla)
        self.tabla.grid(row=2, column=0, sticky="nsew")
        barra = ttk.Scrollbar(izquierda, orient="vertical",
                              command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.grid(row=2, column=1, sticky="ns")
        self.tabla.bind("<Double-1>", lambda e: self._cambiar_cantidad())
        self.tabla.tag_configure("alterna", background=estilos.FILA_ALTERNA)

        fila_botones = ttk.Frame(izquierda, style="Tarjeta.TFrame")
        fila_botones.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for texto, accion in (("Buscar (F3)", self._buscar_nombre),
                              ("Cantidad (F2)", self._cambiar_cantidad),
                              ("Quitar línea (Supr)", self._quitar_linea),
                              ("Consultar precio (F4)", self._consultar_precio)):
            ttk.Button(fila_botones, text=texto, style="Plano.TButton",
                       command=accion).pack(side="left", padx=(0, 8))

        # ---- panel derecho: visor tipo POS + acciones
        derecha = ttk.Frame(cuerpo, style="Fondo.TFrame")
        derecha.grid(row=0, column=1, sticky="nsew")
        derecha.columnconfigure(0, weight=1)
        derecha.rowconfigure(1, weight=1)

        visor = ttk.Frame(derecha, style="Display.TFrame", padding=22)
        visor.grid(row=0, column=0, sticky="new")
        ttk.Label(visor, text="TOTAL A PAGAR",
                  style="DisplayTitulo.TLabel").pack(anchor="w")
        self.lbl_total = ttk.Label(visor, text="0", style="DisplayTotal.TLabel",
                                   anchor="e")
        self.lbl_total.pack(fill="x")
        self.lbl_detalle_totales = ttk.Label(visor, text="",
                                             style="DisplaySub.TLabel")
        self.lbl_detalle_totales.pack(anchor="w", pady=(4, 0))

        # zona de cambio: aparece al cerrar una venta, como el visor real
        self.zona_cambio = ttk.Frame(visor, style="Display.TFrame")
        self.lbl_banner = tk.Label(self.zona_cambio, text="",
                                   bg=estilos.DISPLAY_FONDO,
                                   font=(estilos.FUENTE, 15, "bold"))
        self.lbl_banner.pack(anchor="w", pady=(14, 0))
        ttk.Label(self.zona_cambio, text="CAMBIO",
                  style="DisplayTitulo.TLabel").pack(anchor="w", pady=(6, 0))
        self.lbl_cambio = ttk.Label(self.zona_cambio, text="",
                                    style="DisplayCambio.TLabel", anchor="e")
        self.lbl_cambio.pack(fill="x")
        self.lbl_venta_hecha = ttk.Label(self.zona_cambio, text="",
                                         style="DisplaySub.TLabel")
        self.lbl_venta_hecha.pack(anchor="w")

        acciones = ttk.Frame(derecha, style="Fondo.TFrame")
        acciones.grid(row=1, column=0, sticky="sew", pady=(12, 0))
        acciones.columnconfigure(0, weight=1)
        ttk.Button(acciones, text="COBRAR  (F12)", style="Exito.TButton",
                   command=self._cobrar).grid(row=0, column=0, sticky="ew",
                                              pady=(0, 8))
        ttk.Button(acciones, text="Cancelar venta  (Esc)",
                   style="Peligro.TButton",
                   command=self._cancelar).grid(row=1, column=0, sticky="ew",
                                                pady=(0, 8))
        fila_recibo = ttk.Frame(acciones, style="Fondo.TFrame")
        fila_recibo.grid(row=2, column=0, sticky="ew")
        fila_recibo.columnconfigure(0, weight=1)
        fila_recibo.columnconfigure(1, weight=1)
        ttk.Button(fila_recibo, text="Reimprimir (F6)", style="Plano.TButton",
                   command=self._reimprimir_ultima).grid(row=0, column=0,
                                                         sticky="ew",
                                                         padx=(0, 4))
        ttk.Button(fila_recibo, text="PDF última venta", style="Plano.TButton",
                   command=self._pdf_ultima).grid(row=0, column=1, sticky="ew")

        # ---- barra de estado
        self.estado = tk.Label(self, text="", anchor="w",
                               font=(estilos.FUENTE, 12, "bold"),
                               bg=estilos.FONDO, padx=26, pady=6)
        self.estado.pack(fill="x", side="bottom")
        ayuda = ("Enter Agregar («3*código» agrega 3)  ·  F2 Cantidad  ·  "
                 "Supr Quitar  ·  F3 Buscar  ·  F4 Precio  ·  "
                 "F6 Reimprimir  ·  F12 Cobrar  ·  Esc Cancelar")
        tk.Label(self, text=ayuda, anchor="w", font=(estilos.FUENTE, 10),
                 fg=estilos.GRIS, bg=estilos.FONDO, padx=26).pack(
            fill="x", side="bottom")

    def _atajos(self):
        app = self.app
        app.atajo("<F2>", lambda e: self._cambiar_cantidad())
        app.atajo("<F3>", lambda e: self._buscar_nombre())
        app.atajo("<F4>", lambda e: self._consultar_precio())
        app.atajo("<F6>", lambda e: self._reimprimir_ultima())
        app.atajo("<F12>", lambda e: self._cobrar())
        app.atajo("<Delete>", lambda e: self._quitar_linea())
        app.atajo("<Escape>", lambda e: self._cancelar())
        # La caja siempre está escuchando el lector: si el foco quedó en
        # la tabla o en un botón y llega un escaneo (o se teclea un
        # código), los caracteres se redirigen solos al campo de código.
        app.atajo("<Key>", self._captura_global)

    def _captura_global(self, evento):
        if isinstance(evento.widget, tk.Entry):
            return None
        caracter = evento.char
        if not caracter or not caracter.isprintable():
            return None
        self.entrada_codigo.focus_set()
        self.entrada_codigo.insert("end", caracter)
        return "break"

    def _actualizar_ticket(self):
        consecutivo = int(db.obtener_config("consecutivo_factura", "0")) + 1
        prefijo = "E" if self.entrenamiento else "F"
        self.lbl_ticket.configure(text=f"Ticket: {prefijo}-{consecutivo:06d}")

    # --------------------------------------------------------- carrito

    def _recuperar_diario(self):
        diario = db.leer_diario()
        if diario:
            self.items = diario["items"]
            self._estado_msg(
                "Se recuperó una venta que quedó en curso. Puede continuarla "
                "o cancelarla con Esc.", "aviso")

    def _agregar_codigo(self):
        texto = self.entrada_codigo.get().strip()
        self.entrada_codigo.delete(0, "end")
        if not texto:
            return
        cantidad = 1
        for separador in ("*", "x", "X"):
            if separador in texto:
                izquierda, _, derecha = texto.partition(separador)
                if izquierda.strip().isdigit() and derecha.strip():
                    cantidad = max(1, int(izquierda.strip()))
                    texto = derecha.strip()
                break
        producto = db.buscar_por_codigo(texto)
        if producto is None:
            self._estado_msg(
                f"El código «{texto}» no existe. Verifíquelo o busque el "
                "producto por nombre con F3.", "error")
            self.bell()
            return
        self._agregar_producto(producto, cantidad)

    def _agregar_producto(self, producto: dict, cantidad: int = 1):
        self._ocultar_cambio()
        for item in self.items:
            if item["id"] == producto["id"]:
                item["cantidad"] += cantidad
                self._estado_msg(
                    f"«{producto['nombre']}» ya estaba en la venta: la cantidad "
                    f"aumentó a {item['cantidad']}.", "info")
                break
        else:
            self.items.append({
                "id": producto["id"], "codigo": producto["codigo_barras"],
                "nombre": producto["nombre"], "precio": producto["precio"],
                "cantidad": cantidad,
            })
            self._estado_msg(
                f"{producto['nombre']} — {fmt_dinero(producto['precio'])}", "ok")
        if (db.config_activa("controlar_stock") and not self.entrenamiento
                and producto["stock"] <= 0):
            self._estado_msg(
                f"Atención: «{producto['nombre']}» aparece sin stock.", "aviso")
        self._sincronizar()

    def _linea_seleccionada(self):
        seleccion = self.tabla.selection()
        if seleccion:
            return int(seleccion[0])
        if self.items:
            return len(self.items) - 1  # por defecto, la última línea
        return None

    def _cambiar_cantidad(self):
        indice = self._linea_seleccionada()
        if indice is None:
            self._estado_msg("No hay productos en la venta.", "error")
            return
        item = self.items[indice]
        nueva = pedir_numero(self.app, "Cambiar cantidad",
                             f"Cantidad para «{item['nombre']}»:",
                             item["cantidad"])
        if nueva:
            item["cantidad"] = nueva
            self._sincronizar()
        self.entrada_codigo.focus_set()

    def _quitar_linea(self):
        indice = self._linea_seleccionada()
        if indice is None:
            return
        item = self.items.pop(indice)
        self._estado_msg(f"Se quitó «{item['nombre']}» de la venta.", "info")
        self._sincronizar()
        self.entrada_codigo.focus_set()

    def _buscar_nombre(self):
        DialogoBusqueda(self.app, self._agregar_producto)
        self.entrada_codigo.focus_set()

    def _consultar_precio(self):
        DialogoPrecio(self.app)
        self.entrada_codigo.focus_set()

    # --------------------------------------------------------- totales

    def _totales(self):
        subtotal = sum(i["precio"] * i["cantidad"] for i in self.items)
        iva = round(subtotal * self.iva_pct / 100)
        return subtotal, iva, subtotal + iva

    def _sincronizar(self):
        """Refresca tabla y visor, y persiste el diario de venta en curso."""
        self.tabla.delete(*self.tabla.get_children())
        for indice, item in enumerate(self.items):
            self.tabla.insert(
                "", "end", iid=str(indice),
                values=(item["codigo"], item["nombre"], item["cantidad"],
                        fmt_dinero(item["precio"]),
                        fmt_dinero(item["precio"] * item["cantidad"])),
                tags=("alterna",) if indice % 2 else ())
        hijos = self.tabla.get_children()
        if hijos:
            self.tabla.see(hijos[-1])  # la última línea siempre visible
        subtotal, iva, total = self._totales()
        self.lbl_total.configure(text=fmt_dinero(total))
        articulos = sum(i["cantidad"] for i in self.items)
        detalle = f"{articulos} artículo(s)"
        if self.iva_pct:
            detalle += (f"  ·  Subtotal {fmt_dinero(subtotal)}"
                        f"  ·  IVA {self.iva_pct}% {fmt_dinero(iva)}")
        self.lbl_detalle_totales.configure(text=detalle)
        self._actualizar_ticket()
        if self.items:
            db.guardar_diario(self.items)
        else:
            db.borrar_diario()

    def _ocultar_cambio(self):
        self.zona_cambio.pack_forget()

    # --------------------------------------------------------- cobro

    def _cobrar(self):
        if not self.items:
            self._estado_msg("Agregue al menos un producto antes de cobrar.",
                             "error")
            self.bell()
            return
        _, _, total = self._totales()
        DialogoCobro(self.app, total, self._registrar_pago)
        self.entrada_codigo.focus_set()

    def _registrar_pago(self, metodo: str, recibido: int,
                        codigo_autorizacion=None, cliente_nombre="",
                        cliente_nit=""):
        """Llamado por el diálogo de cobro con un pago ya validado."""
        venta = db.registrar_venta(
            usuario=self.app.usuario, items=self.items,
            iva_porcentaje=self.iva_pct, metodo_pago=metodo, recibido=recibido,
            entrenamiento=self.entrenamiento,
            controlar_stock=db.config_activa("controlar_stock"),
            codigo_autorizacion=codigo_autorizacion,
            cliente_nombre=cliente_nombre, cliente_nit=cliente_nit,
        )
        db.borrar_diario()
        self.items = []
        self.ultima_venta = venta
        self._sincronizar()
        self._estado_msg(f"Venta {venta['numero_factura']} registrada.", "ok")
        self.zona_cambio.pack(fill="x")
        self._animar_cierre(venta, 0)
        self.entrada_codigo.focus_set()

    def _animar_cierre(self, venta: dict, paso: int):
        """Deja explícito el cierre de la venta antes de mostrar el cambio,
        para que quede claro que esa transacción terminó (petición del
        usuario: hacer el cierre más dinámico y notorio)."""
        if not self.winfo_exists():
            return
        if paso < 4:
            color = estilos.DISPLAY_VERDE if paso % 2 == 0 else estilos.DISPLAY_AMBAR
            self.lbl_banner.configure(text="✓  VENTA FINALIZADA", fg=color)
            self.lbl_venta_hecha.configure(text=f"Ticket {venta['numero_factura']}")
            self.after(140, lambda: self._animar_cierre(venta, paso + 1))
            return
        self.lbl_banner.configure(text="✓  Venta finalizada",
                                  fg=estilos.DISPLAY_VERDE)
        self.lbl_cambio.configure(text=fmt_dinero(venta["cambio"]))
        detalle = (f"Venta {venta['numero_factura']}  ·  {venta['metodo_pago']}"
                  f"  ·  Recibido {fmt_dinero(venta['recibido'])}")
        self.lbl_venta_hecha.configure(text=detalle)
        if db.config_activa("imprimir_auto"):
            self.lbl_venta_hecha.configure(text=detalle + "   ·   🖨 Imprimiendo…")
            self.after(400, lambda: self._imprimir_auto(venta, detalle))

    def _imprimir_auto(self, venta: dict, detalle: str):
        if not self.winfo_exists():
            return
        try:
            recibos.imprimir(venta)
            self.lbl_venta_hecha.configure(text=detalle + "   ·   🖨 Recibo impreso")
        except OSError:
            self.lbl_venta_hecha.configure(
                text=detalle + "   ·   Sin impresora: recibo guardado")
            self._estado_msg(
                "No se pudo imprimir automáticamente; el ticket quedó en "
                "datos/tickets. Puede reimprimir con F6.", "aviso")

    def _reimprimir_ultima(self):
        if not self.ultima_venta:
            self._estado_msg("Aún no hay una venta en esta sesión de caja. "
                             "Use el Historial para reimprimir anteriores.",
                             "aviso")
            return
        try:
            recibos.imprimir(self.ultima_venta)
            self._estado_msg(f"Recibo {self.ultima_venta['numero_factura']} "
                             "enviado a la impresora.", "ok")
        except OSError:
            self._estado_msg("No se pudo imprimir. El ticket quedó guardado "
                             "en datos/tickets.", "aviso")

    def _pdf_ultima(self):
        if not self.ultima_venta:
            self._estado_msg("Aún no hay una venta en esta sesión de caja.",
                             "aviso")
            return
        sugerida = recibos.ruta_pdf_sugerida(self.ultima_venta)
        ruta = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".pdf",
            initialdir=str(sugerida.parent), initialfile=sugerida.name,
            filetypes=[("Archivo PDF", "*.pdf")])
        if ruta:
            recibos.generar_pdf(self.ultima_venta, ruta)
            self._estado_msg(f"PDF guardado: {ruta}", "ok")

    def _cancelar(self):
        if not self.items:
            self.app.mostrar_menu()
            return
        if messagebox.askyesno(
                "Cancelar venta",
                "Hay una venta en curso. ¿Seguro que desea cancelarla?\n"
                "Los productos escaneados se descartarán.", parent=self.app):
            self.items = []
            db.borrar_diario()
            self._sincronizar()
            self._ocultar_cambio()
            self._estado_msg("Venta cancelada.", "info")
            self.entrada_codigo.focus_set()

    def _estado_msg(self, mensaje: str, tipo: str = "info"):
        colores = {"ok": estilos.EXITO, "error": estilos.PELIGRO,
                   "aviso": estilos.AVISO, "info": estilos.PRIMARIO_OSCURO}
        self.estado.configure(text=mensaje, fg=colores.get(tipo, estilos.TEXTO))
        self.after(8000, lambda: self.estado.configure(text="")
                   if self.estado.winfo_exists() else None)


class DialogoCobro(tk.Toplevel):
    """Paso de cobro como en un POS real: total en grande, método de pago,
    denominaciones rápidas y cambio en vivo (plan.md §1.4)."""

    def __init__(self, padre, total: int, al_confirmar):
        super().__init__(padre)
        self.title("Cobrar")
        self.total = total
        self.al_confirmar = al_confirmar
        self.configure(bg=estilos.TARJETA, padx=26, pady=20)
        self.transient(padre)
        self.resizable(False, False)

        visor = tk.Frame(self, bg=estilos.DISPLAY_FONDO, padx=18, pady=12)
        visor.pack(fill="x")
        tk.Label(visor, text="TOTAL A PAGAR", bg=estilos.DISPLAY_FONDO,
                 fg=estilos.DISPLAY_GRIS,
                 font=(estilos.FUENTE, 11, "bold")).pack(anchor="w")
        tk.Label(visor, text=fmt_dinero(total), bg=estilos.DISPLAY_FONDO,
                 fg=estilos.DISPLAY_VERDE,
                 font=(estilos.MONO, 32, "bold")).pack(anchor="e")

        tk.Label(self, text="Facturar a (opcional):", bg=estilos.TARJETA,
                 font=(estilos.FUENTE, 10, "bold"),
                 fg=estilos.GRIS).pack(anchor="w", pady=(12, 2))
        fila_cliente = tk.Frame(self, bg=estilos.TARJETA)
        fila_cliente.pack(fill="x")
        self.campo_cliente_nombre = tk.Entry(fila_cliente,
                                             font=(estilos.FUENTE, 10),
                                             relief="solid", bd=1)
        self.campo_cliente_nombre.insert(0, "")
        self._placeholder(self.campo_cliente_nombre, "Empresa o nombre")
        self.campo_cliente_nombre.pack(side="left", expand=True, fill="x",
                                       padx=(0, 6))
        self.campo_cliente_nit = tk.Entry(fila_cliente,
                                          font=(estilos.FUENTE, 10),
                                          relief="solid", bd=1, width=14)
        self._placeholder(self.campo_cliente_nit, "NIT / CC")
        self.campo_cliente_nit.pack(side="left")

        tk.Label(self, text="Método de pago:", bg=estilos.TARJETA,
                 font=(estilos.FUENTE, 12, "bold")).pack(anchor="w",
                                                         pady=(14, 2))
        self.metodo = tk.StringVar(value="Efectivo")
        fila_metodos = tk.Frame(self, bg=estilos.TARJETA)
        fila_metodos.pack(fill="x")
        self.fila_metodos_ref = fila_metodos
        for indice, met in enumerate(METODOS, start=1):
            ttk.Radiobutton(fila_metodos, text=f"{met}  (F{indice})",
                            value=met, variable=self.metodo,
                            command=self._cambio_metodo).pack(side="left",
                                                              padx=(0, 16))
            self.bind(f"<F{indice}>",
                      lambda e, m=met: (self.metodo.set(m),
                                        self._cambio_metodo()))

        self.fila_tarjeta = tk.Frame(self, bg=estilos.TARJETA)
        self.tipo_tarjeta = tk.StringVar(value="Débito")
        for tipo in TIPOS_TARJETA:
            ttk.Radiobutton(self.fila_tarjeta, text=tipo, value=tipo,
                            variable=self.tipo_tarjeta).pack(side="left",
                                                             padx=(0, 16))

        tk.Label(self, text="Dinero recibido:", bg=estilos.TARJETA,
                 font=(estilos.FUENTE, 12, "bold")).pack(anchor="w",
                                                         pady=(12, 2))
        self.entrada = estilos.entrada_grande(self, justify="right")
        self.entrada.pack(fill="x")
        self.entrada.bind("<KeyRelease>", lambda e: self._recalcular())
        self.entrada.bind("<Return>", lambda e: self._confirmar())

        fila_rapidos = tk.Frame(self, bg=estilos.TARJETA)
        fila_rapidos.pack(fill="x", pady=(8, 0))
        self.botones_rapidos = []
        boton = ttk.Button(fila_rapidos, text="Exacto", style="Plano.TButton",
                           command=lambda: self._poner(self.total))
        boton.pack(side="left", padx=(0, 6))
        self.botones_rapidos.append(boton)
        for billete in DENOMINACIONES:
            boton = ttk.Button(fila_rapidos, text=fmt_dinero(billete),
                               style="Plano.TButton",
                               command=lambda b=billete: self._poner(b))
            boton.pack(side="left", padx=(0, 6))
            self.botones_rapidos.append(boton)

        fila_cambio = tk.Frame(self, bg=estilos.TARJETA)
        fila_cambio.pack(fill="x", pady=(14, 0))
        tk.Label(fila_cambio, text="CAMBIO:", bg=estilos.TARJETA,
                 font=(estilos.FUENTE, 13, "bold")).pack(side="left")
        self.lbl_cambio = tk.Label(fila_cambio, text="—", bg=estilos.TARJETA,
                                   fg=estilos.GRIS,
                                   font=(estilos.MONO, 22, "bold"))
        self.lbl_cambio.pack(side="right")

        self.lbl_error = tk.Label(self, text="", bg=estilos.TARJETA,
                                  fg=estilos.PELIGRO,
                                  font=(estilos.FUENTE, 11, "bold"))
        self.lbl_error.pack(anchor="w", pady=(4, 0))

        fila_final = tk.Frame(self, bg=estilos.TARJETA)
        fila_final.pack(fill="x", pady=(12, 0))
        ttk.Button(fila_final, text="CONFIRMAR  (Enter)", style="Exito.TButton",
                   command=self._confirmar).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 8))
        ttk.Button(fila_final, text="Cancelar (Esc)", style="Plano.TButton",
                   command=self.destroy).pack(side="left", expand=True,
                                              fill="x")

        self.bind("<F12>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.entrada.focus_set()
        self.grab_set()
        self.update_idletasks()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.wait_window()

    def _placeholder(self, entrada: tk.Entry, texto: str):
        entrada.insert(0, texto)
        entrada.configure(fg=estilos.GRIS)

        def _limpiar(_e):
            if entrada.get() == texto:
                entrada.delete(0, "end")
                entrada.configure(fg=estilos.TEXTO)

        def _restaurar(_e):
            if not entrada.get():
                self._placeholder(entrada, texto)

        entrada.bind("<FocusIn>", _limpiar)
        entrada.bind("<FocusOut>", _restaurar)
        entrada._placeholder_texto = texto

    def _valor_o_vacio(self, entrada: tk.Entry) -> str:
        valor = entrada.get().strip()
        return "" if valor == getattr(entrada, "_placeholder_texto", None) else valor

    def _cambio_metodo(self):
        metodo = self.metodo.get()
        efectivo = metodo == "Efectivo"
        estado = "normal" if efectivo else "disabled"
        self.entrada.configure(state=estado)
        for boton in self.botones_rapidos:
            boton.state(["!disabled"] if efectivo else ["disabled"])
        if metodo == "Tarjeta":
            self.fila_tarjeta.pack(fill="x", pady=(4, 0), after=self.fila_metodos_ref)
        else:
            self.fila_tarjeta.pack_forget()
        if not efectivo:
            self.lbl_cambio.configure(text="0", fg=estilos.EXITO)
            self.lbl_error.configure(text="")
        else:
            self._recalcular()
            self.entrada.focus_set()

    def _poner(self, monto: int):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, str(monto))
        self._recalcular()
        self.entrada.focus_set()

    def _recalcular(self):
        recibido = parse_dinero(self.entrada.get())
        if recibido is None:
            self.lbl_cambio.configure(text="—", fg=estilos.GRIS)
            return
        cambio = recibido - self.total
        if cambio < 0:
            self.lbl_cambio.configure(text=f"Faltan {fmt_dinero(-cambio)}",
                                      fg=estilos.PELIGRO)
        else:
            self.lbl_cambio.configure(text=fmt_dinero(cambio),
                                      fg=estilos.EXITO)

    def _confirmar(self):
        metodo = self.metodo.get()
        if metodo == "Efectivo":
            recibido = parse_dinero(self.entrada.get())
            if recibido is None:
                self.lbl_error.configure(text="Escriba el dinero recibido o use "
                                              "los botones de billetes.")
                self.bell()
                return
            if recibido < self.total:
                # Error común de práctica: efectivo insuficiente (plan.md §1.8)
                self.lbl_error.configure(
                    text=f"Efectivo insuficiente: faltan "
                         f"{fmt_dinero(self.total - recibido)}.")
                self.bell()
                return
            self._cerrar_con(metodo, recibido, None)
            return

        if metodo == "Tarjeta":
            terminal = DialogoTerminalTarjeta(self, self.total,
                                              self.tipo_tarjeta.get())
            if terminal.resultado and terminal.resultado[0] == "aprobado":
                self._cerrar_con(metodo, self.total, terminal.resultado[1])
            return

        # Transferencia
        qr_dialogo = DialogoQRTransferencia(self, self.total)
        if qr_dialogo.resultado and qr_dialogo.resultado[0] == "aprobado":
            self._cerrar_con(metodo, self.total, qr_dialogo.resultado[1])

    def _cerrar_con(self, metodo, recibido, codigo_autorizacion):
        self.al_confirmar(metodo, recibido, codigo_autorizacion,
                          self._valor_o_vacio(self.campo_cliente_nombre),
                          self._valor_o_vacio(self.campo_cliente_nit))
        self.destroy()


class DialogoTerminalTarjeta(tk.Toplevel):
    """Simulación de datáfono para prácticas: no hay lector de tarjetas
    real ni se captura ningún dato financiero (petición del usuario:
    permitir practicar el cobro con tarjeta sin necesitar una física).
    Aprueba automáticamente tras una breve animación de "procesando";
    puede forzarse un rechazo para practicar ese caso también."""

    def __init__(self, padre, total: int, tipo: str):
        super().__init__(padre)
        self.title("Terminal de tarjeta")
        self.resultado = None
        self.configure(bg=estilos.DISPLAY_FONDO, padx=30, pady=24)
        self.transient(padre)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        tk.Label(self, text="💳", bg=estilos.DISPLAY_FONDO,
                 font=(estilos.FUENTE, 38)).pack()
        self.lbl_estado = tk.Label(self, text=f"Acerque o inserte la tarjeta "
                                   f"({tipo})", bg=estilos.DISPLAY_FONDO,
                                   fg="white", font=(estilos.FUENTE, 13, "bold"))
        self.lbl_estado.pack(pady=(10, 4))
        tk.Label(self, text=fmt_dinero(total), bg=estilos.DISPLAY_FONDO,
                 fg=estilos.DISPLAY_VERDE,
                 font=(estilos.MONO, 24, "bold")).pack(pady=(0, 10))

        self.forzar_rechazo = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Forzar rechazo (práctica)",
                        variable=self.forzar_rechazo).pack(pady=(0, 6))

        self.lbl_detalle = tk.Label(self, text="Simulación de práctica — sin "
                                    "lector de tarjetas real.",
                                    bg=estilos.DISPLAY_FONDO,
                                    fg=estilos.DISPLAY_GRIS,
                                    font=(estilos.FUENTE, 9))
        self.lbl_detalle.pack()

        self.boton_accion = ttk.Button(self, text="Cobrar con tarjeta  (Enter)",
                                       style="Exito.TButton",
                                       command=self._iniciar)
        self.boton_accion.pack(fill="x", pady=(16, 6))
        self.boton_cancelar = ttk.Button(self, text="Cancelar (Esc)",
                                         style="Plano.TButton",
                                         command=self._cancelar)
        self.boton_cancelar.pack(fill="x")

        self.bind("<Return>", lambda e: self._iniciar())
        self.bind("<Escape>", lambda e: self._cancelar())
        self.grab_set()
        self.update_idletasks()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_set()
        self.wait_window()

    def _iniciar(self):
        self.boton_accion.state(["disabled"])
        self.unbind("<Return>")
        self._procesar(0)

    def _procesar(self, paso: int):
        if not self.winfo_exists():
            return
        puntos = "." * (1 + paso % 3)
        self.lbl_estado.configure(text=f"Procesando{puntos}", fg="white")
        if paso < 5:
            self.after(280, lambda: self._procesar(paso + 1))
            return
        if self.forzar_rechazo.get():
            self.lbl_estado.configure(text="✘ TRANSACCIÓN RECHAZADA",
                                      fg=estilos.PELIGRO)
            self.lbl_detalle.configure(text="Fondos insuficientes (simulado). "
                                       "Puede reintentar o cambiar de método.",
                                       fg=estilos.PELIGRO)
            self.boton_accion.configure(text="Reintentar (Enter)",
                                        command=self._iniciar)
            self.boton_accion.state(["!disabled"])
            self.bind("<Return>", lambda e: self._iniciar())
            self.bell()
            return
        codigo = str(secrets.randbelow(900000) + 100000)
        self.lbl_estado.configure(text="✔ TRANSACCIÓN APROBADA",
                                  fg=estilos.DISPLAY_VERDE)
        self.lbl_detalle.configure(text=f"Código de autorización: {codigo}",
                                   fg=estilos.DISPLAY_GRIS)
        self.resultado = ("aprobado", codigo)
        self.boton_accion.configure(text="Continuar (Enter)",
                                    command=self.destroy)
        self.boton_accion.state(["!disabled"])
        self.bind("<Return>", lambda e: self.destroy())
        self.after(1000, self.destroy)

    def _cancelar(self):
        self.resultado = None
        self.destroy()


class DialogoQRTransferencia(tk.Toplevel):
    """Cobro por transferencia con un código QR real hacia una pasarela
    de pago local simulada (petición del usuario): un teléfono en la
    misma red puede escanearlo y aprobar el pago desde su navegador. El
    botón "Simular pago" evita que la venta dependa de tener un
    teléfono o red disponibles (plan.md: ninguna función esencial puede
    depender de un servicio externo)."""

    def __init__(self, padre, total: int):
        super().__init__(padre)
        self.title("Cobro por transferencia")
        self.resultado = None
        self.configure(bg=estilos.TARJETA, padx=22, pady=18)
        self.transient(padre)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.pasarela = pasarela.Pasarela(
            negocio=db.obtener_config("nombre_negocio", "SISTEMA DE CAJA"),
            monto_texto=fmt_dinero(total))

        tk.Label(self, text="Transferencia bancaria",
                 font=(estilos.FUENTE, 14, "bold"),
                 bg=estilos.TARJETA).pack(anchor="w")
        tk.Label(self, text=fmt_dinero(total),
                 font=(estilos.MONO, 18, "bold"), fg=estilos.PRIMARIO_OSCURO,
                 bg=estilos.TARJETA).pack(anchor="w", pady=(0, 10))

        try:
            matriz = qr.generar_matriz(self.pasarela.url)
            self._dibujar_qr(matriz)
        except Exception:
            tk.Label(self, text="No se pudo generar el código QR.\n"
                     "Use «Simular pago» para continuar.",
                     bg=estilos.TARJETA, fg=estilos.PELIGRO,
                     justify="left").pack(pady=10)
            log.exception("Fallo al generar el QR de transferencia")

        tk.Label(self, text="Escanee con la cámara del teléfono (misma red "
                            "Wi-Fi) o escriba la dirección manualmente:",
                 bg=estilos.TARJETA, font=(estilos.FUENTE, 9),
                 fg=estilos.GRIS, wraplength=280,
                 justify="left").pack(anchor="w", pady=(8, 2))
        entrada_url = tk.Entry(self, font=(estilos.MONO, 9), relief="flat",
                               bg="#f1f5f9", justify="center")
        entrada_url.insert(0, self.pasarela.url)
        entrada_url.configure(state="readonly")
        entrada_url.pack(fill="x", pady=(0, 4))

        if self.pasarela.ip_es_local():
            tk.Label(self, text="No se detectó una red local: un teléfono no "
                     "podrá alcanzar esta dirección. Use «Simular pago».",
                     bg=estilos.TARJETA, fg=estilos.AVISO,
                     font=(estilos.FUENTE, 8), wraplength=280,
                     justify="left").pack(anchor="w", pady=(0, 4))

        self.lbl_estado = tk.Label(self, text="⏳ Esperando confirmación…",
                                   font=(estilos.FUENTE, 12, "bold"),
                                   fg=estilos.AVISO, bg=estilos.TARJETA)
        self.lbl_estado.pack(pady=(6, 10))

        fila = tk.Frame(self, bg=estilos.TARJETA)
        fila.pack(fill="x")
        ttk.Button(fila, text="Simular pago aprobado", style="Exito.TButton",
                   command=lambda: self.pasarela.forzar(True)).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(fila, text="Simular rechazo", style="Plano.TButton",
                   command=lambda: self.pasarela.forzar(False)).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))
        fila.columnconfigure(0, weight=1)
        fila.columnconfigure(1, weight=1)
        ttk.Button(self, text="Cancelar (Esc)", style="Peligro.TButton",
                   command=self._cancelar).pack(fill="x", pady=(8, 0))

        self.bind("<Escape>", lambda e: self._cancelar())
        self.grab_set()
        self.update_idletasks()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._sondear()
        self.wait_window()

    def _dibujar_qr(self, matriz):
        n = len(matriz)
        escala = max(4, 216 // n)
        lado = n * escala
        lienzo = tk.Canvas(self, width=lado, height=lado, bg="white",
                           highlightthickness=0)
        lienzo.pack(pady=(0, 8))
        for fila in range(n):
            for col in range(n):
                if matriz[fila][col]:
                    x0, y0 = col * escala, fila * escala
                    lienzo.create_rectangle(x0, y0, x0 + escala, y0 + escala,
                                            fill="black", width=0)

    def _sondear(self):
        if not self.winfo_exists():
            return
        estado = self.pasarela.estado()
        if estado == "aprobado":
            codigo = secrets.token_hex(3).upper()
            self.resultado = ("aprobado", codigo)
            self.lbl_estado.configure(text="✔ Pago confirmado", fg=estilos.EXITO)
            self.after(500, self.destroy)
            return
        if estado == "rechazado":
            self.lbl_estado.configure(text="✘ Pago rechazado",
                                      fg=estilos.PELIGRO)
            self.after(1500, self._reiniciar_espera)
            return
        self.after(400, self._sondear)

    def _reiniciar_espera(self):
        if not self.winfo_exists():
            return
        self.pasarela.reiniciar()
        self.lbl_estado.configure(text="⏳ Esperando confirmación…",
                                  fg=estilos.AVISO)
        self._sondear()

    def _cancelar(self):
        self.resultado = None
        self.destroy()

    def destroy(self):
        try:
            self.pasarela.detener()
        except Exception:
            log.exception("Error al detener la pasarela al cerrar el diálogo")
        super().destroy()


class DialogoPrecio(tk.Toplevel):
    """Consulta de precio sin agregar a la venta, como el verificador
    de precios de un supermercado."""

    def __init__(self, padre):
        super().__init__(padre)
        self.title("Consultar precio")
        self.configure(bg=estilos.TARJETA, padx=24, pady=18)
        self.transient(padre)
        self.resizable(False, False)

        tk.Label(self, text="Escanee o escriba el código:",
                 font=(estilos.FUENTE, 12, "bold"),
                 bg=estilos.TARJETA).pack(anchor="w")
        self.entrada = estilos.entrada_grande(self, width=24)
        self.entrada.pack(pady=(6, 10))
        self.entrada.bind("<Return>", lambda e: self._consultar())

        self.resultado = tk.Label(self, text="", bg=estilos.TARJETA,
                                  font=(estilos.FUENTE, 14, "bold"),
                                  fg=estilos.PRIMARIO_OSCURO, justify="left")
        self.resultado.pack(anchor="w", pady=(0, 8))

        ttk.Button(self, text="Cerrar (Esc)", style="Plano.TButton",
                   command=self.destroy).pack(fill="x")
        self.bind("<Escape>", lambda e: self.destroy())
        self.entrada.focus_set()
        self.grab_set()
        self.wait_window()

    def _consultar(self):
        codigo = self.entrada.get().strip()
        self.entrada.delete(0, "end")
        if not codigo:
            # Los lectores suelen enviar un terminador doble (Enter+salto):
            # el segundo llega con el campo ya vacío y no debe borrar el
            # resultado recién mostrado.
            return
        producto = db.buscar_por_codigo(codigo)
        if producto is None:
            self.resultado.configure(text=f"El código «{codigo}» no existe.",
                                     fg=estilos.PELIGRO)
            self.bell()
            return
        texto = f"{producto['nombre']}\nPrecio: {fmt_dinero(producto['precio'])}"
        if db.config_activa("controlar_stock"):
            texto += f"   ·   Stock: {producto['stock']}"
        self.resultado.configure(text=texto, fg=estilos.PRIMARIO_OSCURO)


class DialogoBusqueda(tk.Toplevel):
    """Búsqueda de producto por nombre con resultados en vivo (plan.md §1.2)."""

    def __init__(self, padre, al_elegir):
        super().__init__(padre)
        self.title("Buscar producto")
        self.al_elegir = al_elegir
        self.configure(bg=estilos.TARJETA, padx=20, pady=16)
        self.transient(padre)
        self.geometry("560x460")

        tk.Label(self, text="Escriba parte del nombre o la categoría:",
                 font=(estilos.FUENTE, 12, "bold"), bg=estilos.TARJETA).pack(anchor="w")
        self.entrada = estilos.entrada_grande(self)
        self.entrada.pack(fill="x", pady=8)
        self.entrada.bind("<KeyRelease>", lambda e: self._refrescar())
        self.entrada.bind("<Return>", lambda e: self._elegir())
        self.entrada.bind("<Down>", lambda e: self._foco_lista())

        self.lista = ttk.Treeview(self, columns=("nombre", "precio", "codigo"),
                                  show="headings", selectmode="browse")
        for col, titulo, ancho, ancla in (("nombre", "Producto", 260, "w"),
                                          ("precio", "Precio", 100, "e"),
                                          ("codigo", "Código", 120, "w")):
            self.lista.heading(col, text=titulo)
            self.lista.column(col, width=ancho, anchor=ancla)
        self.lista.pack(fill="both", expand=True, pady=(4, 8))
        self.lista.bind("<Double-1>", lambda e: self._elegir())
        self.lista.bind("<Return>", lambda e: self._elegir())

        ttk.Button(self, text="Agregar a la venta (Enter)", style="Exito.TButton",
                   command=self._elegir).pack(fill="x")
        self.bind("<Escape>", lambda e: self.destroy())

        self._refrescar()
        self.entrada.focus_set()
        self.grab_set()
        self.wait_window()

    def _refrescar(self):
        self.lista.delete(*self.lista.get_children())
        self._resultados = db.buscar_por_nombre(self.entrada.get())
        for producto in self._resultados:
            self.lista.insert("", "end", iid=str(producto["id"]),
                              values=(producto["nombre"],
                                      fmt_dinero(producto["precio"]),
                                      producto["codigo_barras"]))
        hijos = self.lista.get_children()
        if hijos:
            self.lista.selection_set(hijos[0])

    def _foco_lista(self):
        hijos = self.lista.get_children()
        if hijos:
            self.lista.focus_set()
            self.lista.focus(hijos[0])

    def _elegir(self):
        seleccion = self.lista.selection()
        if not seleccion:
            return
        id_producto = int(seleccion[0])
        producto = next((p for p in self._resultados if p["id"] == id_producto),
                        None)
        if producto:
            self.al_elegir(producto)
            self.destroy()
