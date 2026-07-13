# Fase 29 - Mapa contextual de mesas

## Alcance

Esta fase deja el POS de `table_service` como una superficie operativa de salon. El editor y la configuracion de mesas quedan fuera del POS; `/pos` se enfoca en mapa, estados y acciones por mesa.

## UX full-screen

- `/pos` en modo mesas renderiza un mapa full-screen oscuro.
- Fuera del mapa solo queda el boton `Volver al menu principal`, fijo en la esquina superior izquierda.
- No se muestran `Editor de mesas`, selector de area, `Todas las areas`, filtros por estado ni paneles laterales.
- Los contadores quedan dentro del mapa, arriba a la derecha:
  - `Libres: X`
  - `Ocupadas: X`
  - `En cocina: X`
- El mapa usa scroll/pan propio y mantiene fondo oscuro tambien en tema claro.
- Las mesas usan variables del tema para bordes y resaltados: `--color-primary`, `--color-primary-border`, `--color-primary-surface` y `--color-primary-contrast`.

## Menu contextual

Al tocar una mesa se abre un menu contextual. En desktop aparece cerca del cursor; en pantallas pequenas funciona como bottom sheet. Se cierra tocando fuera o con `Esc`.

El menu muestra:

- nombre de mesa
- estado: libre, ocupada, en cocina o parcial
- personas cuando hay sesion
- total cacheado si existe
- indicador `Unida` cuando la sesion incluye mas de una mesa

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
- Liberar mesa cuando no hay saldo pendiente
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
3. pide confirmacion `Unir Mesa X con Mesa Y`
4. une la mesa a la sesion existente o crea una sesion agrupada si ambas mesas estaban libres

El backend valida mesas inactivas, ids invalidos y conflictos con otra sesion activa para evitar 500.

## Mover mesa

`Mover mesa` entra en modo seleccion:

1. muestra `Selecciona la mesa destino`
2. resalta mesas libres
3. pide confirmacion `Mover orden de Mesa X a Mesa Y`
4. mueve la sesion al destino y actualiza la referencia de la orden

No se pierden productos, personas ni pagos porque se mueve la relacion de mesa, no la orden.

## Liberar mesa

`Liberar mesa` llama al endpoint de release. Si hay saldo pendiente, el backend responde con `No puedes liberar una mesa con saldo pendiente.` y no borra datos de venta. Si la orden ya esta pagada o no hay orden con saldo, la sesion se cierra.

## Enviar cocina

`Enviar cocina` se muestra para sesiones con orden activa. Si la orden esta vacia, el backend responde con mensaje controlado. Si procede, marca la orden como enviada y la mesa pasa a `En cocina`.

## Pendientes

- Separar mesas unidas.
- Reservas/bloqueo de mesa.
- Selector profesional de areas.
- Flujo avanzado de cocina por persona.
- Pruebas E2E de escritorio y touch.
