# Fase 44 - Fix kitchen complete 500 y polling de mesas

## Causa del 500 en Terminado

El endpoint `POST /api/kitchen/items/<id>/complete/` usaba:

```python
OrderItem.objects.select_for_update().select_related("order", "product").filter(id=pk).first()
```

`OrderItem.product` es nullable. Django generaba un `LEFT OUTER JOIN` hacia `product` y PostgreSQL rechazaba el `FOR UPDATE` sobre el lado nullable del join con:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

## Corrección aplicada

El endpoint ahora bloquea primero solo la fila base de `OrderItem`:

```python
item = OrderItem.objects.select_for_update().filter(id=pk).first()
```

Después valida si el producto requiere cocina con una consulta separada a `Product`, y solo al final recarga relaciones necesarias para serializar (`table_guest`, `applied_modifiers`). Esto evita combinar `FOR UPDATE` con joins nullable.

También se corrigió el flujo de servir listos por sesión para no bloquear un queryset derivado de `_kitchen_items_queryset()` con join a `product`. Ahora bloquea `OrderItem` por `order_id` y `kitchen_status`, y valida `requires_kitchen` en una consulta separada.

## Otros select_for_update revisados

Se revisaron usos en:

- `send-to-kitchen`: ya tenía patrón seguro de lock base sobre `OrderItem` y consulta separada a `Product`.
- `complete kitchen item`: corregido.
- `serve item` y `serve-ready`: corregido el lock de listos por sesión.
- `release`, `force-release`, `move`, `merge`, `split`: bloquean filas base (`TableSession`, `RestaurantTable`, `TableSessionTable`) sin joins nullable.
- `payments`, `cashier`, `inventory`: no quedó un patrón de `select_for_update().select_related(...)` vulnerable en órdenes/cocina; inventario usa `select_related` sobre FK no nullable o `prefetch_related`, que no causa el outer join nullable del incidente.

## Permisos de cocina

- Cocina, admin, manager y superadmin pueden marcar `Terminado`.
- Mesero puede ver cocina, pero no puede marcar `Terminado`.
- Si Mesero intenta completar un producto, la API responde `403` con: `El rol Mesero solo puede visualizar cocina.`
- Mesero mantiene permiso para marcar `Servido` cuando el producto ya está terminado.

## Bug intermitente al volver al mapa

La ruta de edición de mesa se abría como:

```text
/pos?pending_order_id=<id>&mode=edit
```

Durante la hidratación del pedido, el frontend reemplazaba la URL por `/pos`. Luego la carga de runtime settings podía aplicar el default `table_map` y ejecutar `setPosMode("tables")`, sacando al usuario de la pantalla de productos sin acción explícita.

## Protección del modo edición

- La URL con `pending_order_id` y `mode=edit` o `mode=pay` se conserva mientras se hidrata la orden.
- Runtime settings ya no fuerza mapa cuando existe una ruta activa de edición/pago de orden.
- `Volver a mesas` marca una bandera explícita de usuario y navega a `/pos?mode=tables`.
- Polling de sesiones/listos no navega ni cambia `posMode`.
- Los callbacks de polling usan refs como fallback para no depender de cierres viejos ni reiniciar intervalos por cada actualización.

## Polling

- Mapa de mesas mantiene polling de sesiones y ready-summary cuando `posMode === "tables"`.
- Edición de productos de mesa no activa el polling del mapa porque `posMode` se mantiene en `pos`.
- Cocina mantiene polling, pero evita requests solapados.
- Botones `Terminado` y `Servido` se bloquean mientras hay request en curso para impedir duplicados.

## Pruebas realizadas

- Se agregó cobertura backend para completar productos de cocina, idempotencia, mesero 403, ready-summary y servir productos terminados.
- El intento de correr `manage.py test` no pudo crear DB de prueba por permisos PostgreSQL: `permission denied to create database`.
- Smoke transaccional sobre `roseedb` con rollback: OK. Validó `complete` 200, repetición 200 idempotente, ready-summary con el item listo, Mesero 403 y `serve` 200.
- `backend/manage.py check`: OK.
- `backend/manage.py migrate`: OK, sin migraciones aplicadas. Django reportó deuda previa de modelos en `employees`, `inventory` y `menu` sin migración.
- Confirmación DB posterior: `roseedb` / `roseedb`.
- `backend/manage.py ensure_superadmin`: OK.
- `npm run build`: OK.
- `npm run lint -- --max-warnings=0`: falla por deuda previa extensa (`any`, hooks deps, disables sin uso, require en `tailwind.config.ts`). No se identificó un error nuevo por esta iteración.

## Pendientes y riesgos

- Las pruebas manuales completas en navegador dependen de credenciales/usuarios locales disponibles.
- La DB de prueba requiere permisos `CREATEDB` o una base de test precreada para ejecutar el suite Django normal.
- Queda deuda previa de lint frontend y migraciones pendientes ajenas al cambio.
