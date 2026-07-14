# Fase 30 - permisos de cocina y Open Orders por modo

## Alcance

Esta iteracion corrige el uso operativo de cocina y limita el modal de ordenes abiertas al flujo de POS rapido. No cambia base de datos, puertos, dominios, Caddy, Cloudflare, systemd ni tuneles.

## Permisos de cocina

Se consolidaron helpers de permisos:

- `user_is_kitchen(user)`
- `user_can_view_kitchen(user)`
- `user_can_manage_kitchen_items(user)`

Pueden operar cocina y marcar productos como `Terminado`:

- `superadmin`
- `admin`
- `manager`
- `kitchen` / `cocina`

El endpoint `POST /api/kitchen/items/<id>/complete/` usa permiso operativo de cocina, valida que el item exista y que ya haya sido enviado a cocina. Si el item ya esta `ready`, responde de forma idempotente con el estado actual. Si ya fue servido, responde con `ALREADY_SERVED`; si aun no fue enviado, responde con `NOT_IN_KITCHEN`.

El middleware de acceso por rol permite al rol cocina consultar:

- `/api/kitchen/*`
- `/api/orders/tables/kitchen-summary/`
- `/api/orders/active/`
- `/api/core/feature-flags/`
- endpoints auxiliares de servicio, sucursal e impresion requeridos por la pantalla.

## Asistencia en `/kitchen`

El rol `kitchen` omite la validacion de asistencia del frontend. Asi `/kitchen` no llama innecesariamente a `/api/employees/attendance/today/`, no genera 403 y no muestra el toast `No se pudo validar asistencia: Sin permisos`.

La logica de asistencia se mantiene para los roles que si la requieren.

## Open Orders

El modal de ordenes abiertas ahora solo puede aparecer cuando el usuario esta realmente en POS rapido:

- `operation_mode = quick_pos`
- `operation_mode = both` con entrada rapida activa
- `/pos?mode=quick`

No aparece en:

- mapa de mesas
- `table_service`
- `table_order`
- `mode=edit`
- `mode=pay`
- flujos con `session_id`
- modal de pago

El texto del modal quedo en espanol.

## Entrada a POS rapido en modo `both`

Cuando `operation_mode = both` y la entrada por defecto es mapa de mesas, el mapa muestra un boton discreto `POS rapido`. El boton navega a `/pos?mode=quick` para abrir el POS rapido real sin contexto de mesa.

## Pruebas

Validaciones esperadas:

- usuario cocina puede entrar a `/kitchen`
- no se dispara `attendance/today` para rol cocina
- `POST /api/kitchen/items/<id>/complete/` permite rol cocina, admin, manager y superadmin
- cajero no opera items de cocina
- modo mesas no muestra modal de ordenes abiertas
- modo `both` con mapa muestra boton `POS rapido`
- modo `quick_pos` conserva el modal de ordenes abiertas si aplica

## Pendientes

La prueba manual real de marcar `Terminado` debe hacerse con un pedido de prueba enviado a cocina para evitar modificar ordenes reales existentes.
