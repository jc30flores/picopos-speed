# Fase 25 - Fix Settings, DTE apagado y Reportes

## Contexto

Después de la primera fase de GastroPOSV, la UI llamaba `GET /api/settings/appearance/` y `GET /api/settings/dte/`, pero esas rutas no estaban expuestas en `backend/config/urls.py`. El backend sí tenía vistas en `apps.core`, por eso el navegador recibía 404 y las pestañas quedaban cargando.

También se detectó que el cobro seguía entrando al flujo DTE aunque Hacienda estuviera apagado. El pago terminaba registrado, pero el backend imprimía `payment.dte.failed` y trazas por un estado esperado: facturación electrónica desactivada.

## Correcciones

- Se expusieron `/api/settings/appearance/` y `/api/settings/dte/` con trailing slash bajo `/api`.
- Ambos endpoints devuelven JSON estable con defaults aunque no exista configuración previa.
- El frontend tolera campos nuevos (`enabled`, `environment`, `config_status`) y antiguos (`hacienda_enabled`, `ambiente`, `status`).
- Las pestañas Apariencia y Hacienda/DTE tienen loading, error y botón Reintentar.
- Se agregó `apps.dte.runtime` como helper central para estado runtime DTE.
- El cobro ya no llama `send_dte_for_order` cuando DTE está desactivado o pendiente de configuración.
- El outbox, monitor y orquestador DTE saltan procesamiento cuando DTE está apagado o incompleto.
- Reportes/Transacciones oculta “Enviar DTE a Cliente” cuando DTE está apagado.
- La ruta DTE directa muestra estado informativo si el sistema opera como POS local.
- Tickets, cierres, delivery y fallbacks visibles usan `GastroPOSV` o nombre comercial configurado.

## Reportes

- Se agregaron métricas de dueño en Resumen: neto estimado, mejor día, hora pico y comparación.
- Se agregaron accesos rápidos: Hoy, Ayer, Semana actual y Mes actual.
- Se centralizaron formatos visibles de fecha, hora, moneda, porcentaje y duración.
- Los ejes y tooltips de gráficas muestran fechas amigables, no timestamps ISO.
- Los tooltips usan colores del tema para modo oscuro/claro.

## Cómo probar

1. Confirmar rama: `git branch --show-current`.
2. Confirmar DB: `python backend/manage.py shell -c "from django.db import connection; print(connection.settings_dict['NAME'])"`.
3. Ejecutar `backend/venv/bin/python backend/manage.py migrate`.
4. Ejecutar `backend/venv/bin/python backend/manage.py ensure_superadmin`.
5. Login como `superadmin` / `102938`.
6. Abrir Configuración > Apariencia y guardar un color válido.
7. Abrir Configuración > Hacienda/DTE y apagar facturación electrónica.
8. Cobrar una venta: debe quedar local, sin traceback DTE.
9. Ir a Reportes > Transacciones: no debe aparecer “Enviar DTE a Cliente”.
10. Abrir DTE por URL: debe mostrar que facturación electrónica está desactivada.
11. Abrir ticket: no debe mostrar `Pico de Gallo` como marca hardcodeada.

## Pendientes

- Resolver migraciones pendientes existentes en `employees`, `inventory` y `menu` con revisión separada.
- Validación manual completa en navegador con servicio real levantado.
- Multi-sucursal completo.
- Licenciamiento, portal remoto y sincronización cloud.
- Renombrar rutas/servicios internos Windows en una fase específica.
