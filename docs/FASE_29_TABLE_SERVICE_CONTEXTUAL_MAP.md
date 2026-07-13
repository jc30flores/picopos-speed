# Fase 29 - Mapa contextual de mesas

## Alcance

Esta fase deja el POS de `table_service` como una superficie operativa de salon. El editor y la configuracion de mesas quedan fuera del POS; `/pos` se enfoca en mapa, estados y acciones por mesa.

## UX full-screen

- `/pos` en modo mesas renderiza un mapa full-screen.
- Fuera del mapa solo queda el boton minimalista `Menu`, fijo en la esquina superior izquierda.
- No se muestran `Editor de mesas`, selector de area, `Todas las areas`, filtros por estado ni paneles laterales.
- Los contadores quedan dentro del mapa, arriba a la derecha:
  - `Libres: X`
  - `Ocupadas: X`
  - `En cocina: X`
- El mapa usa scroll/pan propio.
- En tema claro usa superficies claras profesionales con contraste de texto.
- En tema oscuro usa superficies oscuras operativas.
- Las mesas usan variables del tema para bordes y resaltados: `--color-primary`, `--color-primary-border`, `--color-primary-surface`, `--color-primary-soft` y `--color-primary-contrast`.
- El boton de regreso navega al menu principal con `navigate("/")` sin recargar la pagina.

## Menu contextual

Al tocar una mesa se abre un menu contextual. En desktop aparece cerca del cursor; en pantallas pequenas funciona como bottom sheet. Se cierra tocando fuera o con `Esc`.

El menu muestra:

- nombre de mesa
- estado: libre, ocupada, en cocina o parcial
- personas cuando hay sesion
- total cacheado si existe
- indicador `Unida` cuando la sesion incluye mas de una mesa
- colores adaptados a tema claro/oscuro mediante `bg-popover`, `text-popover-foreground`, `border` y `muted`

## Acciones por estado

Mesa libre:

- Nueva orden
- Unir mesa
- Cerrar

Mesa ocupada o con orden abierta:

- Agregar productos
- Ver cuenta
- Cobrar
- Enviar cocina
- Mover mesa
- Unir mesa
- Dividir cuenta
- Liberar mesa con confirmacion propia; el backend bloquea si hay saldo pendiente
- Cerrar

Mesa unida:

- Ver cuenta conjunta
- Agregar productos
- Cobrar grupo
- Mover grupo
- Unir otra mesa
- Separar mesa
- Dividir cuenta
- Enviar cocina
- Liberar grupo si no hay saldo
- Cerrar

Reservas/bloqueo quedan pendientes porque no hay flujo completo habilitado.

## Nueva orden y agregar productos

`Nueva orden` abre el dialogo de personas, modo de orden (`Orden completa` o `Por persona`) y notas. El modo recomendado por defecto es `Por persona`. Al iniciar, se crea la sesion y se abre el POS contextual de esa mesa.

`Agregar productos` reemplaza a `Nueva orden` cuando ya existe una sesion activa. Reutiliza el POS rapido con contexto de mesa, persona activa en modo `per_person`, guardado y regreso al mapa.

En POS contextual de mesa:

- El encabezado dice `Orden de mesa`.
- Si hay grupo, muestra `Grupo Mesa X + Mesa Y`.
- Solo aparece `Volver a mesas`; no aparece `Volver al menu principal`.
- Si hay productos sin guardar, `Volver a mesas` abre un modal propio con `Guardar y volver`, `Volver sin guardar` y `Cancelar`.
- El CTA principal ya no es `Cobrar`; es `Enviar a cocina` cuando hay productos de cocina o `Guardar orden` cuando no aplica cocina.
- `Cobrar mesa` queda como accion secundaria.

## Recuperacion de sesion activa

Si el usuario intenta iniciar una orden sobre una mesa que ya tiene sesion activa, el backend responde `409 Conflict` con:

```json
{
  "code": "table_already_has_active_session",
  "message": "La mesa ya tiene una orden activa.",
  "session": {},
  "order_id": 123
}
```

El frontend consume ese payload y abre la sesion existente en lugar de mostrar un error rojo o volver a intentar crear otra sesion.

El boton `Iniciar orden` queda deshabilitado mientras el request esta en curso para evitar doble POST. Despues de crear o recuperar una sesion, el estado local de sesiones se actualiza inmediatamente y `posMode` cambia a `pos` antes de navegar con `pending_order_id`.

## Ver cuenta

`Ver cuenta` abre un resumen local con:

- mesa
- personas
- productos y asignacion por persona cuando existe
- subtotal
- descuentos
- impuestos
- total
- pagos realizados
- saldo pendiente
- acciones para agregar productos, cobrar, imprimir cuenta local y cerrar

No se muestra flujo DTE cuando DTE esta apagado.

## Cobrar

`Cobrar` abre directamente el modal de cobro con `pending_order_id` y `mode=pay`, conservando pagos divididos, pagos parciales y pago completo. No manda al usuario a tomar productos como paso principal. Al completar el pago, el frontend solicita liberar la sesion pagada para que el mapa la muestre libre. Si el pago queda parcial, la sesion permanece activa.

DTE apagado sigue registrando el pago localmente y no contacta Hacienda.

## Unir mesas

`Unir mesa` entra en modo seleccion dentro del mapa:

1. muestra `Selecciona la mesa que deseas unir con Mesa X`
2. resalta destinos validos
3. abre modal propio `Unir mesas`
4. si ambas mesas estaban libres, muestra cantidad de personas, modo de orden y notas
5. une la mesa a la sesion existente o crea una sesion agrupada si ambas mesas estaban libres

El backend valida mesas inactivas, ids invalidos y conflictos con otra sesion activa para evitar 500.

Las mesas unidas ahora comparten identidad visual de grupo:

- mismo color de grupo
- borde y halo compartido
- etiqueta `Grupo N`
- menu contextual con lista completa del grupo, por ejemplo `Mesa 9 + Mesa 10`

Para unir una tercera mesa, se elige `Unir mesa` desde cualquier mesa del grupo y luego se selecciona una mesa libre. La mesa nueva se agrega a la misma sesion y adopta la identidad visual del grupo.

## Separar mesas

`Separar mesa` aparece cuando una sesion tiene mas de una mesa. Usa modal propio del sistema y llama `POST /api/orders/tables/sessions/<id>/split-table/`.

Reglas actuales:

- quita la mesa seleccionada del grupo
- mantiene la orden/cuenta conjunta en las mesas restantes
- si queda una sola mesa, el grupo visual desaparece
- la mesa separada queda libre visualmente porque ya no pertenece a la sesion activa

La separacion avanzada de productos/personas por mesa sigue pendiente; por ahora la cuenta no se divide automaticamente.

## Mover mesa

`Mover mesa` entra en modo seleccion:

1. muestra `Selecciona la mesa destino`
2. resalta mesas libres
3. abre modal propio `Mover mesa`
4. mueve la sesion al destino y actualiza la referencia de la orden

No se pierden productos, personas ni pagos porque se mueve la relacion de mesa, no la orden.

## Liberar mesa

`Liberar mesa` abre modal propio del sistema. Si hay saldo pendiente, el backend responde con `No puedes liberar una mesa con saldo pendiente.` y no borra datos de venta. Si la orden ya esta pagada o no hay orden con saldo, la sesion se cierra.

## Confirmaciones del sistema

El flujo de mesas no usa `window.confirm`, `alert` ni `prompt`. Las confirmaciones de unir, mover y liberar usan `AlertDialog` de GastroPOSV con botones `Cancelar` y accion principal.

## Enviar cocina

`Enviar cocina` se muestra para sesiones con orden activa y tambien es el CTA principal del POS contextual cuando los productos requieren cocina. Si la orden esta vacia, el backend responde con mensaje controlado. Si procede, guarda los items, marca la orden como enviada y la mesa pasa a `En cocina`.

Cuando no hay productos de cocina, el CTA principal es `Guardar orden`; guarda los items en la mesa sin abrir cobro.

## Pruebas realizadas

- `backend/venv/bin/python backend/manage.py check`
- `cd frontend && npm run build`
- Smoke de compilacion del flujo: mapa, menu contextual, POS contextual, cobro directo, split endpoint y documentacion.

## Pendientes

- Reservas/bloqueo de mesa.
- Selector profesional de areas.
- Flujo avanzado de cocina por persona.
- Envio a cocina incremental por item para evitar reimpresion/reenviado de items ya enviados.
- Division real de cuenta al separar una mesa con productos asignados.
- Pruebas E2E de escritorio y touch.
- El log `Bad request syntax ('0')` no se pudo reproducir desde las llamadas API de mesas; `request()` mantiene guard contra body `0`.
