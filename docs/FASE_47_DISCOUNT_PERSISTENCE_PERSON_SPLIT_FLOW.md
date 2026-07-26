# Fase 47 - Descuentos persistentes y division de cobro

## Evidencia

Se reprodujo el caso reportado con Camarones empanizados a $5.99 y DESCUENTO ESTUDIANTE de $1.50. El carrito podia mostrar $5.99 - $1.50 = $4.49, pero al reabrir la cuenta o cobrar se usaba el subtotal bruto como saldo.

Tambien se valido la cuenta grande de las capturas:

- Persona 1: $35.97.
- Persona 2: $11.99.
- Persona 3: $5.99 con descuento de $1.50.
- Subtotal bruto: $53.95.
- Total neto correcto: $52.45.

## Causa raiz

El descuento no tenia un unico contrato visible para todos los flujos de cobro. El backend ya tenia snapshots y calculo central de totales, pero algunos consumidores seguian dependiendo de campos ambiguos o de estados locales del modal.

Los puntos concretos eran:

- `frontend/src/lib/posPricing.ts`: el calculo visual del carrito para descuentos fijos de producto o categoria no multiplicaba por cantidad como lo hace el backend.
- `frontend/src/pages/Index.tsx`: `handleSelectSplitByPerson` cerraba el modal de pago, limpiaba `checkoutDraft` y `tablePaymentScope`, y regresaba a Cuenta de mesa. Al volver a cobrar, la division quedaba en "Cuenta sin dividir".
- `frontend/src/pages/Index.tsx`: el encabezado del modal mantenia el total de mesa como jerarquia principal aunque el objetivo real fuera una persona o una parte.
- `backend/apps/payments/serializers.py` y `backend/apps/payments/views.py`: el contrato aceptaba objetivos de pago de orden, custom y guest, pero no exponia de forma clara `split_part` como alcance validado.

## Fuente autoritativa

La fuente unica para totales queda en `backend/apps/orders/services/totals.py`.

Funciones principales:

- `calculate_order_totals(order)`
- `calculate_order_item_totals(items)`
- `calculate_person_totals(order, guest_id)`
- `calculate_payment_scope_remaining_cents(order, payment_scope, ...)`
- `split_cents_evenly(total_cents, parts)`
- `allocate_cents(total_cents, weights)`

Los serializers y endpoints consumen esos resultados. El frontend no decide el total autoritativo; solo presenta el monto y envia el objetivo de pago.

## Formula

La formula usada es:

`subtotal bruto - descuento total + impuestos/cargos actuales = total neto`

El saldo pendiente se calcula como:

`total neto - pagos aplicados`

Se mantienen las reglas tributarias existentes. Esta fase no cambia si los precios incluyen IVA ni modifica la configuracion fiscal.

## Persistencia del descuento

La persistencia usa los campos existentes:

- `AppliedDiscount` para descuentos aplicados a la orden o items.
- `discount_snapshot` para conservar nombre, tipo, valor, monto y alcance.
- `OrderItem.discount_amount` para snapshot del descuento aplicado al item.

No se creo migracion. Las ordenes pagadas conservan su snapshot historico y no dependen de consultar promociones activas editadas despues.

## Cuenta de mesa

La cuenta debe mostrar los conceptos separados:

- Subtotal bruto.
- Descuento.
- Total neto.
- Pagado.
- Pendiente.

Los totales por persona salen de `calculate_person_totals`. Si el descuento pertenece al item de Persona 3, no se reparte entre otras personas.

Ejemplo:

- Persona 1: $35.97.
- Persona 2: $11.99.
- Persona 3: $5.99 - $1.50 = $4.49.
- Total mesa: $52.45.

## Cobro

El modal de cobro usa el saldo neto del backend como monto grande. Para cobro completo, el objetivo es la orden. Para cobro por persona, el objetivo es el invitado. Para partes iguales, el objetivo es la parte activa.

El backend valida:

- Que el objetivo pertenece a la orden.
- Que la persona tiene saldo pendiente.
- Que la parte no fue pagada antes.
- Que el pago no excede el saldo neto.
- Que no se cobre dos veces.

## Division por persona

La seleccion de "Dividir por persona" ya no cierra el modal principal ni regresa a Cuenta de mesa. Solo cierra el submodal de configuracion y cambia el cobro activo a la primera persona con saldo.

El modal muestra:

- `AHORA COBRARAS`.
- Persona activa.
- Cantidad de productos.
- Monto pendiente de esa persona como numero principal.

Despues de pagar una persona, el modal mantiene el flujo abierto, marca esa persona como pagada y selecciona la siguiente con saldo. Si no queda saldo, se usa el cierre normal de cuenta pagada.

## Partes iguales

Las partes iguales se generan siempre desde el saldo neto pendiente, no desde el subtotal bruto. Se trabaja en centavos.

Ejemplos:

- $52.45 en 2 partes: $26.22 y $26.23.
- $52.45 en 3 partes: $17.48, $17.48 y $17.49.

La suma de partes coincide exactamente con el saldo neto.

Cuando hay una parte activa, el encabezado principal muestra:

- `AHORA COBRARAS`.
- `PARTE N DE M`.
- Monto de esa parte como numero principal.
- Saldo total de mesa y pendiente despues de esa parte en texto secundario.

## Reparto de centavos

`split_cents_evenly` reparte en centavos enteros. La base se obtiene con division entera y el residuo se asigna deterministicamente a las ultimas partes, evitando diferencias de $0.01.

Para descuentos generales de orden, `allocate_cents` distribuye proporcionalmente con largest remainder y orden estable.

## Estados React corregidos

Se separo el estado confirmado de division del borrador del submodal:

- `splitMode`
- `personSplitEnabled`
- `splitDraftMode`
- `splitDraftParts`
- `splitDraftActivePartId`
- `tablePaymentScope`
- `tablePaymentPayments`

Cancelar el submodal ya no cambia la division activa. Aplicar una division actualiza el flujo interno sin cerrar el modal principal.

## Pruebas realizadas

Se ejecutaron pruebas transaccionales con rollback sobre `roseedb`, sin enviar DTE:

- $5.99 - $1.50 = $4.49.
- $53.95 - $1.50 = $52.45.
- Personas: $35.97 + $11.99 + $4.49 = $52.45.
- Dos partes: $26.22 + $26.23 = $52.45.
- Tres partes: $17.48 + $17.48 + $17.49 = $52.45.
- Pago por persona continuo, incluyendo pago mixto de Persona 3 con $2.00 tarjeta y $2.49 efectivo.
- Pago por partes iguales continuo.
- Estados de cocina no cambian descuento ni total.

## Riesgos pendientes

- La suite Django no pudo crear base de datos de prueba por permisos PostgreSQL del usuario actual. Se cubrio con smoke transaccional en `roseedb` con rollback.
- `npm run lint -- --max-warnings=0` sigue fallando por deuda previa del repositorio. No se amplio el alcance para corregir errores ajenos.
- Las partes iguales se validan como `split_part`, pero no hay una tabla persistente nueva de partes porque esta fase evito migraciones. El backend impide duplicar el mismo `split_part` recibido.
