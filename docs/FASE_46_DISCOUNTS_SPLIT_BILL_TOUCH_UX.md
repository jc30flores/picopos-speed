# Fase 46: descuentos, dividir cuenta y respuesta tactil

## Evidencia del bug

En una cuenta de mesa con dos `Camarones empanizados` de `$5.99`, el POS mostraba el descuento estudiante de `$1.50` por producto durante la toma de orden, pero `Cuenta de mesa` y `Cobrar` seguian usando `$11.98` como saldo. El modal incluso mostraba `Subtotal $11.98`, `Descuento -$3.00`, `Total $11.98`.

## Causa raiz

El descuento si se detectaba en el carrito, pero se perdia o se ignoraba al persistir y volver a cobrar una orden abierta:

- `orders.views._sync_pending_order_lines` borraba descuentos aplicados, recreaba items y dejaba `discount_total = 0`, `discount_snapshot = {}` y `amount_due_cents` con el subtotal bruto.
- `payments.views.PaymentListCreateView` recalculaba el saldo cobrable desde `order.total` y podia congelar el subtotal bruto como monto a cobrar.
- El frontend no mapeaba `discount_total`/`disposable_total` de la API y al reabrir una orden reconstruia el resumen con pricing local sin descuento seleccionado.
- El descuento fijo por producto se aplicaba por linea, no por unidad, asi que cantidad `2` podia no equivaler a dos lineas de cantidad `1`.

## Calculo autoritativo

Se centralizo el calculo en `apps.orders.services.totals`:

- `calculate_order_totals(order)`
- `calculate_order_item_totals(items)`
- `calculate_person_totals(order, guest)`
- `calculate_payment_scope_remaining_cents(order, allocation_payload)`
- `split_cents_evenly(total_cents, count)`
- `sync_order_totals(order)`
- `apply_order_discounts_and_totals(...)`

Formula base:

`subtotal_bruto - discount_total + desechables/impuestos segun politica actual = total_final`

La politica tributaria no se cambio. Si IVA esta incluido, el total final sigue siendo el total cobrado y el impuesto se deriva del neto. Si IVA no esta incluido, el impuesto se agrega al neto. Todo dinero se calcula con `Decimal` o centavos enteros.

## Persistencia

Se reutilizan campos existentes:

- `Order.discount_total`
- `Order.discount_snapshot`
- `OrderItem.discount_amount`
- `AppliedDiscount`

No se creo migracion. Para ventas pagadas, `financial_locked_at` conserva el total cobrable historico y evita recalcular el descuento sobre saldos parciales.

## Cuenta y cobro

`Cuenta de mesa` ahora muestra subtotal bruto, descuento, total neto, pagado y pendiente. Por persona muestra subtotal, descuento, total neto, pagado y pendiente usando los descuentos asignados por item.

El modal de cobro usa el saldo neto autoritativo para el numero grande y muestra resumen consistente. En el caso reportado:

- Subtotal bruto: `$11.98`
- Descuento: `$3.00`
- Total neto / pendiente inicial: `$8.98`

Pagos parciales y mixtos descuentan del neto ya calculado; no vuelven a aplicar promociones sobre el saldo.

## Dividir cuenta

El panel de division se rediseño con tarjetas completas presionables:

- `Cuenta sin dividir`
- `Dividir por persona`
- `Dividir en partes iguales`

Las tarjetas usan `role="radio"` y `aria-checked`, son navegables con teclado y tienen foco visible. En partes iguales el minimo es `2` y el maximo `20`.

El reparto de centavos es deterministico. Para `$8.98 / 3` se genera:

- Parte 1: `$2.99`
- Parte 2: `$2.99`
- Parte 3: `$3.00`

El backend rechaza repetir una parte ya pagada con: `Esta parte ya fue pagada.`

## Respuesta tactil

El teclado PIN usaba `pointerdown` y `click`; ahora `pointerdown` es el disparador inmediato para puntero primario y `click` queda como respaldo de teclado/lectores. Se filtra `event.isPrimary`, se evita duplicar digitos y el estado presionado se limpia con:

- `pointerup`
- `pointercancel`
- `pointerleave`
- `window blur`
- `visibilitychange`
- timeout de seguridad de `80 ms`

Tambien se agregaron utilidades tactiles (`tap-target`, `touch-button`, `pin-key`) y `touch-action: manipulation`/tap highlight transparente a botones frecuentes. No se agregaron listeners globales ni `preventDefault` global.

## Pruebas realizadas

- `backend/venv/bin/python -m py_compile ...`: OK.
- `backend/venv/bin/python backend/manage.py check`: OK.
- `cd frontend && npx tsc --noEmit`: OK.
- `cd frontend && npm run build`: OK.
- Smoke transaccional con rollback en `roseedb`: OK.

El smoke valido:

- 1 producto: `$5.99 - $1.50 = $4.49`.
- 2 productos, uno pendiente y uno en cocina: `$11.98 - $3.00 = $8.98`.
- Cambio de cantidad `2 -> 1`.
- Pago parcial `$4.00`, pendiente `$4.98`.
- Pago mixto `$4.00 tarjeta + $4.98 efectivo`, pagado `$8.98`.
- Persona 1 con dos productos conserva `$3.00` de descuento.
- Producto no elegible no recibe descuento.
- Partes iguales `$8.98 / 3 = 299, 299, 300` centavos.
- Parte repetida rechazada.
- Ticket renderizado en memoria incluye descuento y total neto.

## Limitaciones y riesgos

- `manage.py test` no pudo crear base de pruebas por permisos PostgreSQL (`permission denied to create database`). No se uso `roseedb` como test DB destructiva.
- `npm run lint -- --max-warnings=0` falla por deuda previa del repositorio; los errores nuevos de `Index.tsx` fueron corregidos y quedan advertencias previas.
- No se hizo prueba manual con navegador real ni dispositivo fisico; la validacion tactil fue por revision de eventos, TypeScript y build.
- DTE/Hacienda se mantuvo desactivado en smoke mediante mock del runtime y rollback transaccional.
