# Sistema de Caja Registradora Didáctica

Herramienta de formación para cursos de **Atención al Cliente y Manejo de
Caja Registradora**. Simula el flujo real de una caja de mostrador:
escanear → cobrar → dar cambio → entregar recibo.

Construido 100 % con la librería estándar de Python (Tkinter + SQLite):
**cero dependencias, cero Internet, base de datos local**. Ver el alcance
completo y las exclusiones de diseño en [plan.md](plan.md).

---

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior (probado con 3.12) — [python.org](https://www.python.org/downloads/),
  marcando *"Add python.exe to PATH"* al instalar.
- Opcional: lector de código de barras USB (los que funcionan como teclado
  sirven todos, sin configurar nada).
- Opcional: impresora (térmica o normal) instalada como predeterminada.

## Cómo iniciar

Doble clic en **`iniciar.bat`**, o desde una terminal en esta carpeta:

```
python -m caja.main
```

### Usuarios iniciales

| Usuario  | Contraseña  | Rol           |
|----------|-------------|---------------|
| `admin`  | `admin123`  | Administrador |
| `cajero` | `cajero123` | Cajero        |

> Cambie la contraseña del administrador en **Configuración → Cambiar mi
> contraseña** antes de usar el sistema con estudiantes.

El sistema viene con **20 productos de ejemplo** (códigos `7701001` a
`7701020`) listos para practicar.

---

## Flujo de una venta (solo teclado, como en un POS real)

1. En el menú, **F1** abre *Nueva venta*.
2. Escanee el código o escríbalo y pulse **Enter**. Para varias unidades:
   `3*7701001` agrega 3 de una vez.
3. **F2** cambia la cantidad de la línea seleccionada, **Supr** la quita,
   **F3** busca por nombre, **F4** consulta un precio sin agregarlo.
4. **F12** abre el **cobro**: opcionalmente anote "Facturar a" (empresa y
   NIT/CC), elija método (F1 Efectivo / F2 Tarjeta / F3 Transferencia) y
   confirme. En efectivo, escriba lo recibido o toque el billete que
   entregó el cliente (10.000 / 20.000 / 50.000 / 100.000 / Exacto); el
   cambio se calcula en vivo.
5. Al confirmar, el visor muestra **"✓ VENTA FINALIZADA"** y luego el
   **CAMBIO a entregar**; el cursor vuelve solo al campo de código para
   atender al siguiente cliente. **F6** reimprime la última venta.
6. **Esc** cancela la venta en cualquier momento (pide confirmación).

### Métodos de pago simulados (para practicar sin hardware real)

- **Tarjeta**: abre un **datáfono simulado** — sin lector ni datos de
  tarjeta reales. Muestra "Procesando…" y aprueba con un código de
  autorización de 6 dígitos. La casilla **"Forzar rechazo"** permite
  practicar una transacción rechazada.
- **Transferencia**: genera un **código QR real** (generador propio en
  `caja/qr.py`, sin librerías externas) hacia una **pasarela de pago
  educativa** que corre en la misma máquina (`caja/pasarela.py`). Un
  teléfono conectado a la misma red Wi‑Fi puede escanearlo y aprobar o
  rechazar el pago desde su navegador; la caja detecta la confirmación
  sola. Si no hay teléfono o red disponible, los botones **"Simular pago
  aprobado / rechazo"** dejan continuar la venta sin bloquearla. El
  servidor solo existe mientras el diálogo está abierto — no queda como
  proceso de fondo — y la página siempre indica **"SIMULACIÓN EDUCATIVA
  — SIN DINERO REAL"**; no se conecta a ningún banco ni pasarela real.
  > La primera vez que un teléfono intente conectarse, Windows puede
  > pedir permiso de **Firewall** para Python en redes privadas: hay que
  > permitirlo para que el QR funcione desde otro dispositivo.

## Todo se opera con el teclado (el ratón es opcional)

**Menú:** `F1` Nueva venta · `F2` Productos · `F3` Historial ·
`F4` Reportes (admin) · `F5` Configuración (admin) · `F6` Usuarios (admin)
· `F8` Cerrar sesión

**Historial:** `F4`/`↓` sobre una fecha abre el **mini calendario**
(flechas mueven el día, RePág/AvPág el mes, Inicio = hoy, Enter elige) ·
`F5` Buscar · `F6` Reimprimir · `F7` PDF · `F8` incluir/excluir
entrenamiento · `↓` desde el nº de factura salta a la lista.

**Productos:** Enter/`↓` en el buscador salta a la lista · `F5` Nuevo ·
`F6` Guardar · `F8` Eliminar.

**Usuarios (admin):** `F5` Nuevo perfil · `F6` Guardar · `F8` Activar/
Desactivar. El administrador crea cajeros y otros administradores,
restablece contraseñas y desactiva perfiles (nunca se borran: las ventas
conservan su cajero). Siempre debe quedar al menos un administrador activo.

**Reportes:** `F1` Hoy · `F2` Últimos 7 días · `F3` Este mes · `F4` Todo.

**Configuración:** `F6` Guardar.

`Esc` vuelve al menú desde cualquier pantalla (en Venta, cancela la venta).

---

## Funciones para el curso

- **Modo entrenamiento** (Configuración): las ventas se numeran `E-…`,
  no descuentan inventario y no aparecen en los reportes.
- **Errores comunes simulables**: código inexistente, efectivo
  insuficiente y producto duplicado muestran mensajes didácticos claros
  sin interrumpir la venta.
- **Impresión automática** (Configuración): imprime el ticket al cerrar
  cada venta, como una caja real con impresora térmica.
- **Reinicio entre clases** (Configuración → Reiniciar datos): borra
  ventas y sesiones, restaura los productos de ejemplo y deja un respaldo
  previo. Hay que escribir `REINICIAR` para confirmar.

## Robustez (qué pasa si algo sale mal)

- **¿Se fue la luz a mitad de una venta?** El carrito se guarda en disco
  tras cada cambio; al volver a entrar, la venta se recupera sola.
- **¿Falló el lector?** Escriba el código a mano: es el mismo campo.
- **¿No hay impresora?** El recibo queda siempre como archivo en
  `datos/tickets/` y puede guardarse como PDF.
- **¿Un error inesperado?** La aplicación no se cierra: muestra un aviso
  y registra el detalle en `datos/eventos.log`.
- **Respaldos**: se crea uno automático en cada arranque (se conservan
  los últimos 15) en `datos/respaldos/`; también manual desde Configuración.

## Estructura

```
plan.md            Alcance, requisitos y exclusiones (documento rector)
iniciar.bat        Arranque con doble clic
caja/
  main.py          Punto de entrada, manejo global de errores
  db.py            SQLite local: esquema, ventas atómicas, respaldos
  seguridad.py     Contraseñas con PBKDF2 (nunca texto plano)
  recibos.py       Recibo de texto, PDF sin librerías, impresión
  qr.py            Generador de códigos QR en Python puro (sin librerías)
  pasarela.py      Servidor HTTP efímero: pasarela de pago educativa
  util.py          Formato de dinero y fechas
  ui/              Pantallas Tkinter (login, menú, venta, productos,
                   historial, reportes, configuración)
datos/             Se crea al primer arranque: caja.db, tickets/,
                   respaldos/, eventos.log
```
