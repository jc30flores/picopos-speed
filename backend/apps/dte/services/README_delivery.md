# DTE delivery (email + WhatsApp)

## Endpoints internos
- `POST /api/dte/issued/{id}/deliver/`
- `POST /api/dte/orders/{order_id}/deliver/`

Ambos usan `deliver_dte_to_client(...)` en `delivery.py`.

## JSON esperado de entrada
```json
{
  "channels": ["email", "whatsapp"],
  "email": "cliente@correo.com",
  "phone": "5037xxxxxxx"
}
```

- `channels` es obligatorio (al menos un canal válido).
- `email` y `phone` son opcionales; si no se envían, se usan los del cliente.

## Respuesta
```json
{
  "success": false,
  "order_id": 111,
  "issued_id": 123,
  "results": {
    "email": {"ok": true, "status_code": 200, "provider_status": 200, "provider_message": "ok", "recipient": "cliente@correo.com", "error": null},
    "whatsapp": {"ok": false, "status_code": null, "provider_status": null, "provider_message": "WHATSAPP_DTE_API_BASE missing", "recipient": null, "error": "WHATSAPP_DTE_API_BASE missing"}
  },
  "summary": "Fallo en canal(es): whatsapp"
}
```

- `success=true` solo cuando todos los canales solicitados terminaron `ok=true`.

## Configuración requerida
- WhatsApp: `WHATSAPP_DTE_API_BASE`, `WHATSAPP_DTE_API_KEY`
- Email: `DELIVER_EMAIL_API_BASE_URL` o `EMAIL_API_BASE_URL`; `DELIVER_EMAIL_API_KEY` o `EMAIL_API_KEY`

## Contratos usados por este backend

### Email (`DELIVER_EMAIL_API_BASE_URL + DELIVER_EMAIL_API_ENDPOINT`)
Payload enviado:
```json
{
  "to_email": "cliente@correo.com",
  "subject": "DTE DTE-01-S001P001-000000000000123",
  "body_text": "Adjuntamos comprobante DTE DTE-01-S001P001-000000000000123.",
  "invoice_json": { "...": "..." },
  "flags": { "source": "picopos", "channel": "email_dte", "attach_pdf": true, "attach_json": true },
  "metadata": { "dte_type": "CF_01", "status": "ACEPTADO" }
}
```
- Campos requeridos: `to_email`, `subject`, `body_text`, `invoice_json`.
- Campos opcionales: `flags`, `metadata` (y `body_html` si se necesitara agregar en el futuro).

### WhatsApp (`WHATSAPP_DTE_API_BASE + WHATSAPP_DTE_API_ENDPOINT`)
Payload enviado (gateway actual):
```json
{
  "num_receptor": "5037XXXXXXX",
  "send_json": true,
  "dte": { "...": "..." },
  "tipo_dte": "01",
  "doc_type": "CF",
  "empresa_nombre": "PicoPOS",
  "total": 15.50,
  "hacienda_response": { "...": "..." },
  "sello_recibido": "SELLO",
  "fh_procesamiento": "2026-04-11T10:00:00-06:00",
  "descripcion_msg": "DTE DTE-01-S001P001-000000000000123 estado ACEPTADO"
}
```
- Este backend usa un gateway configurable vía `.env`.
- Endpoint por defecto: `/api/send-dte-whatsapp`.
- Si el proveedor devuelve `queued=true`/`status=queued`, el intento queda `QUEUED` (encolado), no `SENT`.

## Auditoría
Se registra un `log_audit` por canal con:
- usuario actor,
- `order_id` / `issued_id`,
- estado del canal,
- `status_code` y error resumido.

No se registran API keys ni secretos.
