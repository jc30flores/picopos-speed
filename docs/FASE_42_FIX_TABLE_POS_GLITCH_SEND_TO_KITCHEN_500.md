# Fase 42 - Corrección de POS mesas y envío a cocina

## Alcance

Esta fase corrige dos fallos puntuales del flujo de mesas:

- El flash del POS rápido al entrar desde el menú principal a POS / Mesas.
- El error 500 en `send-to-kitchen` causado por `FOR UPDATE` sobre un `OUTER JOIN` nullable.

No se cambiaron puertos, dominios, Cloudflare, Caddy, systemd, túneles, PWA, favicon, manifest, Lovable, DTE ni `backend/.env`.

## Causa del glitch POS rápido -> mesas

El botón POS / Mesas navegaba a `/pos` sin modo explícito. El componente POS iniciaba con:

- `operationMode = quick_pos`
- `posMode = pos`

Mientras cargaba la configuración real, alcanzaba a renderizar POS rápido y a iniciar estado de POS rápido antes de cambiar al mapa de mesas.

## Corrección de inicialización

- El menú principal navega a `/pos?mode=tables` cuando el servicio de mesas está activo.
- El POS detecta `mode=tables` desde el primer render y arranca en modo mesas.
- Mientras se resuelve configuración para rutas ambiguas, se muestra `Cargando POS...` en vez de POS rápido como fallback.
- El mesero no queda bloqueado por verificación de caja para entrar al mapa.

## Requests DELIVERY en modo mesas

Los requests de productos/descuentos de `DELIVERY` podían dispararse porque el POS rápido inicializaba primero. Ahora:

- En mapa de mesas no se cargan productos/descuentos de POS rápido.
- Al abrir una orden de mesa se selecciona un tipo de servicio de mesa/local si existe.
- Se evita heredar `DELIVERY` como tipo de servicio para órdenes de mesa.

## Causa del 500 send-to-kitchen

El endpoint construía QuerySets con `select_for_update()` y filtros como:

- `product__requires_kitchen=False`
- `product__isnull=True`

Como `OrderItem.product` es nullable, Django generaba un join externo. PostgreSQL no permite aplicar `FOR UPDATE` al lado nullable de un `OUTER JOIN`, por eso lanzaba:

`FOR UPDATE cannot be applied to the nullable side of an outer join`

## Corrección de locking

El endpoint ahora:

1. Obtiene ids de `OrderItem` pendientes sin bloquear joins nullable.
2. Bloquea solo filas base de `OrderItem` con `select_for_update()`.
3. Consulta los productos con cocina activa en una consulta separada.
4. Clasifica en Python:
   - productos que van a cocina;
   - productos que no van a cocina.

Esto mantiene la operación transaccional e idempotente sin usar `FOR UPDATE` sobre relaciones nullable.

## Productos Cocina ON/OFF

- Cocina ON: se marcan como `sent`, aparecen en pantalla de cocina y actualizan la sesión como `sent_to_kitchen`.
- Cocina OFF: se guardan en la cuenta, se marcan como `delivered` para no generar cocina, y no aparecen en pantalla de cocina.
- Mixtos: solo los Cocina ON aparecen en cocina; el usuario ve `Pedido enviado. Algunos productos no van a cocina.`
- Sin pendientes: respuesta controlada en español, sin 500.

## Preservación de carrito y mapa ante fallos

- El carrito se limpia solo después de éxito real de `send-to-kitchen`.
- Si falla el refresh de sesiones o productos listos, el mapa conserva el estado anterior.
- Ya no se reemplazan mesas/sesiones por listas vacías cuando falla una llamada de refresco.

## Pruebas realizadas

- Compilación Python de `table_views.py` y `test_table_send_to_kitchen.py`.
- Smoke transaccional en `roseedb` con rollback:
  - producto Cocina ON: `200`, `sent_count=1`, `saved_count=0`;
  - producto Cocina OFF: `200`, `sent_count=0`, `saved_count=1`;
  - productos mixtos: `200`, `sent_count=1`, `saved_count=1`;
  - doble POST: `200`, `sent_count=0`, `saved_count=0` en el segundo envío;
  - orden vacía: `400` controlado con `No hay productos pendientes para enviar.`;
  - kitchen summary respondió `200`.
- Se agregó cobertura de smoke para:
  - producto Cocina ON;
  - producto Cocina OFF;
  - productos mixtos;
  - orden vacía;
  - doble POST sin duplicar.

La ejecución de tests Django quedó bloqueada porque el usuario de PostgreSQL no tiene permiso para crear la base de test.

## Pendientes y riesgos

- Validación manual en navegador con usuario Mesero sigue siendo necesaria para confirmar que Network ya no muestra `DELIVERY` al abrir `/pos?mode=tables`.
- La suite Django debe ejecutarse en un entorno con permisos de creación de base de test o con una base de test previamente provisionada.
