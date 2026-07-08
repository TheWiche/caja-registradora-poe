"""Gestión de productos (plan.md §1.2). Solo el administrador edita;
el cajero puede consultar y buscar (plan.md §4 seguridad).

Teclas:  Enter en buscador → lista · F5 Nuevo · F6 Guardar ·
         F8 Eliminar · Esc Menú
"""

import tkinter as tk
from tkinter import ttk, messagebox

from .. import db
from ..util import fmt_dinero, parse_dinero
from . import estilos
from .estilos import BarraSuperior


class PantallaProductos(ttk.Frame):
    def __init__(self, maestro, app):
        super().__init__(maestro, style="Fondo.TFrame")
        self.app = app
        self.es_admin = app.usuario["rol"] == "administrador"
        self.id_editando = None

        BarraSuperior(self, app, "Productos", volver=True)
        app.atajo("<Escape>", lambda e: app.mostrar_menu())
        if self.es_admin:
            app.atajo("<F5>", lambda e: self._limpiar())
            app.atajo("<F6>", lambda e: self._guardar())
            app.atajo("<F8>", lambda e: self._eliminar())

        cuerpo = ttk.Frame(self, style="Fondo.TFrame", padding=(24, 14, 24, 20))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3)
        if self.es_admin:
            cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        # ---- lista con búsqueda en vivo
        panel_lista = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=16)
        panel_lista.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel_lista.rowconfigure(2, weight=1)
        panel_lista.columnconfigure(0, weight=1)

        ttk.Label(panel_lista, text="Buscar por código, nombre o categoría:",
                  style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        self.buscador = estilos.entrada_grande(panel_lista)
        self.buscador.grid(row=1, column=0, sticky="ew", pady=(6, 10))
        self.buscador.bind("<KeyRelease>", lambda e: self._refrescar())
        self.buscador.bind("<Return>", lambda e: self._foco_tabla())
        self.buscador.bind("<Down>", lambda e: self._foco_tabla())

        columnas = ("codigo", "nombre", "precio", "categoria", "stock")
        self.tabla = ttk.Treeview(panel_lista, columns=columnas, show="headings",
                                  selectmode="browse")
        for col, titulo, ancho, ancla in (
                ("codigo", "Código", 110, "w"), ("nombre", "Nombre", 240, "w"),
                ("precio", "Precio", 100, "e"), ("categoria", "Categoría", 120, "w"),
                ("stock", "Stock", 70, "center")):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor=ancla)
        self.tabla.grid(row=2, column=0, sticky="nsew")
        barra = ttk.Scrollbar(panel_lista, orient="vertical",
                              command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.grid(row=2, column=1, sticky="ns")
        if self.es_admin:
            self.tabla.bind("<<TreeviewSelect>>", lambda e: self._cargar_seleccion())

        # ---- formulario (solo administrador)
        if self.es_admin:
            self._construir_formulario(cuerpo)
        else:
            ttk.Label(cuerpo, text="Consulta solamente: la edición de productos\n"
                      "está reservada al administrador.",
                      style="Sub.TLabel").grid(row=1, column=0, sticky="w",
                                               pady=(10, 0))
        self._refrescar()
        self.buscador.focus_set()

    def _construir_formulario(self, cuerpo):
        formulario = ttk.Frame(cuerpo, style="Tarjeta.TFrame", padding=16)
        formulario.grid(row=0, column=1, sticky="nsew")
        formulario.columnconfigure(0, weight=1)

        self.titulo_form = ttk.Label(formulario, text="Nuevo producto",
                                     style="TituloTarjeta.TLabel")
        self.titulo_form.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.campos = {}
        etiquetas = (("codigo", "Código de barras"), ("nombre", "Nombre"),
                     ("precio", "Precio"), ("categoria", "Categoría"),
                     ("stock", "Stock"))
        for fila, (clave, texto) in enumerate(etiquetas, start=1):
            ttk.Label(formulario, text=texto + ":", style="Campo.TLabel").grid(
                row=fila * 2 - 1, column=0, sticky="w")
            entrada = tk.Entry(formulario, font=(estilos.FUENTE, 13),
                               relief="solid", bd=1)
            entrada.grid(row=fila * 2, column=0, sticky="ew", pady=(2, 8))
            self.campos[clave] = entrada

        ttk.Button(formulario, text="Guardar  (F6)", style="Exito.TButton",
                   command=self._guardar).grid(row=11, column=0, sticky="ew",
                                               pady=(8, 6))
        ttk.Button(formulario, text="Nuevo producto  (F5)",
                   style="Plano.TButton",
                   command=self._limpiar).grid(row=12, column=0, sticky="ew",
                                               pady=(0, 6))
        ttk.Button(formulario, text="Eliminar seleccionado  (F8)",
                   style="Peligro.TButton",
                   command=self._eliminar).grid(row=13, column=0, sticky="ew")

    def _foco_tabla(self):
        hijos = self.tabla.get_children()
        if hijos:
            self.tabla.focus_set()
            self.tabla.selection_set(hijos[0])
            self.tabla.focus(hijos[0])

    def _refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for producto in db.listar_productos(self.buscador.get()):
            self.tabla.insert("", "end", iid=str(producto["id"]),
                              values=(producto["codigo_barras"], producto["nombre"],
                                      fmt_dinero(producto["precio"]),
                                      producto["categoria"], producto["stock"]))

    def _cargar_seleccion(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        producto = next((p for p in db.listar_productos(self.buscador.get())
                         if p["id"] == int(seleccion[0])), None)
        if not producto:
            return
        self.id_editando = producto["id"]
        self.titulo_form.configure(text="Editar producto")
        valores = {"codigo": producto["codigo_barras"], "nombre": producto["nombre"],
                   "precio": producto["precio"], "categoria": producto["categoria"],
                   "stock": producto["stock"]}
        for clave, entrada in self.campos.items():
            entrada.delete(0, "end")
            entrada.insert(0, str(valores[clave]))

    def _limpiar(self):
        self.id_editando = None
        self.titulo_form.configure(text="Nuevo producto")
        for entrada in self.campos.values():
            entrada.delete(0, "end")
        seleccion = self.tabla.selection()
        if seleccion:
            self.tabla.selection_remove(seleccion)
        self.campos["codigo"].focus_set()

    def _leer_formulario(self):
        codigo = self.campos["codigo"].get().strip()
        nombre = self.campos["nombre"].get().strip()
        precio = parse_dinero(self.campos["precio"].get())
        categoria = self.campos["categoria"].get().strip() or "General"
        stock_texto = self.campos["stock"].get().strip() or "0"
        if not codigo or not nombre:
            raise ValueError("El código y el nombre son obligatorios.")
        if precio is None:
            raise ValueError("El precio debe ser un número (ejemplo: 4500).")
        if not stock_texto.lstrip("-").isdigit():
            raise ValueError("El stock debe ser un número entero.")
        return codigo, nombre, precio, categoria, int(stock_texto)

    def _guardar(self):
        try:
            codigo, nombre, precio, categoria, stock = self._leer_formulario()
            if self.id_editando:
                db.actualizar_producto(self.id_editando, codigo, nombre, precio,
                                       categoria, stock)
                mensaje = f"Producto «{nombre}» actualizado."
            else:
                db.crear_producto(codigo, nombre, precio, categoria, stock)
                mensaje = f"Producto «{nombre}» creado."
        except ValueError as error:
            messagebox.showwarning("Productos", str(error), parent=self.app)
            return
        self._refrescar()
        self._limpiar()
        messagebox.showinfo("Productos", mensaje, parent=self.app)

    def _eliminar(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Productos", "Seleccione primero un producto "
                                   "en la lista.", parent=self.app)
            return
        valores = self.tabla.item(seleccion[0], "values")
        if messagebox.askyesno(
                "Eliminar producto",
                f"¿Eliminar «{valores[1]}»?\n\nLas ventas ya registradas "
                "conservarán su información.", parent=self.app):
            db.eliminar_producto(int(seleccion[0]))
            self._refrescar()
            self._limpiar()
