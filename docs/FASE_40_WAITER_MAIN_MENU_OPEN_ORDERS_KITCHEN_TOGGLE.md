# Fase 40 - Mesero, ordenes abiertas y productos sin cocina

## Alcance

Esta fase corrige flujos operativos del rol Mesero y reglas de cocina sin tocar infraestructura, PWA, dominios, puertos, Caddy, Cloudflare, systemd ni configuracion de base de datos.

## Causas encontradas

- El Mesero seguia aterrizando directamente en `/pos`; eso saltaba el centro de control y no lo llevaba al panel de marcaje.
- El proveedor de asistencia trataba al Mesero como rol con bypass, por lo que no se validaba el flujo de entrada/salida.
- La allowlist backend del rol Mesero permitia consultar asistencia del dia, pero no permitia ejecutar clock-in, break ni clock-out.
- Las operaciones de unir, mover y separar mesa estaban amarradas al mismo permiso de cajero/gerente/admin usado para liberar mesa.
- La liberacion forzada de mesa solo aceptaba PIN admin/superadmin y siempre cancelaba la orden, incluso cuando la mesa ya no tenia saldo pendiente.
- `orders/pending` listaba cualquier orden `is_pending=True`, incluyendo ordenes sin items, total 0, pagadas o anuladas.
- El contador de cuentas abiertas usado por caja tenia una query distinta y podia contar pendientes invalidas.
- El modelo `Product` ya tenia `requires_kitchen`; faltaba un switch rapido en la tabla de productos y faltaba respetar ese campo en resumen/envio de cocina.
- El serializer de items no exponia `requires_kitchen`, por lo que el frontend no podia distinguir "Sin cocina" de "Pendiente de enviar".

## Mesero en menu principal y marcaje

- `waiter` ahora puede entrar a `/`.
- El login de Mesero redirige al centro de control.
- El Mesero ya no tiene bypass de asistencia en frontend.
- La allowlist backend de Mesero permite:
  - `/api/employees/attendance/today/`
  - `/api/employees/attendance/clock-in/`
  - `/api/employees/attendance/break-start/`
  - `/api/employees/attendance/break-end/`
  - `/api/employees/attendance/clock-out/`
  - `/api/employees/me/attendance/`
- En el menu principal, el Mesero ve `POS / Mesas` y `Cocina solo lectura`.
- No se exponen modulos administrativos al Mesero desde el menu principal.

## Permisos de Mesero en mesas

El Mesero puede:

- Abrir mapa de mesas.
- Crear orden.
- Agregar productos.
- Ver cuenta.
- Imprimir cuenta local/precuenta.
- Mover mesa.
- Unir mesa.
- Separar mesa.
- Enviar productos a cocina.
- Ver cocina.
- Marcar productos terminados como servidos.

El Mesero no puede:

- Cobrar.
- Abrir caja.
- Cerrar caja.
- Liberar mesa directamente.
- Marcar productos como terminados desde cocina.

## Liberar mesa con PIN supervisor

- La opcion `Liberar mesa` puede aparecer al Mesero.
- Si el Mesero la presiona, se abre `Autorizacion requerida`.
- Se solicita motivo obligatorio y PIN supervisor.
- PIN autorizado:
  - cajero
  - gerente/manager
  - admin
  - superadmin
- PIN invalido devuelve `PIN no autorizado.`
- Si hay saldo pendiente, la cuenta se cancela/anula con auditoria.
- Si no hay saldo pendiente, la mesa se cierra/libera sin anular la orden pagada.
- La auditoria registra `requested_by`, `authorized_by`, motivo, sesion/orden y saldo cancelado.

## Ordenes abiertas

`/api/orders/pending/` ahora excluye:

- total `0.00`
- `amount_due_cents <= 0`
- ordenes sin items
- pagadas
- anuladas/voided
- refunded full
- canceladas
- entregadas/cerradas operativamente

Tambien se bloquea guardar una orden abierta vacia o con total `$0.00` con el mensaje:

`No se puede guardar una orden abierta sin productos o con total $0.00.`

El contador de cuentas abiertas usado por caja y cierre automatico se alineo con la misma regla.

## Columna Cocina en productos

- Se reutilizo el campo existente `requires_kitchen`.
- No se creo migracion nueva.
- La tabla `Productos del Menu` ahora tiene columna `Cocina`.
- El switch actualiza solo `requires_kitchen`.
- Mensajes:
  - `Producto se enviara a cocina.`
  - `Producto no se mostrara en cocina.`

## Productos que no van a cocina

Si `requires_kitchen=false`:

- El producto se vende normalmente.
- Aparece en orden, cuenta, ticket, recibo, reportes y totales.
- No aparece en resumen de cocina.
- No aparece en pantalla de cocina.
- No genera burbuja de listo para servir.
- No se cuenta como pendiente/en cocina/listo.
- En cuenta de mesa se muestra como `Sin cocina`.
- Si una mesa solo tiene productos sin cocina, `Enviar a cocina` guarda la cuenta y devuelve:
  `Orden guardada. No hay productos para cocina.`

Si una orden tiene productos mixtos:

- Solo los productos con `requires_kitchen=true` se envian y aparecen en cocina.
- Los productos sin cocina se conservan en la cuenta y totales.

## Pruebas realizadas

- `git diff --check`: OK.
- `backend/venv/bin/python backend/manage.py check`: OK.
- `backend/venv/bin/python backend/manage.py migrate`: OK, sin migraciones nuevas aplicadas.
- DB confirmada con shell: `roseedb` / `roseedb`.
- `npm run build`: OK.
- `npm run lint -- --max-warnings=0`: falla por deuda previa de lint en archivos no relacionados (`any`, hooks, disables, require en tailwind).
- Smoke read-only de ordenes abiertas:
  - `valid_pending_count`: 1
  - `invalid_returned_count`: 0
- Smoke read-only de resumen cocina:
  - `non_kitchen_items_in_summary`: 0
- Smoke read-only contador caja:
  - contador global: 1
  - sucursal 1: 1
- Logs recientes:
  - endpoints publicos `/api/public/appearance/`, `/api/public/pwa/metadata/`, favicon responden 200/304.
  - no se observaron tracebacks recientes.
  - se observan 403 de `/api/settings/dte/` por acceso no autorizado a configuracion DTE; no pertenecen a endpoints publicos ni a esta correccion.

## Pendientes y riesgos

- No se hicieron pruebas UI completas con credenciales reales de Mesero/Cajero/Admin desde navegador en esta corrida.
- `migrate` reporta cambios de modelos existentes en `employees`, `inventory`, `menu` sin migracion; no se generaron migraciones porque esta fase reutiliza `requires_kitchen` existente.
- El lint general del frontend ya tiene deuda amplia previa.
- La liberacion de mesa por Mesero depende de que los usuarios supervisores tengan PIN activo y valido.
