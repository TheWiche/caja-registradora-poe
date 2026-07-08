"""Pasarela de pago educativa para practicar transferencias (plan.md §1.4).

Corre un servidor HTTP efímero (librería estándar, sin dependencias)
SOLO mientras el diálogo de cobro por transferencia está abierto, y se
apaga al cerrarlo — nunca queda como proceso de fondo (plan.md §6.2).
Un teléfono en la misma red Wi-Fi/LAN puede escanear el código QR y
"aprobar" el pago desde su navegador; la caja detecta la confirmación
sola. Si no hay teléfono o red disponible, el propio diálogo de cobro
ofrece "Simular pago" para que la venta nunca quede bloqueada
(plan.md: ninguna función esencial depende de un servicio externo).

Es una SIMULACIÓN para prácticas: no se conecta a ningún banco ni
procesador de pagos real, no recibe ni guarda datos financieros, y toda
la comunicación permanece dentro de la red local del salón de clase.
La página deja explícito en todo momento que es material educativo.
"""

import http.server
import logging
import secrets
import socket
import threading

log = logging.getLogger("caja")

_ESTADOS = {}
_bloqueo = threading.Lock()


def _ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no envía datos: solo elige la ruta
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


_ESTILO = """
body{font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;
     margin:0;padding:0;display:flex;min-height:100vh;align-items:center;
     justify-content:center}
.tarjeta{background:#1e293b;border-radius:16px;padding:32px;max-width:380px;
         width:90%;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.aviso{background:#c2410c;color:white;font-weight:bold;font-size:12px;
       border-radius:8px;padding:6px 10px;margin-bottom:16px;
       letter-spacing:.5px}
.monto{font-family:Consolas,monospace;font-size:34px;font-weight:bold;
       color:#4ade80;margin:8px 0 4px}
.negocio{color:#94a3b8;font-size:14px;margin-bottom:18px}
.boton{display:block;width:100%;padding:14px;margin-top:12px;border:0;
       border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer}
.aprobar{background:#15803d;color:white}
.rechazar{background:transparent;color:#94a3b8;border:1px solid #475569}
.resultado{font-size:22px;font-weight:bold;margin:18px 0}
"""

_PAGINA_PAGO = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pasarela educativa</title><style>{estilo}</style></head><body>
<div class="tarjeta">
  <div class="aviso">SIMULACIÓN EDUCATIVA — SIN DINERO REAL</div>
  <div class="negocio">{negocio}</div>
  <div>Total a transferir</div>
  <div class="monto">$ {monto}</div>
  <form method="POST" action="/p/{token}/aprobar">
    <button class="boton aprobar" type="submit">Aprobar pago</button>
  </form>
  <form method="POST" action="/p/{token}/rechazar">
    <button class="boton rechazar" type="submit">Rechazar</button>
  </form>
</div></body></html>"""

_PAGINA_APROBADA = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pago aprobado</title><style>{estilo}</style></head><body>
<div class="tarjeta">
  <div class="aviso">SIMULACIÓN EDUCATIVA — SIN DINERO REAL</div>
  <div class="resultado" style="color:#4ade80">✔ Pago aprobado</div>
  <div class="negocio">Puede cerrar esta ventana y volver a la caja.</div>
</div></body></html>"""

_PAGINA_RECHAZADA = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pago rechazado</title><style>{estilo}</style></head><body>
<div class="tarjeta">
  <div class="aviso">SIMULACIÓN EDUCATIVA — SIN DINERO REAL</div>
  <div class="resultado" style="color:#f87171">✘ Pago rechazado</div>
  <div class="negocio">Puede cerrar esta ventana y volver a la caja.</div>
</div></body></html>"""

_PAGINA_EXPIRADA = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Enlace no válido</title><style>{estilo}</style></head><body>
<div class="tarjeta">
  <div class="aviso">SIMULACIÓN EDUCATIVA</div>
  <div class="resultado">Este enlace ya no está activo.</div>
</div></body></html>"""


class _Manejador(http.server.BaseHTTPRequestHandler):
    negocio = "SISTEMA DE CAJA"
    monto_texto = "0"
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        pass  # sin ruido de acceso en la consola (plan.md §6: nada superfluo)

    def _html(self, cuerpo: str, estado=200):
        datos = cuerpo.encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        partes = self.path.strip("/").split("/")
        if len(partes) == 2 and partes[0] == "p":
            self._pagina_pago(partes[1])
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        partes = self.path.strip("/").split("/")
        if len(partes) == 3 and partes[0] == "p" and partes[2] in (
                "aprobar", "rechazar"):
            token = partes[1]
            aprobado = partes[2] == "aprobar"
            with _bloqueo:
                if token in _ESTADOS:
                    _ESTADOS[token] = "aprobado" if aprobado else "rechazado"
            self._html((_PAGINA_APROBADA if aprobado
                       else _PAGINA_RECHAZADA).format(estilo=_ESTILO))
        else:
            self.send_response(404)
            self.end_headers()

    def _pagina_pago(self, token):
        with _bloqueo:
            existe = token in _ESTADOS
        if not existe:
            self._html(_PAGINA_EXPIRADA.format(estilo=_ESTILO), 404)
            return
        self._html(_PAGINA_PAGO.format(
            estilo=_ESTILO, negocio=self.negocio, monto=self.monto_texto,
            token=token))


class Pasarela:
    """Servidor efímero de una sola transacción de práctica."""

    def __init__(self, negocio: str, monto_texto: str):
        self.token = secrets.token_hex(3)
        with _bloqueo:
            _ESTADOS[self.token] = "pendiente"
        manejador = type("_ManejadorConDatos", (_Manejador,), {
            "negocio": negocio, "monto_texto": monto_texto,
        })
        self.httpd = http.server.ThreadingHTTPServer(("0.0.0.0", 0), manejador)
        self.puerto = self.httpd.server_address[1]
        self._detenida = False
        self.hilo = threading.Thread(target=self.httpd.serve_forever,
                                     daemon=True)
        self.hilo.start()
        log.info("Pasarela de práctica iniciada en el puerto %s (token %s)",
                 self.puerto, self.token)

    @property
    def url(self) -> str:
        return f"http://{_ip_local()}:{self.puerto}/p/{self.token}"

    def ip_es_local(self) -> bool:
        return _ip_local().startswith("127.")

    def estado(self) -> str:
        with _bloqueo:
            return _ESTADOS.get(self.token, "expirado")

    def forzar(self, aprobado: bool):
        """Botón 'Simular pago' del cajero cuando no hay teléfono a mano."""
        with _bloqueo:
            if self.token in _ESTADOS:
                _ESTADOS[self.token] = "aprobado" if aprobado else "rechazado"

    def reiniciar(self):
        with _bloqueo:
            if self.token in _ESTADOS:
                _ESTADOS[self.token] = "pendiente"

    def detener(self):
        if self._detenida:
            return
        self._detenida = True
        with _bloqueo:
            _ESTADOS.pop(self.token, None)
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except OSError:
            log.exception("Error al detener la pasarela de práctica")
        log.info("Pasarela de práctica detenida (token %s)", self.token)
