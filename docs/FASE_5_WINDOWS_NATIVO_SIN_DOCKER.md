# Fase 5 — Preparación de paquete nativo Windows sin Docker Desktop

## 1. Cambio de estrategia
La estrategia comercial cambia de operación Windows con Docker Desktop a un instalador nativo para clientes finales.

## 2. Objetivo comercial
El objetivo es que el cliente descargue un único `PicoDeGallo-Setup.exe` y no instale manualmente Docker Desktop, WSL2, Python, Node.js, PostgreSQL, Caddy ni dependencias técnicas.

## 3. Docker como herramienta técnica
Docker se conserva para desarrollo, pruebas y despliegues controlados, pero no será requisito para clientes normales.

## 4. Arquitectura nativa Windows
El release nativo separa `Program Files` para binarios/código y `ProgramData` para configuración, datos persistentes, logs, backups y diagnósticos.

## 5. Servicios Windows
Se contemplan `PicoDeGallo-PostgreSQL`, `PicoDeGallo-Backend`, `PicoDeGallo-DTE-Worker`, `PicoDeGallo-DTE-Monitor` y `PicoDeGallo-Caddy`.

## 6. PostgreSQL nativo
La opción recomendada es PostgreSQL portable controlado por el instalador. La alternativa es instalador oficial silencioso. SQLite no reemplaza el modo real.

## 7. Backend nativo
Gunicorn permanece para Linux/Docker. Windows nativo usará Waitress como servidor WSGI compatible, sin usar `runserver` como servicio productivo.

## 8. Frontend y Caddy nativos
El frontend compilado se servirá desde `C:\Program Files\PicoDeGallo\frontend`; Caddy para Windows hará proxy local a backend y servirá media/static.

## 9. DTE worker/monitor nativos
DTE sigue activo. `dte_outbox_worker` y `dte_monitor` se ejecutarán como servicios Windows separados con `DTE_BACKGROUND_MODE=external`.

## 10. Rutas
`C:\Program Files\PicoDeGallo` contiene programa y runtimes. `C:\ProgramData\PicoDeGallo` contiene `.env`, media, static, dte_logs, logs, backups, diagnostics y datos PostgreSQL.

## 11. Backups
`backup.ps1` usará `pg_dump`, copiará media y dte_logs, y generará `manifest.json` sin secretos.

## 12. Restore
`restore.ps1` validará manifiesto, pedirá confirmación, restaurará DB/media/dte_logs y reiniciará servicios.

## 13. Diagnóstico
`diagnostics.ps1` generará ZIP sanitizado con estado de servicios, logs, salud HTTP, espacio en disco y configuración no sensible.

## 14. Impresión Windows
La impresión Windows real y agente de impresión siguen pendientes.

## 15. Instalador .exe pendiente
Esta fase no crea el `.exe`; sólo prepara layout, scripts, plantillas y documentación para la siguiente fase.

## 16. Binarios requeridos
El release necesitará Python Windows, PostgreSQL Windows/portable, Caddy Windows y WinSW o wrapper equivalente. No se versionan en Git.

## 17. Qué no se versiona
No se versionan `.env` reales, tokens, passwords, binarios `.exe/.dll/.msi/.zip`, venv, site-packages, frontend/dist generado, media, dumps ni backups.

## 18. Riesgos
Falta validar en Windows limpio, definir estrategia final PostgreSQL, empaquetar runtimes, validar Waitress con carga real, firmar instalador y diseñar actualización/rollback.

## 19. Pruebas requeridas en Windows limpio
Instalar sin herramientas técnicas previas, iniciar servicios, validar DTE con credenciales controladas, crear backup, restaurar, generar diagnóstico, reiniciar PC y desinstalar sin borrar datos.

## 20. Criterios para pasar a Inno Setup final
Layout estable, scripts parseados y probados, servicios instalables con WinSW, Caddy funcional, PostgreSQL inicializable, backend en Waitress, DTE worker/monitor activos, backup/restore validado y cero secretos en logs.

## Estado explícito
DTE sigue activo. No se enviaron DTE reales durante pruebas automatizadas. No se contactó Hacienda durante pruebas automatizadas. Docker no se elimina, pero no es el camino comercial para clientes normales.
