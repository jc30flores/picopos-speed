# Fase 25 - DTE full settings, permisos y polish

## Alcance

Esta fase completa la configuración de Hacienda/DTE desde interfaz usando las tablas existentes del sistema: `DTEGlobalSettings`, `DTEBranchConfig` y `DTEControlCounter`. No se toca `gallo_db` y no se guardan secretos en documentación ni migraciones.

## Emisor

La pestaña Configuración > Hacienda/DTE ahora permite capturar datos del emisor:

- Razón social y nombre comercial.
- NIT, DUI y NRC.
- Código y descripción de actividad económica.
- Tipo de establecimiento.
- Departamento, municipio y complemento de dirección.
- Teléfono y correo.

La generación DTE prioriza `DTEBranchConfig` en DB; `.env` queda como fallback temporal.

## Sucursal Principal

La misma pantalla permite configurar la sucursal principal:

- Nombre de sucursal.
- Código establecimiento MH e interno.
- Código punto de venta MH e interno.
- Tipo establecimiento.
- Dirección de sucursal si difiere.

## Correlativos

Se agregó administración de correlativos/last number:

- Endpoint `GET /api/settings/dte/correlatives/`.
- Endpoint `POST /api/settings/dte/correlatives/` para inicializar tipos soportados.
- Endpoint `PATCH /api/settings/dte/correlatives/<id>/` para editar `last_number`.
- Edición solo superadmin.
- Motivo obligatorio.
- Confirmación requerida si se intenta bajar un número.
- Auditoría con valor anterior, nuevo y motivo.

Tipos inicializados:

- Consumidor Final / 01.
- Crédito Fiscal / 03.
- Nota de Crédito / 05.
- Nota de Débito / 06.
- Sujeto Excluido / 14.

## DTE Off

Cuando Hacienda/DTE está apagado:

- POS sigue funcionando local.
- No se encola ni se envía DTE.
- `/api/dte/issued/` devuelve estado `disabled` para superadmin.
- Acciones DTE se ocultan en Reportes/Transacciones y ventas recientes.
- Worker/outbox duerme más tiempo y loguea `DTE_WORKER_DISABLED sleeping` de forma limitada.

## Permisos

- Superadmin puede ver y editar configuración técnica, emisor, sucursal y correlativos.
- Admin puede ver configuración básica, pero no editar URL, token, producción ni correlativos.
- Cajero no accede a configuración técnica.
- Las permission classes DTE consideran superadmin como nivel máximo.

## Apariencia

La validación de color ahora adapta tonos comunes generando:

- `--color-primary`
- `--color-primary-hover`
- `--color-primary-soft`
- `--color-primary-border`
- `--color-primary-text`
- `--color-primary-contrast`
- `--color-primary-on-light`
- `--color-primary-on-dark`

Los errores de formato devuelven `message` y `suggestions`.

## Reportes y Fechas

Se mantiene el trabajo anterior de fechas amigables y dashboard para dueño. La pestaña DTE se oculta si DTE está apagado, y las acciones fiscales no se muestran cuando no aplican.

## Pendientes

- Multi-sucursal real.
- Portal remoto.
- Cifrado avanzado/rotación de secretos.
- Licencias.
- Sincronización cloud.
- Limpieza de deuda ESLint heredada.
