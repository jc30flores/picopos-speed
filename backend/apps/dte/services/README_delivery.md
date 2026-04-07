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
    "email": {"ok": true, "status_code": 200, "error": null},
    "whatsapp": {"ok": false, "status_code": null, "error": "WHATSAPP_DTE_API_BASE missing"}
  },
  "summary": "Fallo en canal(es): whatsapp"
}
```

- `success=true` solo cuando todos los canales solicitados terminaron `ok=true`.

## Configuración requerida
- WhatsApp: `WHATSAPP_DTE_API_BASE`, `WHATSAPP_DTE_API_KEY`
- Email: `DELIVER_EMAIL_API_BASE_URL` o `EMAIL_API_BASE_URL`; `DELIVER_EMAIL_API_KEY` o `EMAIL_API_KEY`

## Auditoría
Se registra un `log_audit` por canal con:
- usuario actor,
- `order_id` / `issued_id`,
- estado del canal,
- `status_code` y error resumido.

No se registran API keys ni secretos.
