# Fase 3 — DTE worker/monitor separados para Docker

## 1. Objetivo
Separar los procesos de fondo DTE del proceso web/Gunicorn para Docker, manteniendo DTE activo.

## 2. Relación con auditoría
Continúa la preparación Docker Windows sin cambiar el flujo fiscal ni apagar DTE.

## 3. Relación con Fase 1 y Fase 2
Usa runtime strict, Gunicorn, healthchecks y Compose base; agrega servicios dedicados para DTE.

## 4. Problema de AppConfig.ready/RUN_MAIN
El código heredado arrancaba monitor y outbox desde `AppConfig.ready()` condicionado por `RUN_MAIN`, útil en runserver pero riesgoso en Gunicorn por duplicación o acoplamiento al web.

## 5. DTE_BACKGROUND_MODE
Nueva variable: `legacy`, `external`, `disabled`.

## 6. legacy/external/disabled
`legacy` conserva Ubuntu nativo/runserver. `external` evita arranque en web y usa servicios Compose. `disabled` es solo diagnóstico controlado de procesos de fondo, no apaga el módulo DTE.

## 7. Comandos creados
`python manage.py dte_outbox_worker` y `python manage.py dte_monitor`, ambos con `--once`; worker incluye `--batch-size`, `--max-iterations`, `--sleep-seconds`, `--no-send`; monitor incluye `--max-iterations`, `--sleep-seconds`, `--no-network`.

## 8. Servicios Docker agregados
`dte-worker` ejecuta `python manage.py dte_outbox_worker`. `dte-monitor` ejecuta `python manage.py dte_monitor`. Ambos usan la imagen backend y no publican puertos.

## 9. Worker duplicado
El outbox ya selecciona filas con `select_for_update(skip_locked=True)`. El command agrega un advisory lock PostgreSQL de ciclo para reducir duplicación accidental entre workers.

## 10. Ubuntu nativo
`DTE_BACKGROUND_MODE=legacy` es el default y conserva el comportamiento de `AppConfig.ready()` con `RUN_MAIN`.

## 11. DTE activo en Docker
Docker usa `DTE_BACKGROUND_MODE=external`, `DTE_MONITOR_ENABLED=true`, `DTE_OUTBOX_WORKER_ENABLED=true` y placeholders obligatorios para `DTE_BASE_URL` y `DTE_API_TOKEN`.

## 12. Variables DTE requeridas
`DTE_BASE_URL`, `DTE_API_TOKEN`, `DTE_API_AUTH_HEADER`, `DTE_API_AUTH_PREFIX`, `DTE_MONITOR_ENABLED`, `DTE_OUTBOX_WORKER_ENABLED`, `DTE_MAX_RETRIES`, `DTE_PENDING_BATCH_SIZE`, `DTE_LOG_DIR`.

## 13. Pruebas ejecutadas
Se ejecutaron validaciones estáticas/compilación y comandos locales disponibles. Docker no está disponible en el entorno.

## 14. Pruebas bloqueadas
Docker compose/build/up/logs bloqueados por falta de Docker CLI. Tests Django pueden quedar bloqueados si faltan dependencias locales no instaladas.

## 15. Limitaciones
No se enviaron DTE reales. No se contactó Hacienda durante pruebas automatizadas. No se validó stack Docker en ejecución por limitación de entorno.

## 16. Rollback
Revertir este commit vuelve al arranque heredado desde AppConfig.ready y elimina servicios dte-worker/dte-monitor.

## 17. Próxima fase recomendada
Probar Docker en ambiente con CLI disponible y luego preparar scripts Windows/instalador.

DTE sigue activo. No se implementó una ruta operativa sin DTE. Docker ahora debe usar workers separados. Windows scripts e instalador `.exe` siguen pendientes.
