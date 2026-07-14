# Fase 32 - Correcciones responsive, cobro de mesa e impresion

## Alcance

Esta fase corrige problemas operativos del modo mesas sin tocar infraestructura, base de datos, puertos, dominios, Caddy, systemd, Cloudflare ni `.env`.

Base validada: `roseedb`.

## Modales responsive

- `DialogContent` y `AlertDialogContent` ahora tienen ancho seguro `calc(100vw - 2rem)` y altura maxima `calc(100dvh - 2rem)`.
- `DialogFooter` y `AlertDialogFooter` permiten envolver botones y apilarlos en pantallas pequenas.
- Se ajustaron modales criticos:
  - Productos sin guardar.
  - Nueva orden de mesa.
  - Unir mesas.
  - Liberar mesa con saldo pendiente.
  - Cobrar pedido.
  - Vista previa de ticket.
  - Cuenta de mesa.

## Contraste visual

- Se agregaron tokens:
  - `--app-text-strong`
  - `--app-heading`
  - `--app-label`
- El header contextual de mesa usa `--color-primary-text`, calculado para leerse sobre el color suave del tema.
- El texto "Orden de mesa" y el nombre de mesa quedan visibles en claro, oscuro y colores personalizados.

## Cobro directo desde mesa

- `openTablePayment` ya no cambia el fondo al POS de productos.
- El cobro desde mapa o cuenta abre el modal sobre el modo mesas.
- El cobro completo de mesa ahora usa `tablePaymentScope` igual que el cobro por persona.
- Si el cobro se abrió desde Cuenta de mesa y se cierra sin pagar, vuelve a Cuenta de mesa.

## Pago por persona y multimétodo

- Los pagos por persona siguen usando `PaymentAllocation` para asignar montos a persona/items.
- Los pagos parciales ya no intentan guardar la orden con `/api/orders/<id>/pending/` después del pago.
- En pago de mesa completo, el frontend ya no llama manualmente `release` después del pago; el backend de pagos cierra la sesión cuando el saldo global queda en cero.
- Si la sesión ya está cerrada y alguien llama `release`, el endpoint responde 200 idempotente.
- El pago multimétodo conserva partes pagadas y permite continuar con la siguiente parte.

## Ticket cuenta no pagada

- La cuenta local abre el modal termico 58mm/80mm.
- El ticket indica:
  - `CUENTA DE MESA`
  - `Ticket para revisión`
  - `Cuenta no pagada`
  - `NO VÁLIDO COMO COMPROBANTE FISCAL`
  - `Pendiente de pago`
- El preview usa papel blanco y texto negro fuerte, independiente del tema.

## Recibo pagado

- Al completar el pago de una mesa se genera vista previa de recibo termico.
- El recibo indica:
  - `RECIBO DE PAGO`
  - `Cuenta pagada`
  - mesa, alcance, fecha, pedido, productos, metodo, pagado, recibido/cambio y total pagado.

## Bluetooth

- Cancelar el selector Bluetooth ya no muestra error tecnico en ingles.
- Mensajes normalizados:
  - `No se seleccionó ninguna impresora.`
  - `Bluetooth no está disponible en este navegador. Puedes usar impresión del navegador.`
  - `No se pudo conectar con la impresora. Verifica que esté encendida y cerca.`
  - `No se pudo imprimir. Revisa la conexión de la impresora.`
- Imprimir sin Bluetooth conectado abre fallback del navegador con mensaje claro.

## PDF / reportlab

- `/api/orders/<id>/receipt.pdf` mantiene fallback sin 500 y responde `RECEIPT_PDF_UNAVAILABLE` si no puede generar PDF.
- `/api/payments/<id>/ticket.pdf` responde `PAYMENT_TICKET_PDF_UNAVAILABLE` en fallos genericos de PDF.

## Pruebas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- Confirmacion DB `roseedb / roseedb`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- `npm run build`
- Revision de logs con `journalctl -u la-rosee-project -n 700 --no-pager`

## Pendientes

- Validar Bluetooth con impresora fisica real.
- La impresion de logo por ESC/POS sigue limitada a preview/fallback; por Bluetooth se envia texto termico.
- Django reporta drift previo de migraciones en `employees`, `inventory` y `menu`, fuera de esta fase.
