# Fase 29 - Mapa contextual de mesas

## Alcance

Esta fase corrige permisos de Configuracion > Funciones y avanza el modo restaurante para que el mapa de mesas sea la vista principal cuando la instalacion opera en `table_service`.

## Permisos de Funciones

- `superadmin` ve y modifica todas las secciones de Funciones.
- `admin` ve solo:
  - Modo de Operacion
  - Inventario
  - Seguridad / Caja
  - Control Rapido
  - Personalizacion visual
- `admin` no recibe ni puede modificar claves sensibles como POS, Pantallas, Reportes, Clientes o Hacienda/DTE.
- Hacienda / DTE sigue siendo solo para `superadmin`.
- El backend filtra el JSON por rol y devuelve `403` si un admin intenta modificar una clave no permitida.

## Mapa de mesas

- En modo mesas, `/pos` muestra un mapa full-screen con barra superior compacta.
- Se removieron los paneles laterales fijos de operacion.
- El mapa permite filtrar por area y estado:
  - Todas
  - Libres
  - Ocupadas
  - En cocina
- Las mesas muestran estado, capacidad/personas e indicador de mesa unida.
- El color activo del tema se usa para bordes y estados visuales.

## Menu contextual

Al tocar o hacer click derecho sobre una mesa se abre un menu contextual. En desktop aparece cerca del cursor; en pantallas pequenas funciona como bottom sheet.

Acciones disponibles segun estado:

- Mesa libre: Nueva orden.
- Mesa ocupada: Agregar productos, Ver cuenta, Cobrar, Enviar a cocina, Mover mesa, Unir mesas, Dividir cuenta y Liberar mesa.
- No se muestra Adjuntar cuenta porque el cobro conjunto real queda pendiente y no debe aparecer como boton roto.

## Nueva orden por personas

El endpoint `/api/orders/tables/sessions/` acepta:

```json
{
  "table_id": 1,
  "guest_count": 4,
  "order_mode": "by_guest",
  "notes": ""
}
```

Tambien acepta `table_ids`, `guests_count`, `table` y `per_person` por compatibilidad.

La respuesta incluye `session_id`, `order_id`, `guest_count`, `status` y la lista de personas. En modo `per_person`, el POS contextual mantiene una persona activa y asigna productos nuevos con `assignedName`.

## Correccion del 500

La causa del 500 era doble:

- Se generaba `order_number` con `count() + 1` y `branch_id=1`, causando colisiones con la restriccion unica por sucursal.
- `TableSessionSerializer` declaraba `tables` pero no lo incluia en `fields`.

Ahora la numeracion usa `Max(order_number) + 1` dentro de transaccion por sucursal activa y el serializer responde correctamente.

## Mover, unir y liberar

Se agregaron endpoints:

- `POST /api/orders/tables/sessions/<id>/move-table/`
- `POST /api/orders/tables/sessions/<id>/release/`

`merge` ya existia y se mantiene para unir mesas libres a una sesion activa.

Liberar mesa solo se permite si no hay saldo pendiente.

## Cobro y pagos divididos

Cobrar desde mesa reutiliza el flujo existente del POS rapido con `pending_order_id` y `mode=pay`. Esto conserva:

- pago completo
- pago parcial
- efectivo con cambio
- multiples metodos
- caja sin inflar efectivo con tarjeta/transferencia

DTE apagado sigue operando como POS local y no debe enviar ni contactar Hacienda.

## Pruebas realizadas

- Smoke de permisos con `APIClient`:
  - superadmin ve todas las claves de Funciones.
  - admin ve solo campos permitidos.
  - admin modificando `pos_enabled` recibe `403`.
  - admin modificando `operation_mode` recibe `200`.
  - admin consultando Hacienda/DTE recibe `403`.
- Smoke de mesas en transaccion con rollback:
  - crear sesion de mesa con 4 personas devuelve `201`.
  - mover mesa devuelve `200`.
  - liberar mesa sin saldo devuelve `200`.
- `python manage.py check` sin errores.
- `npm run build` exitoso.

## Pendientes

- Cobro conjunto real entre varias mesas.
- Historial/auditoria visual de movimientos de mesa.
- Separar mesas unidas.
- Flujo avanzado de cocina por persona.
- Reservas.
- Multi-sucursal real.
- Portal remoto y licencias.
- Pruebas automatizadas de mesas con base de test con permiso `CREATE DATABASE`.
