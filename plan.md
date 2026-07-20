# Plan Maestro — Sistema de Caja Registradora Didáctico

> **Propósito del documento:** Este archivo es la fuente única de verdad del proyecto. Cualquier decisión de diseño, alcance o implementación futura debe verificarse contra este documento antes de ejecutarse. Si una funcionalidad nueva no encaja aquí, **no se agrega** sin antes actualizar este plan y justificar por qué no rompe el principio fundamental (ver sección 0).

---

## 0. Objetivo y principio fundamental

**Objetivo:** Construir una herramienta didáctica para un curso de Atención al Cliente y Manejo de Caja Registradora. Debe simular con fidelidad el flujo real de una caja registradora comercial, sin la complejidad de un sistema comercial completo.

**Principio fundamental (no negociable):**
> Toda funcionalidad que no contribuya directamente al proceso de venta debe excluirse del sistema. El software debe garantizar un flujo de atención **continuo, rápido y estable**, priorizando: lectura de código de barras → registro de productos → cálculo del total → procesamiento del pago → devolución del cambio.

Cualquier feature que se proponga a futuro debe pasar este filtro:
1. ¿Contribuye directamente al ciclo de venta o a la enseñanza del mismo?
2. ¿Puede fallar sin bloquear una venta en curso?
3. ¿Puede implementarse sin dependencias externas ni conexión a Internet?
4. ¿Añade pasos, clics o pantallas al flujo principal de cobro?

Si la respuesta a (4) es "sí" sin que (1) lo justifique claramente, se rechaza o se relega a configuración opcional/oculta.

---

## 1. Alcance funcional

### 1.1 Inicio de sesión
- Usuario + contraseña.
- Roles: **Administrador** y **Cajero**.
- Registro de fecha/hora de ingreso (para trazabilidad, no para telemetría externa).
- Recuperación automática de la última sesión activa si el sistema se cerró de forma inesperada.

### 1.2 Gestión de productos
- CRUD completo (crear, editar, eliminar).
- Búsqueda por código de barras y por nombre.
- Campos: código de barras, nombre, precio, categoría, stock (opcional, solo para prácticas).
- Solo el **Administrador** puede modificar productos (crear/editar/eliminar).
- Generación de código de barras: al crear un producto, un botón "Generar" sugiere un código EAN-13 nuevo y único (uso interno). Cualquier producto (nuevo o de ejemplo) puede visualizarse como código de barras real, descargarse en PDF o imprimirse — individual o en una hoja de varias etiquetas para pegar en productos físicos de práctica (ver decisión abajo).

> **Decisión (20/07/2026):** códigos de barras reales, no decorativos. Los códigos generados por el sistema son **EAN-13 auténticos** (13 dígitos, dígito verificador real, prefijo 20-29 — reservado de verdad por el estándar GS1 para uso interno de tienda/sin marca); cualquier código sin forma de EAN-13 válido (como los 20 productos de ejemplo, de 7 dígitos) se renderiza en **Code 39**, sin necesitar dígito verificador. Un EAN-13 guardado con el 13º dígito incorrecto **no se corrige** al dibujarlo: cae a Code 39, porque el código impreso debe decodificar exactamente al mismo texto guardado en la base de datos (si no, escanear la etiqueta buscaría un producto distinto). Verificado con un decodificador real (pyzbar/zbar, instalado *solo* durante el desarrollo, nunca como dependencia): 20/20 códigos de ejemplo + 10 EAN-13 generados al azar + 6 casos límite (verificador incorrecto, alfanumérico, carácter inválido) decodificaron correctamente en la primera corrida. Misma disciplina que con el generador de QR (caja/qr.py): una autoprueba de autoconsistencia matemática no basta, hace falta un decodificador independiente.

### 1.3 Venta en caja (pantalla principal)
- Entrada de código de barras vía lector USB (emula teclado) **o** digitación manual — deben ser 100% intercambiables y transparentes para el flujo.
- Al leer/ingresar código: mostrar nombre, precio unitario, cantidad, subtotal.
- Permitir modificar cantidad y eliminar ítems de la venta en curso.
- Soportar múltiples productos por venta.
- Mostrar en tiempo real: subtotal, IVA (opcional/configurable), total.
- Todo el ciclo debe poder completarse **solo con teclado + lector de código de barras** (sin depender del mouse).

### 1.4 Cobro
- Ingreso de dinero recibido.
- Cálculo automático e inmediato de cambio.
- Métodos de pago: efectivo, tarjeta, transferencia. Tarjeta y transferencia son **simulaciones de práctica**, no integración con bancos ni pasarelas reales:
  - **Tarjeta**: datáfono simulado (sin lector físico ni datos de tarjeta), con animación de "procesando", código de autorización de 6 dígitos, y opción de forzar un rechazo para practicar ese escenario.
  - **Transferencia**: código QR real (generador propio, `caja/qr.py`, sin dependencias) hacia una pasarela de pago educativa que corre en un servidor HTTP local efímero (`caja/pasarela.py`, solo mientras el diálogo está abierto). Un teléfono en la misma red puede escanear y aprobar/rechazar desde el navegador; si no hay teléfono o red, botones de "Simular pago" garantizan que la venta nunca se bloquee (cumple §5). La página siempre indica "SIMULACIÓN EDUCATIVA — SIN DINERO REAL".
- Validación de efectivo insuficiente antes de permitir finalizar.
- Campo opcional "Facturar a" (nombre de empresa/persona y NIT/CC) por venta, impreso en el recibo si se diligencia.
- Al cerrar cada venta se muestra un aviso breve de "VENTA FINALIZADA" antes del cambio, para que el cierre de la transacción sea inequívoco (decisión 07/07/2026, ver abajo).

### 1.5 Factura / recibo
- Al finalizar: número de factura, fecha, cajero, productos, cantidades, total, dinero recibido, cambio.
- Opciones: imprimir (impresora térmica opcional) y guardar en PDF.
- La venta se **persiste automáticamente** al finalizar; no existe un botón separado de "guardar" que pueda omitirse.

### 1.6 Historial
- Consulta de ventas por fecha y por número de factura.

### 1.7 Reportes básicos
- Total vendido por día.
- Número de ventas.
- Producto más vendido.

### 1.8 Funciones específicas para el contexto educativo
- **Modo entrenamiento**: las ventas no afectan el stock/inventario real.
- Catálogo de productos de ejemplo precargado.
- Opción de reinicio de base de datos entre clases (con confirmación explícita, no accidental).
- Atajos de teclado para agilizar el cobro.
- Simulación de errores comunes: código inexistente, efectivo insuficiente, producto duplicado — para práctica de manejo de errores por parte del estudiante.

> **Decisión (07/07/2026):** se eliminó el "quiz de práctica de cambio" (diálogo que pedía al estudiante calcular el cambio). Razón: interrumpía el flujo y no existe en un POS real. La fidelidad al sistema real prima sobre los refuerzos didácticos artificiales: el estudiante practica con el mismo flujo que encontrará en un trabajo (cobro en paso aparte con denominaciones rápidas, cambio en visor, foco de vuelta al escáner). Los mensajes de error didácticos (código inexistente, efectivo insuficiente, duplicado) se conservan porque sí ocurren en cajas reales.

---

## 2. Modelo de datos (base local)

```
Usuarios        (id, nombre, usuario, contraseña_hash, rol)
Productos       (id, codigo_barras, nombre, precio, categoria, stock)
Ventas          (id, fecha, usuario, subtotal, iva, total, efectivo, cambio,
                 cliente_nombre, cliente_nit, codigo_autorizacion)
DetalleVenta    (id, id_venta, id_producto, cantidad, precio, subtotal)
```

`cliente_nombre`/`cliente_nit`: facturación opcional a nombre de empresa. `codigo_autorizacion`: código que entrega el datáfono simulado o la pasarela de transferencia. Estas tres columnas se agregan a bases de datos existentes mediante una migración automática (`db._migrar`) al iniciar, sin perder ventas previas.

- Base de datos **local**, embebida (ej. SQLite), sin servidor externo.
- Contraseñas nunca en texto plano (hash).
- Índices sobre `codigo_barras`, `fecha` y `numero_factura` para búsquedas <1s.
- Respaldo automático periódico de la base de datos (archivo local, sin dependencia de nube).

---

## 3. Pantallas del sistema

1. Inicio de sesión
2. Menú principal
3. Productos (CRUD)
4. Nueva venta (pantalla de caja — ver mockup abajo)
5. Historial de ventas
6. Reportes
7. Configuración
8. Usuarios (solo administrador: crear perfiles, roles, restablecer contraseñas, activar/desactivar — nunca borrado físico, para conservar la trazabilidad cajero↔venta)

> **Decisión (07/07/2026):** toda la interfaz debe ser 100 % operable con teclado (teclas F por pantalla, Esc para volver/cancelar); el ratón es siempre opcional. Las fechas se eligen con un mini calendario emergente navegable con flechas (sin librerías externas). Barra superior oscura unificada con reloj en vivo en todas las pantallas.

### Mockup de referencia — pantalla de caja

```
-------------------------------------------------------------
                 SISTEMA DE CAJA
-------------------------------------------------------------
Código:
[____________________________]
-------------------------------------------------------------
Producto               Cant     Precio       Subtotal
-------------------------------------------------------------
Arroz                  2        4.500        9.000
Azúcar                 1        5.200        5.200
Aceite                 1       14.000       14.000
-------------------------------------------------------------
Subtotal:                         28.200
IVA:                               0
TOTAL:                           28.200

Dinero recibido:
[50000]

CAMBIO:
21.800

[Finalizar venta]   [Cancelar]
```

---

## 4. Requisitos no funcionales (calidad de servicio)

| Categoría | Requisito |
|---|---|
| **Disponibilidad** | Operativo toda la jornada; inicio en <10s; sin Internet; sin dependencia de servidores externos; recuperación automática de sesión tras cierre inesperado. |
| **Rendimiento** | Búsqueda por código de barras <1s; cálculos de totales/cambio instantáneos; sin degradación tras ventas consecutivas; UI responde de inmediato a cualquier acción. |
| **Confiabilidad** | Ninguna venta se pierde; persistencia automática al finalizar; integridad de datos garantizada; validación de todo dato de entrada. |
| **Tolerancia a fallos** | Entrada manual si falla el lector; errores inesperados muestran mensaje claro sin cerrar la app; apagado repentino no corrompe la BD; recuperación automática tras reinicio. |
| **Seguridad** | Autenticación obligatoria; trazabilidad cajero↔venta; permisos de administrador para productos/reportes; respaldo automático de BD. |
| **Usabilidad** | Interfaz simple, botones grandes, mínimo de clics, flujo completo operable con teclado + lector. |
| **Escalabilidad** | Arquitectura permite agregar a futuro (sin tocar lo existente): inventario avanzado, clientes frecuentes, descuentos, facturación electrónica, cajón monedero, impresora térmica, lectores biométricos, multi-caja. |
| **Mantenibilidad** | Código organizado y documentado; BD diseñada para extensión; registro de errores en archivo de log; actualización de módulos sin comprometer datos almacenados. |
| **Portabilidad** | Windows 10/11; cualquier lector USB tipo teclado (HID); funcional en equipos de recursos básicos de laboratorio. |

---

## 5. Flujo ininterrumpido de operación (garantías duras)

El sistema **siempre** debe:
- Permitir registrar una venta.
- Calcular total y cambio de forma inmediata.
- Permitir corregir errores antes de finalizar la venta.

El sistema **nunca** debe:
- Bloquearse durante una transacción.
- Perder información de una venta en proceso.
- Requerir reinicio para seguir operando.
- Depender de un servicio externo para una función esencial.
- Degradar su tiempo de respuesta tras uso prolongado.

---

## 6. Exclusiones explícitas — de lo que el sistema DEBE prescindir

> Esta sección es tan vinculante como los requerimientos funcionales. Cualquier propuesta futura que reintroduzca alguno de estos elementos debe ser rechazada salvo justificación explícita y documentada aquí.

### 6.1 Dependencias externas prohibidas
- [ ] Conexión a Internet obligatoria para operar.
- [ ] Servidores remotos para procesar ventas.
- [ ] Servicios en la nube para consultar productos.
- [ ] Licencias con validación en línea constante.

### 6.2 Procesos prohibidos en segundo plano
- [ ] Sincronizaciones automáticas durante una venta activa.
- [ ] Actualizaciones automáticas del sistema en horario de uso.
- [ ] Escaneos o tareas de mantenimiento durante la jornada.
- [ ] Cualquier proceso en background ajeno a la operación de caja.

### 6.3 Elementos que degradan rendimiento
- [ ] Animaciones excesivas o efectos visuales complejos.
- [ ] Transiciones lentas entre pantallas.
- [ ] Carga de imágenes/multimedia innecesaria.
- [ ] Módulos cargados en memoria sin usarse.

### 6.4 Funcionalidades no esenciales (fuera de alcance permanente)
- [ ] Chat interno.
- [ ] Integración con redes sociales.
- [ ] Publicidad.
- [ ] Noticias o contenido informativo.
- [ ] Módulos ajenos a la operación de caja.
- [ ] Funciones experimentales/beta en el flujo principal.

### 6.5 Riesgos de pérdida de información — prohibido
- [ ] Guardado manual de ventas (debe ser automático).
- [ ] Almacenamiento temporal sin respaldo.
- [ ] Cerrar una venta sin registrarla.
- [ ] Eliminar información sin confirmación explícita.

### 6.6 Riesgos para la estabilidad — prohibido
- [ ] Consultas pesadas a la BD que bloqueen la UI.
- [ ] Uso excesivo de RAM/CPU.
- [ ] Ventanas múltiples innecesarias abiertas simultáneamente.
- [ ] Acoplamiento entre módulos tal que uno detenga toda la app.

### 6.7 Riesgos para la continuidad del servicio — prohibido
- [ ] Detener una venta por pérdida de Internet.
- [ ] Obligar a reiniciar la app para continuar trabajando.
- [ ] Cierre inesperado ante errores menores.
- [ ] Reinicios frecuentes requeridos.
- [ ] Tareas internas que interrumpan el cobro.

### 6.8 Riesgos para la experiencia del cajero — prohibido
- [ ] Pasos excesivos para registrar una venta.
- [ ] Formularios extensos.
- [ ] Confirmaciones innecesarias (solo confirmar acciones destructivas).
- [ ] Mensajes técnicos incomprensibles para el usuario final.
- [ ] Pantallas sobrecargadas de información.
- [ ] Funciones duplicadas.

### 6.9 Riesgos de seguridad — prohibido
- [ ] Contraseñas visibles en pantalla o en texto plano en BD.
- [ ] Acceso al sistema sin autenticación.
- [ ] Permisos de administrador para todos los usuarios por defecto.
- [ ] Modificación de precios sin autorización.
- [ ] Eliminación de registros sin trazabilidad (log).

### 6.10 Riesgos de mantenimiento — prohibido
- [ ] Código desorganizado o sin documentar.
- [ ] Duplicidad de funciones/lógica.
- [ ] Dependencias circulares o frágiles entre módulos.
- [ ] BD sin índices adecuados.
- [ ] Acumulación de archivos temporales sin limpieza.

---

## 7. Equipos y compatibilidad

- Lector de código de barras USB (modo teclado/HID).
- Impresora térmica (opcional).
- Cajón monedero (opcional).
- PC con Windows 10/11, hardware de gama básica (equipos de laboratorio).

---

## 8. Checklist de decisión rápida para nuevas features

Antes de implementar cualquier idea nueva, responder por escrito (en un PR o issue) estas preguntas y anexarlas:

1. **¿A qué sección funcional (1.x) pertenece o extiende?**
2. **¿Qué elemento de la sección 6 (exclusiones) podría violar, aunque sea parcialmente?**
3. **¿Puede fallar sin bloquear una venta en curso?** (sí/no + cómo se degrada con gracia)
4. **¿Agrega pasos/clics al flujo principal de cobro?** (cuántos, y por qué se justifican)
5. **¿Requiere Internet o un servicio externo?** (debe ser "no")
6. **¿Cómo se prueba que no degrada el rendimiento (<1s búsqueda, respuesta instantánea)?**

Si no se puede responder con claridad, la feature se pospone o se descarta.

---

## 9. Roadmap de escalabilidad (fuera del MVP, sin comprometer lo actual)

Orden sugerido de incorporación futura, siempre y cuando pasen el checklist de la sección 8:

1. Inventario avanzado (alertas de stock bajo, reposición).
2. Descuentos y promociones.
3. Clientes frecuentes / fidelización.
4. Facturación electrónica / integración fiscal.
5. Soporte multi-caja (varias estaciones sobre la misma BD local/red local).
6. Integración con cajón monedero e impresora térmica físicos.
7. Lectores biométricos para autenticación.

Cada ítem debe implementarse como módulo desacoplado que **no** pueda tumbar el flujo de venta si falla.

---

## 10. Estado del proyecto

- **Fase actual:** Definición de requerimientos (este documento).
- **Próximo paso:** Definir stack tecnológico (lenguaje, framework de UI, motor de BD local) compatible con Windows 10/11, sin dependencias de red, de bajo consumo de recursos.
- **Este archivo debe actualizarse** cada vez que se tome una decisión de alcance, arquitectura o se apruebe/rechace una feature vía el checklist de la sección 8.
