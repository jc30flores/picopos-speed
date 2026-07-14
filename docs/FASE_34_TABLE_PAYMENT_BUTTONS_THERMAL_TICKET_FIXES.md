# Fase 34 - Ticket térmico, Bluetooth y cobro de mesas

Fecha: 2026-07-14

## Alcance

Esta fase corrige puntos operativos del flujo de mesas sin tocar infraestructura, dominios, puertos, Caddy, systemd, Cloudflare, túneles, `.env` ni configuración de base de datos.

## Ticket térmico 58mm/80mm

- La cuenta local y el recibo pagado ahora imprimen cada producto con cantidad, descripción, precio unitario y subtotal de línea.
- El subtotal de línea se calcula como `cantidad x precio unitario`.
- El mismo texto alimenta la vista previa y el envío ESC/POS por Bluetooth para que ambos flujos sean consistentes.
- Los modificadores se imprimen debajo del producto, con envoltura de texto para no romper el ancho de 58mm.

Ejemplo:

```text
3x CREPA DE FRESA
  P.Unit $6.99          $20.97
  + Extra fresa
```

## Bluetooth

- La búsqueda inicial usa filtros por nombres comunes de impresoras: `Printer`, `POS`, `PT-`, `MTP`, `RPP`, `XP-`, `Thermal`, `POS58`, `POS-58`, `58`, `80`.
- Si la impresora no aparece con filtros, el modal ofrece `Buscar todos los dispositivos`.
- La referencia de impresora se mantiene en un manager compartido mientras la página siga abierta.
- Si el navegador soporta `navigator.bluetooth.getDevices`, se intenta recuperar una impresora previamente autorizada.
- Si la impresora se desconecta, el estado cambia a `Desconectada`; al imprimir se intenta reconectar si hay un dispositivo autorizado.
- Cancelar el selector Bluetooth se maneja como una acción normal: `No se seleccionó ninguna impresora.`
- No se muestran errores técnicos crudos en inglés al usuario.

## Menú Contextual De Mesa

- El menú de acciones de mesa tiene ancho compacto con límite de pantalla.
- En pantallas estrechas se centra como panel compacto con altura máxima y scroll interno.
- Los textos de botones pueden envolver línea sin cortar horizontalmente.
- El botón `Cobrar` ya no depende del total cacheado de la sesión para habilitarse; si hay orden activa, abre el cobro y valida saldo real contra la orden.

## Botones Cobrar

- `Cobrar` desde menú contextual abre el modal de pago directo de mesa.
- `Cobrar` desde Cuenta de mesa reutiliza la orden y pagos ya cargados en el modal, evitando consultas duplicadas.
- `Cobrar Persona X` usa el scope de la persona filtrada.
- Cuenta completa usa scope de mesa.
- No navega a edición de productos para cobrar mesas.

## Pago Por Persona Y Resto

- El flujo de pago mantiene `tablePaymentScope` para distinguir cuenta completa vs persona.
- Los cobros de mesa no ejecutan la finalización de órdenes pendientes del POS rápido.
- Tras pago parcial, la cuenta puede reabrirse para seguir cobrando el saldo restante.
- La mesa solo debe liberarse cuando el backend reporta la orden completa como pagada.

## Reducción De Requests

- La disponibilidad de inventario usa listas memoizadas de productos candidatos y cantidades de carrito.
- El chequeo mantiene debounce y solo se dispara cuando cambian cantidades o productos visibles.
- El cobro desde Cuenta de mesa no vuelve a pedir `GET /api/orders/<id>/` ni `GET /api/payments/?order_id=<id>` si esos datos ya están cargados.

## Pruebas

- `npm run build`: exitoso.
- `journalctl -u la-rosee-project -n 700 --no-pager`: se revisaron logs; antes del parche existían ráfagas de `payments/orders/cart-availability`, y no aparecieron tracebacks nuevos durante HMR.

## Pendientes Y Riesgos

- La reconexión Bluetooth depende de soporte real del navegador y permisos ya otorgados por el usuario.
- Algunas impresoras térmicas usan servicios/características no estándar; para esos casos queda disponible el flujo `Buscar todos los dispositivos`.
- El icono/logo en impresión Bluetooth sigue siendo texto ESC/POS; la vista previa sí muestra logo si está configurado.
