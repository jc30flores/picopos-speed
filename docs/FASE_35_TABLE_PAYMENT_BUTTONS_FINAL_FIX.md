# FASE 35 - Corrección final de botones de cobro en mesas

## Alcance

Esta fase corrige el flujo de cobro desde mesas sin tocar infraestructura, puertos, dominios, PWA, DTE ni configuración local. La base verificada para las validaciones fue `roseedb`.

## Causa raíz

Los botones de `Cobrar` dependían de un flujo asíncrono que cargaba orden y pagos antes de abrir el modal. Si ese estado quedaba bloqueado, desmontado por el modal de cuenta, o mezclado con efectos del carrito POS, el usuario no veía respuesta clara al click. Además, el carrito temporal usado para cobrar mesa podía disparar efectos del POS rápido como disponibilidad de inventario y persistencia de draft.

En la corrección final se confirmó una causa adicional y principal: el componente del mapa de mesas tenía un `return` temprano cuando `posMode === "tables"`. El `Dialog` de `Cobrar pedido` estaba renderizado solamente en la rama del POS de productos, por debajo de ese `return`. Entonces el click sí preparaba `isPaymentOpen` y cargaba orden/pagos, pero la UI activa del mapa no montaba ningún modal de pago; por eso la cuenta se cerraba y el usuario volvía al mapa sin ver el cobro.

## Cambios

- `openTablePayment` ahora centraliza la apertura de cobro de mesas.
- El modal `Cobrar pedido` se abre inmediatamente con estado de carga mientras se consultan orden y pagos.
- El mapa de mesas ahora monta el modal `Cobrar pedido` y el diálogo `Dividir cuenta` en su propia rama de renderizado, sin navegar al POS de productos.
- El mismo flujo se usa para:
  - menú contextual de mesa;
  - `Cuenta de mesa > Cobrar`;
  - `Cuenta de mesa > Cobrar Persona X`;
  - resumen de cocina/mesa.
- Los botones de cobro de mesas usan `type="button"` y detienen propagación cuando están dentro del menú contextual.
- Los botones de cobro se deshabilitan mientras se está preparando o mostrando un cobro para evitar aperturas duplicadas.
- Cerrar el modal de pago usa el handler central para limpiar estado y reabrir `Cuenta de mesa` cuando corresponde.
- Durante cobro de mesa se evita:
  - persistir el carrito temporal como draft del POS rápido;
  - recalcular precios del carrito temporal;
  - ejecutar `cart-availability` mientras el modal de cobro está abierto.
  - recalcular descuentos del POS rápido durante el cobro de mesa.

## Pago por persona y restante

Para `Cobrar Persona X`, el frontend calcula:

- productos de la persona;
- total de esa persona;
- pagos ya asignados a esa persona;
- saldo restante de esa persona.

El pago se envía con `payment_scope=guest`, `table_session`, `table_guest`, `guest_number` y `order_item_ids`.

Para `Cobrar` mesa completa, se cobra el saldo total restante de la orden. El backend ahora prorratea allocations sobre el saldo pendiente por producto, no sobre el total original, evitando volver a asignar pago a productos ya cubiertos después de un pago parcial por persona.

## Liberación de mesa

El backend mantiene la sesión en `partially_paid` si queda saldo. Solo cierra/libera la mesa cuando el saldo total de la orden llega a `0`.

## Validaciones realizadas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- verificación DB: `roseedb`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- `cd frontend && npm run build`
- revisión de logs recientes de `la-rosee-project` buscando `pending 422`, `release 404`, tracebacks y errores DTE.

## Pendientes

- `migrate` reporta cambios de modelo antiguos en `employees`, `inventory` y `menu` sin migración. No fueron creados por esta fase y quedan fuera del alcance.
- La prueba manual completa de pago multimétodo debe ejecutarse en UI real con una mesa activa.
