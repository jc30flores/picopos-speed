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
- Cerrar

Separar mesa y reservas quedan pendientes porque no hay flujo completo habilitado.

## Nueva orden y agregar productos

`Nueva orden` abre el dialogo de personas, modo de orden (`Orden completa` o `Por persona`) y notas. Al iniciar, se crea la sesion y se abre el POS contextual de esa mesa.

`Agregar productos` reemplaza a `Nueva orden` cuando ya existe una sesion activa. Reutiliza el POS rapido con contexto de mesa, persona activa en modo `per_person`, guardado y regreso al mapa.

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

`Cobrar` reutiliza el flujo existente con `pending_order_id` y `mode=pay`, conservando pagos divididos, pagos parciales y pago completo. Al completar el pago, el backend cierra la sesion de mesa para que el mapa la muestre libre. Si el pago queda parcial, la sesion queda `partially_paid`.

DTE apagado sigue registrando el pago localmente y no contacta Hacienda.

## Unir mesas

`Unir mesa` entra en modo seleccion dentro del mapa:

1. muestra `Selecciona la mesa que deseas unir con Mesa X`
2. resalta destinos validos
3. abre modal propio `Unir mesas`
4. une la mesa a la sesion existente o crea una sesion agrupada si ambas mesas estaban libres

El backend valida mesas inactivas, ids invalidos y conflictos con otra sesion activa para evitar 500.

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

`Enviar cocina` se muestra para sesiones con orden activa. Si la orden esta vacia, el backend responde con mensaje controlado. Si procede, marca la orden como enviada y la mesa pasa a `En cocina`.

## Pendientes

- Separar mesas unidas.
- Reservas/bloqueo de mesa.
- Selector profesional de areas.
- Flujo avanzado de cocina por persona.
- Pruebas E2E de escritorio y touch.
- El log `Bad request syntax ('0')` no se pudo reproducir desde las llamadas API de mesas; `request()` mantiene guard contra body `0`.
