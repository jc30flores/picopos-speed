# Fase 29 - Mapa contextual de mesas

## Alcance

Esta fase deja el POS de `table_service` como una superficie operativa de salon. El editor y la configuracion de mesas quedan fuera del POS; `/pos` se enfoca en mapa, estados y acciones por mesa.

## UX full-screen

- `/pos` en modo mesas renderiza un mapa full-screen.
- Fuera del mapa solo queda el boton minimalista `Menu`, fijo en la esquina superior izquierda, con icono `Home`, fondo `popover` y contraste para claro/oscuro.
- No se muestran `Editor de mesas`, selector de area, `Todas las areas`, filtros por estado ni paneles laterales.
- Los contadores quedan dentro del mapa, arriba a la derecha:
  - `Libres: X`
  - `Ocupadas: X`
  - `En cocina: X`, clickeable para abrir resumen de cocina
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
- altura maxima `calc(100dvh - 1.5rem)` y scroll interno para que no se salga de pantalla

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
- Liberar mesa con confirmacion propia; si hay saldo pendiente usa liberacion forzada con autorizacion
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
- No aparecen controles del POS rapido: reloj, tipo de pedido, cliente, transacciones de caja, reimpresion, refrescar, impresion de ticket ni cobro como CTA.
- Si hay productos sin guardar, `Volver a mesas` abre un modal propio con `Guardar y volver`, `Volver sin guardar` y `Cancelar`.
- El CTA principal ya no es `Cobrar`; es `Enviar a cocina` cuando hay productos de cocina o `Guardar orden` cuando no aplica cocina.
- La accion secundaria visible en el panel es `Ver cuenta`; el cobro se hace desde mapa o desde cuenta.

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
- estado de cocina por producto: pendiente, en cocina, listo o entregado

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

`Liberar mesa` abre modal propio del sistema.

Sin saldo pendiente:

- libera normal con confirmacion simple
- cierra la sesion y la mesa queda disponible

Con saldo pendiente:

- admin/superadmin puede confirmar con motivo obligatorio
- cajero u otro rol debe ingresar PIN de admin/superadmin y motivo obligatorio
- endpoint: `POST /api/orders/tables/sessions/<id>/force-release/`
- la orden queda `canceled` y `financial_status=voided`
- pagos parciales existentes se conservan y no se toca caja
- se cancela el saldo pendiente ajustando `amount_due_cents` a lo ya pagado
- se registra auditoria `table_session.force_release` con solicitante, autorizador, motivo, saldo cancelado, pago conservado, mesa/sesion/orden
- no genera DTE ni contacta Hacienda

## Confirmaciones del sistema

El flujo de mesas no usa `window.confirm`, `alert` ni `prompt`. Las confirmaciones de unir, mover y liberar usan `AlertDialog` de GastroPOSV con botones `Cancelar` y accion principal.

## Enviar cocina

`Enviar cocina` se muestra para sesiones con orden activa y tambien es el CTA principal del POS contextual cuando los productos requieren cocina. Si la orden esta vacia, el backend responde con mensaje controlado. Si procede, guarda los items, marca la orden como enviada y la mesa pasa a `En cocina`.

Cada `OrderItem` tiene estado de cocina:

- `pending`: pendiente de enviar
- `sent`: en cocina
- `ready`: listo
- `delivered`: entregado

El endpoint de mesa envia solo items `pending`. Si no hay nuevos productos, responde `No hay productos nuevos para enviar.` y no duplica cocina.

Cuando no hay productos de cocina, el CTA principal es `Guardar orden`; guarda los items en la mesa sin abrir cobro.

## Ordenes guardadas por mesa

En POS rapido, el boton de ordenes guardadas conserva el comportamiento existente: con carrito vacio abre `/open-orders`; con productos, guarda la orden.

En POS contextual de mesa, ese boton cambia a `Ver cuenta` y abre el resumen de la mesa/grupo:

- productos por persona o cuenta general
- productos enviados a cocina
- productos pendientes de enviar
- productos listos/entregados
- totales y saldo
- acciones para agregar productos o cobrar

## Vista cocina

El contador `En cocina: X` del mapa abre el modal `Ordenes en cocina`.

La vista muestra por mesa/grupo:

- mesa o grupo
- personas/clientes segun `assigned_name`
- productos pendientes, en cocina, listos y entregados
- total por persona
- total de mesa y saldo
- acciones `Listo`, `Entregado`, `Ver cuenta` y `Cobrar`

Endpoints:

- `GET /api/orders/tables/kitchen-summary/`
- `POST /api/orders/items/<id>/mark-ready/`
- `POST /api/orders/items/<id>/mark-delivered/`

## Viewport del mapa y menu contextual

El mapa operativo ahora usa un viewport fijo de pantalla completa con pan/zoom interno. La pagina no depende de scroll general para encontrar mesas.

Auto-fit inicial:

- calcula el bounding box real de todas las mesas visibles
- considera ancho, alto y margen extra para mesas rotadas
- calcula escala con padding responsive
- limita zoom inicial entre `0.35` y `1.12`
- centra el contenido con `translate3d(...) scale(...)`

Responsive:

- `ResizeObserver` recalcula el fit cuando cambia el contenedor
- no resetea el mapa si el usuario ya hizo pan o zoom manual
- doble click en el fondo ajusta el mapa
- boton `Ajustar` recentra y vuelve a mostrar todo el salon

Pan/zoom:

- wheel hace zoom sobre el punto del cursor
- arrastrar fondo mueve el mapa
- la superficie usa `touch-action: none` para evitar scroll de pagina durante pan

Menu contextual:

- se renderiza como capa fija sobre el mapa
- se mide y se recoloca contra el viewport con margen seguro de 16px
- si no cabe a la derecha o abajo, se mueve dentro de pantalla
- usa `max-height` y scroll interno con `overscroll-behavior: contain`
- en pantallas pequenas o puntero touch se muestra como bottom sheet con altura maxima cercana a `78dvh`
- el encabezado de mesa/grupo queda sticky mientras se hace scroll
- recalcula posicion en `resize` y `orientationchange`

Modo claro/oscuro:

- la superficie sigue usando variables de tema (`background`, `muted`, `card`, `popover`, `border`, colores primarios)
- el boton `Menu`, labels y `Ajustar` son flotantes y no mueven el contenido
- el menu contextual usa `bg-popover`/`text-popover-foreground`, por lo que mantiene contraste en ambos modos

## Pruebas realizadas

- `backend/venv/bin/python backend/manage.py check`
- `cd frontend && npm run build`
- Smoke de compilacion del flujo: mapa, menu contextual, POS contextual limpio, cobro directo, split endpoint, force release, resumen de cocina y documentacion.
- Smoke de viewport: menu contextual con clamp/scroll interno, auto-fit por bounding box, ResizeObserver y boton `Ajustar`.

## Pendientes

- Reservas/bloqueo de mesa.
- Selector profesional de areas.
- Flujo avanzado de cocina por persona.
- Division real de cuenta al separar una mesa con productos asignados.
- Impresion real de comandas incrementales por item nuevo.
- Pruebas E2E de escritorio y touch.
- El log `Bad request syntax ('0')` no se pudo reproducir desde las llamadas API de mesas; `request()` mantiene guard contra body `0`.
