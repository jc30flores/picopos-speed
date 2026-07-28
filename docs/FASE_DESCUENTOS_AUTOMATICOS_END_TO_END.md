# Fase Descuentos Automáticos End To End

## Causa raíz

El formulario guardaba los días con la convención visual del POS y JavaScript: `D=0, L=1, M=2, X=3, J=4, V=5, S=6`. El backend evaluaba con `datetime.weekday()`, donde `L=0` y `D=6`. Por eso una regla configurada de lunes a sábado (`[1,2,3,4,5,6]`) no aplicaba los lunes y podía incluir domingo incorrectamente.

Además, las órdenes creadas desde mesa no siempre persistían `service_type`. La pantalla mostraba Mesa, pero el recálculo backend de la orden pendiente podía evaluar descuentos con `service_type_key=""`. Al enviar a cocina, la regla automática también podía reevaluarse fuera de horario y desaparecer en cuenta/cobro en lugar de conservar el descuento adquirido.

## Evaluación de días

La función central usa `discount_business_weekday(local_dt)`, que convierte la fecha local del negocio a la convención estable `D=0 ... S=6` con `(weekday + 1) % 7`. Esa convención coincide con el formulario y con los valores guardados en `Discount.days_of_week`.

## Zona horaria

El proyecto usa `TIME_ZONE = "America/El_Salvador"` y `USE_TZ = True`. La evaluación de descuentos usa `get_business_local_datetime()`, que convierte cualquier fecha recibida con `timezone.localtime()` antes de comparar día y `TimeField`. No se usa `datetime.now()` naive para descuentos.

## Servicio

La regla no compara etiquetas visibles. Para descuentos se normaliza el servicio con `normalize_discount_service_type()`. Mesa, `MESA`, `dine-in`, `DINE IN`, `EN_LOCAL` y equivalentes se evalúan como `MESA`. Delivery se mantiene como `DELIVERY`; no se mezcla con Pedidos Ya.

Las sesiones de mesa nuevas crean su orden primaria con `service_type=MESA`. Las órdenes pendientes de mesa antiguas o incompletas también resuelven `MESA` durante el autosave antes de recalcular descuentos.

## Productos Seleccionados

Consulta real en `roseedb` para `DESCUENTO ESTUDIANTE`:

- Incluido: `67 Camarones empanizados`.
- Incluido: `66 Filete La Roseé`.
- Incluido: `65 Pechuga a la plancha`.
- Incluido: `68 Camarones al ajillo`.
- Incluido: `69 Cordón blue`.
- No incluido: `35 Crepa de Melocoton`.

El cálculo compara `DiscountRuleTarget.product_id` contra el `Product.id` real de la línea de orden. No compara nombres ni IDs de `OrderItem`.

## Redondeo

El backend usa `Decimal` con redondeo monetario `ROUND_HALF_UP` mediante helpers centrales. El preview frontend usa centavos enteros para evitar valores como `17.990000000000002`; el backend sigue siendo autoritativo.

Caso verificado:

- Subtotal bruto: `$17.99`.
- Camarones empanizados: `$5.99`.
- Descuento: `25% * 5.99 = 1.4975`, redondeado a `$1.50`.
- Total neto: `$16.49`.

## Momento de Fijar El Descuento

Mientras la orden sigue editable, el descuento automático se recalcula con las condiciones actuales. Cuando la orden ya fue enviada a cocina, está en estados de cocina, tiene sesión de mesa enviada/cobrada/cerrada, o está financieramente bloqueada, el snapshot automático aplicado se conserva y se fuerza sobre los productos elegibles. Abrir cuenta o cobrar no debe eliminar el descuento por cambio de hora.

## Personas

Los descuentos se guardan por línea (`OrderItem.discount_amount`). `calculate_person_totals()` suma el subtotal, descuento y total neto de las líneas de cada `TableGuest`. No distribuye descuentos entre personas que no consumieron el producto descontado.

## Partes Iguales

Las partes iguales usan `amount_due_cents` del total neto. `split_cents_evenly()` reparte centavos de forma exacta para que la suma de partes coincida con el saldo neto.

Ejemplo con `$52.45`:

- 2 partes: `$26.22` y `$26.23`.
- 3 partes: `$17.48`, `$17.48` y `$17.49`.

## Pruebas Ejecutadas

- `backend/venv/bin/python -m py_compile` sobre archivos backend modificados: OK.
- `backend/venv/bin/python backend/manage.py test apps.orders.tests.test_discount_application apps.orders.tests.test_discount_payment_totals`: bloqueado porque el usuario PostgreSQL no tiene permiso para crear base de pruebas.
- Smoke transaccional con rollback en `roseedb`, caso de captura real: OK.
- Smoke transaccional con rollback en `roseedb`, mesa/autosave/cocina fuera de horario: OK.

## Riesgos Pendientes

- Las pruebas Django convencionales quedan pendientes hasta que PostgreSQL permita crear la base de test o se configure una base de test autorizada.
- No se cambió la semántica histórica del campo físico `Order.subtotal` por su uso en rutas fiscales antiguas. La fuente autoritativa para subtotal bruto en API/tickets/cobro es `calculate_order_totals()` y los campos serializer `gross_subtotal` / `subtotal_before_discounts`.
- Las pruebas visuales completas en PWA instalada y múltiples viewports deben ejecutarse manualmente o con un entorno navegador estable si se requiere evidencia visual formal.
