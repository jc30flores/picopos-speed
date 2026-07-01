# Fase 4 — Operación local Windows para Docker con DTE activo

## 1. Objetivo
Preparar operación local en Windows con Docker Desktop mediante scripts PowerShell, sin instalador `.exe` todavía.

## 2. Relación con auditoría
Continúa el plan de Docker Windows sin cambiar despliegue Ubuntu nativo, DTE legal, payload fiscal ni impresión física.

## 3. Relación con Fase 1
Usa runtime strict, `.env.docker`, health endpoints y `check_runtime_config`.

## 4. Relación con Fase 2
Mantiene `db`, `bootstrap`, `backend`, `web`, volúmenes persistentes y Caddy como proxy.

## 5. Relación con Fase 3 DTE worker
Docker usa `DTE_BACKGROUND_MODE=external`, con `dte-worker` y `dte-monitor` como procesos separados.

## 6. Por qué todavía no es .exe
No copia archivos a Program Files ni ProgramData, no firma código, no instala Docker Desktop y no crea shortcuts de sistema; sólo agrega scripts versionados.

## 7. Arquitectura Windows
`compose.yaml` + `compose.build.yaml` opcional + `compose.windows.yaml`; sólo `web` publica `${APP_BIND_ADDRESS:-127.0.0.1}:${APP_HTTP_PORT:-9282}:8080`.

## 8. compose.windows.yaml
Overlay mínimo que conserva arquitectura base, fuerza `DTE_BACKGROUND_MODE=external` y permite LAN sólo con `APP_BIND_ADDRESS=0.0.0.0`.

## 9. Servicios incluidos
`db`, `bootstrap`, `backend`, `web`, `dte-worker`, `dte-monitor`.

## 10. Scripts creados
`common`, `preflight`, `init-env`, `install`, `start`, `stop`, `restart`, `status`, `logs`, `diagnostics`, `backup`, `restore`, `uninstall`.

## 11. Generar .env.docker
`deploy/windows/scripts/init-env.ps1 -AppHttpPort 9282 -BindAddress 127.0.0.1` crea secretos locales y mantiene `.env.docker` ignorado por Git.

## 12. Configurar DTE
Usar `-DteBaseUrl` y `-DteApiToken` o editar `.env.docker` localmente. Los placeholders no son válidos para producción DTE.

## 13. Instalar
`deploy/windows/scripts/install.ps1 -UseLocalBuild`. Para pruebas técnicas con placeholders, agregar `-AllowDtePlaceholdersForLocalBuild`.

## 14. Iniciar
`deploy/windows/scripts/start.ps1` valida DTE y levanta servicios.

## 15. Detener
`deploy/windows/scripts/stop.ps1` ejecuta `docker compose down` sin `-v`.

## 16. Reiniciar
`deploy/windows/scripts/restart.ps1` ejecuta stop y start.

## 17. Estado
`deploy/windows/scripts/status.ps1` muestra Docker, servicios, health HTTP y estado DTE sanitizado.

## 18. Logs
`deploy/windows/scripts/logs.ps1 -Service dte-worker -Tail 200` muestra logs sanitizados.

## 19. Diagnóstico
`deploy/windows/scripts/diagnostics.ps1` genera ZIP sanitizado en `deploy/windows/diagnostics/`.

## 20. Backup
`deploy/windows/scripts/backup.ps1` respalda PostgreSQL con `pg_dump`, `media_data`, `dte_logs` y manifiesto JSON sin secretos.

## 21. Restore
`deploy/windows/scripts/restore.ps1 -BackupPath ...` valida manifiesto, pide confirmación, restaura DB, media y logs DTE.

## 22. Desinstalar sin borrar datos
`deploy/windows/scripts/uninstall.ps1` conserva volúmenes, imágenes, backups, diagnósticos y `.env.docker`.

## 23. Purgar datos
`uninstall.ps1 -PurgeData` exige doble confirmación con `BORRAR DATOS PICO DE GALLO` antes de usar `down -v`.

## 24. Acceso LAN
Editar `.env.docker` y definir `APP_BIND_ADDRESS=0.0.0.0`. Por defecto queda en `127.0.0.1`.

## 25. Estado DTE
DTE sigue activo. Docker usa `DTE_BACKGROUND_MODE=external`; `dte-worker` y `dte-monitor` son procesos separados. No se enviaron DTE reales durante pruebas automatizadas y no se contactó Hacienda durante pruebas automatizadas.

## 26. Estado impresión
Impresión Windows real queda pendiente; no se montan USB, CUPS ni dispositivos.

## 27. Estado cajón
No se implementa apertura física de cajón en Windows.

## 28. Pruebas ejecutadas
Validaciones estáticas, parseo PowerShell si está disponible, búsquedas de seguridad y revisión Git.

## 29. Pruebas bloqueadas
Docker build/up/health quedan bloqueados si el entorno no tiene Docker CLI. PowerShell queda bloqueado si `pwsh` no existe.

## 30. Limitaciones
No hay instalador `.exe`, auto-update, publicación de imágenes, agente de impresión Windows ni prueba DTE real controlada.

## 31. Rollback
Revertir este commit elimina overlay Windows, scripts, shortcuts y documentación de Fase 4. Los datos generados localmente no están versionados.

## 32. Próxima fase recomendada
Probar en Windows real con Docker Desktop y preparar instalador `.exe` sin cambiar DTE legal ni payload fiscal.
