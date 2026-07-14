# FASE 35 - Flujo Cocina, Mesero y Pedidos Listos

## Objetivo

Completar el flujo operativo de restaurante entre cocina, mesero y mesa:

- Cocina prepara productos enviados desde mesa.
- Cocina marca productos como `Terminado`.
- El mapa de mesas notifica al mesero con una burbuja de productos listos.
- El mesero marca productos como `Servido` desde el mapa de mesas.
- La cuenta de mesa conserva estados claros: pendiente, en cocina, terminado y servido.

## Rol Mesero

Se agrega el rol backend `waiter` con etiqueta visible `Mesero`.

Permisos operativos:

- Acceder a POS y mapa de mesas.
- Crear o continuar sesiones de mesa.
- Agregar productos a la mesa usando el flujo POS contextual.
- Ver pantalla de cocina en modo lectura.
- Ver cuenta de mesa.
- Marcar productos terminados como servidos.

Restricciones:

- No accede a configuración técnica.
- No accede a DTE/Hacienda.
- No accede a reportes sensibles ni caja administrativa.
- No marca productos como `Terminado` en cocina.
- No administra mesas, inventario, menú ni funciones.

## Permisos Por Rol

Ver cocina:

- Superadmin
- Admin
- Gerente
- Cocina
- Mesero

Marcar `Terminado`:

- Superadmin
- Admin
- Gerente
- Cocina

Marcar `Servido`:

- Superadmin
- Admin
- Gerente
- Cocina
- Mesero

Mapa/POS de mesas:

- Superadmin
- Admin
- Gerente
- Cajero
- Mesero

## Estados

Estados usados en los productos de mesa:

- `pending`: pendiente de enviar.
- `sent`: en cocina / en preparación.
- `ready`: terminado / listo para servir.
- `delivered`: servido.

`Terminado` no marca servido automáticamente. `Servido` solo ocurre cuando el producto se entrega a la mesa.

## Cocina

La pantalla `/kitchen` abre por defecto en `En preparación`, mostrando productos con estado `sent`.

La cocina se refresca automáticamente cada 5 segundos mientras la pestaña está visible. También conserva el botón manual `Actualizar`.

El rol Mesero puede ver cocina, pero el botón `Terminado` no aparece como acción disponible. En su lugar se muestra un mensaje operativo: `Solo cocina puede marcar como terminado.`

## Resumen de Pedidos Listos

Se agrega endpoint:

```text
GET /api/orders/tables/ready-summary/
```

Respuesta:

```json
{
  "tables": [
    {
      "table_id": 1,
      "table_ids": [1],
      "table_name": "Mesa 1",
      "session_id": 8,
      "order_id": 9,
      "ready_count": 2,
      "group_label": null,
      "items": []
    }
  ],
  "total_ready": 2
}
```

El mapa usa este resumen para dibujar burbujas sobre mesas con productos listos.

## Burbuja En Mesa

Cuando una mesa o grupo tiene productos `ready`, se muestra una burbuja redonda roja en la esquina superior de la mesa.

El número representa la suma de cantidades listas para servir.

Si el mesero cierra el modal sin servir, la burbuja permanece. Si sirve todo, desaparece.

## Modal Pedidos Listos Para Servir

Al tocar una mesa con productos listos, el sistema abre primero el modal `Pedidos listos para servir`.

El modal muestra:

- Mesa o grupo.
- Total de productos listos.
- Producto.
- Cantidad.
- Persona.
- Modificadores.
- Tiempo desde que cocina lo marcó terminado.
- Botón `Servir` por producto.
- Botón `Servir todo`.
- Botón `Más opciones`.
- Botón `Cerrar`.

## Endpoints Para Servir

Producto individual:

```text
POST /api/kitchen/items/<id>/serve/
POST /api/orders/items/<id>/serve/
```

Sesión completa:

```text
POST /api/orders/tables/sessions/<id>/serve-ready/
```

El endpoint masivo acepta opcionalmente:

```json
{
  "item_ids": [1, 2, 3]
}
```

Ambos endpoints son idempotentes en productos ya servidos o devuelven una respuesta clara si el producto no está terminado.

## Cuenta De Mesa

La cuenta conserva filtros por estado:

- Pendiente de enviar.
- En cocina.
- Terminados.
- Servidos.
- Pagados.

El estado `ready` se muestra como `Terminado / listo para servir`. El estado `delivered` se muestra como `Servido`.

## Auto Refresh

Polling aplicado:

- Cocina: cada 5 segundos mientras la pestaña está visible.
- Mapa de mesas: cada 5 segundos mientras la pestaña está visible y se está viendo el mapa.
- Cuenta de mesa: refresca al abrir y después de servir/pagar.

Los intervalos se limpian al desmontar para evitar loops.

## Pruebas Realizadas

- Confirmar rama y base `roseedb`.
- Validar permisos con roles mesero/cocina/admin.
- Validar endpoint `ready-summary`.
- Validar endpoints `serve`.
- Validar build frontend.
- Validar migraciones.

## Pendientes

- No se implementa deshacer para un producto marcado como servido.
- No se agregaron campos `served_by` o `completed_by` porque el modelo actual no los tenía; se conserva timestamp existente.
- Si se requiere trazabilidad por usuario de servido, debe agregarse en una fase separada con migración de campos.
