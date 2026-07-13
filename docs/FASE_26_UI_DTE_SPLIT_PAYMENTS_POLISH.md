# Fase 26 - UI, DTE y pagos divididos

## Alcance

Esta fase pule la experiencia de Configuración, limpia el menú principal, refuerza DTE apagado/pendiente como POS local y corrige pagos divididos con varios métodos. El trabajo se validó sobre `gastrodb`; `gallo_db` no se tocó.

## Apariencia

- La vista previa usa un color en borrador.
- El sistema completo no cambia hasta presionar **Aplicar**.
- Se eliminó el botón **Probar color**.
- El botón **Aplicar** queda deshabilitado si no hay cambios o el HEX es inválido.
- La paleta recomendada incluye verde, azul, teal, celeste, turquesa, morado, fucsia, rosado, rojo, naranja, ámbar/dorado, gris y negro suave.
- El backend devuelve variables adicionales:
  - `--color-primary-muted`
  - `--color-primary-surface`

## Menú principal

- El botón DTE ya no aparece en el menú principal.
- El botón **Pedidos abiertos** ya no aparece en el menú principal.
- Las rutas internas pueden seguir existiendo para flujos ya integrados, pero no se presentan como módulos principales.

## DTE / Hacienda

- Configuración > Hacienda/DTE centraliza API, emisor, dirección fiscal, sucursal principal y correlativos.
- Se agregó alias explícito `POST /api/settings/dte/correlatives/initialize/`.
- `GET /api/core/feature-flags/` expone:
  - `dte_enabled`
  - `dte_visible`
  - `can_view_dte`
  - `can_manage_dte`
  - `can_send_dte`
  - `hacienda_enabled`
- DB tiene prioridad para runtime DTE; una configuración DB incompleta no se completa con `.env`.
- La prueba de conexión desde UI no contacta Hacienda si faltan datos mínimos.

## Correlativos / Last Number

- Superadmin puede inicializar correlativos.
- Superadmin puede editar `last_number` con motivo obligatorio.
- Si se baja el número, se requiere confirmación especial.
- Se guarda auditoría de cambios críticos.

## DTE Off o Pendiente

- POS opera localmente.
- No se debe llamar Hacienda.
- No se encola DTE si runtime está apagado o pendiente.
- Worker y monitor hacen backoff/log limitado.
- Reportes y acciones fiscales deben permanecer ocultos cuando no aplican.

## Pagos Divididos y Mixtos

- El backend usa la caja abierta de la sucursal de la orden.
- Pago efectivo con sobrepago se guarda como monto aplicado real y cambio separado.
- Pagos no efectivo no pueden sobrepasar saldo.
- `Payment.amount` y `amount_applied` representan el monto aplicado a la orden.
- Caja registra `cash_in` solo para efectivo aplicado, no para tarjeta/transferencia.
- Reportes/caja agrupan por método sin duplicar el total de la orden.

## Smoke ejecutado

En una transacción con rollback sobre `gastrodb`:

- Orden $10: tarjeta $5 + efectivo $5 => orden pagada, caja efectivo $5, tarjeta $5.
- Orden $10: tarjeta $4 + transferencia $3 + efectivo $3 => orden pagada, neto $10.
- Orden $10: efectivo recibido $20 => aplicado $10, cambio $10, orden pagada.

## Pendientes

- Multi-sucursal real.
- Portal remoto.
- Licencias.
- Cifrado avanzado y rotación de secretos.
- Pruebas automatizadas profundas cuando el rol PostgreSQL pueda crear base de test.
- Limpieza de deuda ESLint heredada.
