# Fase 31 - Cuenta de mesa, impresion local y pagos por persona

## Alcance

Esta fase refuerza el flujo operativo de mesa sin cambiar infraestructura, puertos, dominios, Caddy, systemd ni configuracion de base. La base usada para validar fue `roseedb`.

## Contraste visual

- Se ampliaron tokens globales de tema para bordes fuertes, texto inverso y badges.
- Se agregaron helpers de contraste:
  - `getContrastRatio`
  - `ensureReadableColor`
  - `deriveThemeTokens`
- La carga de apariencia ahora fuerza contraste legible entre color primario, superficies suaves y texto.
- El modal de cuenta usa `foreground`, `muted-foreground`, `app-border-strong`, `badge-bg` y `badge-text` para evitar texto invisible en modo claro/oscuro.

## Cuenta de mesa

- El modal ahora usa ancho adaptable, alto maximo basado en `100dvh`, scroll interno y footer fijo.
- El header muestra mesa, personas, total, pagado y pendiente en una linea compacta.
- Filtros disponibles:
  - Todos
  - Persona 1, Persona 2, etc.
  - Pendiente de enviar
  - En cocina
  - Terminados
  - Servidos
  - Pagados
- La vista Todos agrupa productos por persona y muestra subtotal/pagado por grupo.
- La vista de una persona muestra total, pagado y pendiente de esa persona.
- Cada producto muestra cantidad, precio unitario, total, persona, estado y modificadores.

## Impresion local

- `Imprimir cuenta local` abre un modal de vista previa de ticket.
- El ticket indica:
  - `CUENTA DE MESA`
  - `Ticket para revision`
  - `Cuenta no pagada`
  - `NO VALIDO COMO COMPROBANTE FISCAL`
  - productos agrupados por persona
  - modificadores
  - total, pagado y pendiente
- Se carga el logo configurado desde `settings/ticket`.
- La vista previa soporta 58mm y 80mm.
- El flujo Bluetooth usa Web Bluetooth, busca una caracteristica escribible y envia ESC/POS por chunks.
- Si Bluetooth no esta disponible, el boton Imprimir usa la impresion del navegador.

## Fallback PDF

- `receipt.pdf` ya no debe caer en 500 cuando falta `reportlab`.
- `build_receipt_pdf_from_text` cae a PDF simple si el renderer rico no puede cargar dependencias.
- La vista de orden captura fallos inesperados y devuelve una respuesta controlada.

## Pago por persona y multimétodo

- Se agrego `PaymentAllocation` para asociar pagos a:
  - sesion de mesa
  - persona
  - item opcional
  - monto aplicado
- `createPayment` acepta alcance opcional:
  - `payment_scope`
  - `table_session`
  - `table_guest`
  - `guest_number`
  - `guest_label`
  - `order_item_ids`
- Al cobrar una persona, el modal carga solo sus productos y su saldo.
- Un pago por persona no marca toda la orden como pagada si otras personas tienen saldo.
- La mesa solo se libera cuando el saldo total de la orden llega a cero.
- El panel existente de dividir cuenta se reutiliza para efectivo + tarjeta + transferencia u otros metodos configurados.

## Caja y DTE

- La logica base de caja se conserva: efectivo registra el monto aplicado, no el cambio.
- No se agrego envio fiscal ni llamada nueva a Hacienda.
- DTE permanece sujeto al runtime existente.

## Validaciones realizadas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- verificacion DB: `roseedb`
- `npm run build`

## Pendientes y riesgos

- Web Bluetooth solo funciona en navegadores compatibles y contexto seguro.
- La impresion de imagen/logo por Bluetooth queda como vista previa con logo; el texto ESC/POS se envia directo.
- `makemigrations --check --dry-run` sigue reportando deuda previa de indices en `employees`, `inventory` y `menu`; no fue parte de esta fase.
- Las pruebas reales de impresora fisica y pago con mesa real deben ejecutarse en el navegador del local.
