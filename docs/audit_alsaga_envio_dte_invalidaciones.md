# Auditoría ALSAGA FACTURADOR: Envío DTE (WhatsApp/Correo) + Invalidaciones

## Alcance auditado
- Código backend/frontend del repo `picopos-speed`.
- Variables de entorno y documentación local de DTE.
- **No** se modificó sistema externo Alsaga durante la auditoría.

---

## 1) Hallazgos de integración (base URL, auth, endpoints)

### 1.1 Base URL y auth DTE (bridge principal)
- Base URL: `DTE_BASE_URL`.
- Header auth: `DTE_API_AUTH_HEADER` (default `Authorization`).
- Prefijo auth: `DTE_API_AUTH_PREFIX` (default `Bearer`).
- Token: `DTE_API_TOKEN`.
- Endpoints por tipo:
  - `CF_01` -> `/api/v1/dte/factura`
  - `CCF_03` -> `/api/v1/dte/credito-fiscal`
  - `SE_14` -> `/api/v1/dte/sujeto-excluido`
  - `NC_05` -> `/api/v1/dte/nota-credito`
  - `INVALIDACION` -> `/api/v1/dte/invalidacion`

### 1.2 APIs de entrega (separadas)
- WhatsApp: usa `WHATSAPP_DTE_API_BASE` + `/send` con header `X-API-Key: WHATSAPP_DTE_API_KEY`.
- Correo: usa `DELIVER_EMAIL_API_BASE_URL` + `/send` con header `X-API-Key: DELIVER_EMAIL_API_KEY`.

> Nota: estas 2 APIs están separadas en código, no comparten endpoint.

---

## 2) API WhatsApp (exacto según código)

### Endpoint/método
- `POST {WHATSAPP_DTE_API_BASE}/send`

### Headers
- `X-API-Key: <WHATSAPP_DTE_API_KEY>`

### JSON exacto enviado
```json
{
  "order_id": 123,
  "dte_id": 456,
  "to": "5037XXXXXXX",
  "message": "DTE DTE-01-S001P001-000000000000123 estado ACEPTADO"
}
```

### Fuente de datos
- `order_id`: `DTERecord.order_id`
- `dte_id`: `DTERecord.id`
- `to`: `phone` solicitado o `WHATSAPP_DEFAULT_TO_PHONE`
- `message`: string fijo con `control_number` y `status`

### Respuestas y códigos
- Éxito: cualquier HTTP `2xx` => estado interno `SENT`.
- Error: HTTP no `2xx` o excepción de red => estado interno `FAILED`.
- Reintentos: hasta 3 intentos.
- Se guarda `provider_status`, `provider_body`, `retries`.

---

## 3) API Correo (exacto según código)

### Endpoint/método
- `POST {DELIVER_EMAIL_API_BASE_URL}/send`

### Headers
- `X-API-Key: <DELIVER_EMAIL_API_KEY>`

### JSON exacto enviado
```json
{
  "order_id": 123,
  "dte_id": 456,
  "to": "clie***@dominio.com",
  "subject": "DTE DTE-01-S001P001-000000000000123",
  "metadata": {
    "dte_type": "CF_01",
    "status": "ACEPTADO"
  }
}
```

### Fuente de datos
- `to`: `email` solicitado o `record.order.customer.correo`.
- `subject`, `metadata`: derivados del `DTERecord`.

### Respuestas y códigos
- Éxito: cualquier HTTP `2xx` => `SENT`.
- Error: HTTP no `2xx` o excepción => `FAILED`.
- Reintentos: hasta 3 intentos.

---

## 4) Invalidaciones (Hacienda/Alsaga) exacto en este repo

### Endpoint real
- Tipo DTE interno: `INVALIDACION`.
- Endpoint remoto resultante: `POST {DTE_BASE_URL}/api/v1/dte/invalidacion`.

### Headers
- `Content-Type: application/json`
- `{DTE_API_AUTH_HEADER}: {DTE_API_AUTH_PREFIX} {DTE_API_TOKEN}`

### JSON exacto que hoy se envía
```json
{
  "dte": {
    "identificacion": {
      "tipoDte": "AN",
      "numeroControl": "DTE-01-S001P001-000000000000123",
      "codigoGeneracion": "AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AAAA"
    },
    "motivo": "Motivo redactado",
    "responsable": "01234567-8",
    "solicitante": "98765432-1",
    "extra": {
      "source": "registros"
    }
  }
}
```

### Campos críticos y cómo se derivan
- `codigoGeneracion`: `record.generation_code` o `record.codigo_generacion`.
- `numeroControl`: `record.control_number`.
- `tipoDte`: fijo `AN`.
- `motivo`: del modal/entrada de usuario.
- `responsable` y `solicitante`: strings recibidos por API interna.
- `fecEmi` y `horEmi`: **no se envían** en el payload actual de invalidación.

### Respuestas/estado
- Respuesta se interpreta vía parser general DTE.
- Si parser concluye `ACEPTADO`, se marca éxito y `DTERecord` pasa a `INVALIDADO`.
- Se persiste trazabilidad en `DteInvalidationAttempt`.

---

## 5) Observaciones de completitud / riesgos

1. **No se encontró en este repo documentación externa oficial de Alsaga** que exija campos adicionales para invalidación (por ejemplo `fecEmi`, `horEmi`, bloques de emisor/receptor específicos de Hacienda) más allá del payload implementado actualmente.
2. El formato operativo “exacto” disponible en este código es el documentado arriba; no hay un schema externo adicional versionado dentro del repositorio para validarlo.
3. Las APIs de WhatsApp y Correo sí están separadas y con payload/header distintos.

