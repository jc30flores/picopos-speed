# Fase 41 - Corrección de carrito de mesas y envío a cocina

## Alcance

Esta fase corrige el flujo del POS de mesas al agregar productos, quitar líneas pendientes y enviar a cocina. No cambia base de datos, puertos, dominios, Cloudflare, Caddy, systemd, DTE, PWA, favicon ni branding.

## Causas raíz

- El toast `No se puede guardar una orden abierta sin productos o con total $0.00.` venía del endpoint de cuentas abiertas cuando una mesa sin productos intentaba guardarse como pendiente. Para mesas vacías ahora se descarta silenciosamente la orden vacía y el frontend vuelve al mapa sin mostrar error.
- Los productos desaparecían porque el autosave de mesa reemplazaba el carrito local con los ítems devueltos por backend filtrados solo como pendientes de cocina. Eso eliminaba del `Pedido Actual` productos sin cocina y cualquier línea que el backend todavía no devolviera como pendiente.
- La autorización de eliminación se disparaba al enviar a cocina porque el backend comparaba la orden completa contra el payload recibido. Si faltaba una línea por un refresh viejo, scope de persona o producto sin cocina, lo trataba como eliminación protegida.
- La consulta de disponibilidad de inventario daba 403 al Mesero porque la ruta estaba permitida por el control de roles, pero la vista DRF exigía rol de cajero/manager/admin.

## Cambios realizados

- El POS de mesas mantiene el carrito local visible después de autosave y solo actualiza `sourceOrderItemId` con los IDs nuevos del backend.
- `Enviar a cocina` guarda primero la orden, conserva el carrito si falla, y limpia los productos pendientes solo después de éxito real.
- Los botones del flujo de carrito, extras y envío tienen `type="button"` para evitar submits implícitos.
- Quitar un producto pendiente/no enviado ya no pide PIN ni autorización.
- El backend bloquea eliminación por ítem, no por estado general de la orden.
- Los ítems enviados, terminados o servidos siguen requiriendo autorización si un rol no privilegiado intenta removerlos.
- Los ítems pagados se bloquean con: `Este producto ya fue pagado. Usa devolución o anulación.`
- Los productos con Cocina apagado se guardan en la cuenta, se marcan internamente como `delivered` al enviar, no aparecen en cocina y no generan burbuja de listo.
- `inventory/cart-availability` permite Mesero porque es una consulta operativa de POS, no administración de inventario.

## Reglas actuales

- Mesa sin productos: volver a mesas no guarda nada y no muestra toast de error.
- Producto pendiente/no enviado: se puede aumentar, disminuir o quitar sin autorización.
- Producto enviado a cocina, terminado o servido: requiere autorización para remover si el usuario no es admin/manager/superadmin.
- Producto pagado: no se elimina desde este flujo.
- Producto con Cocina encendida: al enviar, aparece en cocina.
- Producto con Cocina apagada: al enviar, queda en cuenta/ticket/totales, no aparece en cocina.

## Pruebas y validación

- `git diff --check` en archivos de la fase: OK.
- `backend/venv/bin/python backend/manage.py check`: OK.
- `backend/venv/bin/python backend/manage.py migrate`: OK, sin migraciones nuevas. Django mantiene aviso previo de modelos no migrados en `employees`, `inventory`, `menu`.
- Confirmación DB: `roseedb` / `roseedb`.
- `backend/venv/bin/python backend/manage.py ensure_superadmin`: OK.
- `cd frontend && npm run build`: OK.
- `npm run lint -- --max-warnings=0`: falla por deuda previa amplia (`any`, hooks y fast-refresh); no se agregó deuda nueva para esta fase.
- Tests Django enfocados no corrieron porque PostgreSQL no permite crear base de test: `permission denied to create database`.
- Logs revisados: sin tracebacks nuevos; se detectaron 403 previos de `inventory/cart-availability/` para Mesero y se corrigió el permiso.

## Pendientes y riesgos

- Validar manualmente en navegador el caso completo Kevin/Niño con producto cocina ON, producto cocina OFF, quitar pendiente y enviar por persona.
- La suite Django requiere permisos para crear base de test o una base de test precreada.
- Queda deuda previa de lint fuera de esta fase.
