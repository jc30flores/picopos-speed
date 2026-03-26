# Cómo funciona DTE en PicoPOS

## Flujo principal
1. `POST /api/payments/` crea el pago.
2. Si el pago cierra el saldo, se dispara `transaction.on_commit()` y luego `send_dte_for_order(order, payment)`.
3. Se genera/actualiza `DTERecord` con payload request/response, intentos, sello, uuid y estado MH.
4. Si el proveedor responde 5xx/timeout, el DTE queda `PENDIENTE` para `dte_autoresend`.

## Modelos principales
- `DTERecord`: bitácora completa de emisión/reenvío/invalidation/NC.
- `DTEControlCounter`: correlativo por ambiente/tipo/año/establecimiento/punto de venta.
- `DteInvalidationAttempt`: trazabilidad de invalidaciones.
- `DteDeliveryAttempt`: trazabilidad de email/WhatsApp.

## Endpoints
- `GET /api/dte/issued/`
- `POST /api/dte/issued/{id}/resend/`
- `POST /api/dte/issued/{id}/invalidate/`
- `POST /api/dte/issued/{id}/send-email/`
- `POST /api/dte/issued/{id}/send-whatsapp/`
- `POST /api/orders/{id}/credit-note/`
- `GET /api/orders/{id}/credit-note/preview/`
- `GET /api/reports/sales-book/json/`
- `GET /api/reports/sales-book/pdf/`

## Comandos
- `python manage.py dte_healthcheck`
- `python manage.py dte_autoresend --limit 25 --batch-size 25 --backoff-seconds 60`

## Flags de logging
- `DTE_LOG_PAYLOAD_FULL=1`
- `DTE_LOG_RESPONSE_FULL=1`
- `DTE_LOG_TO_FILE=1`
- `DTE_LOG_DIR=tmp/dte_payloads`
