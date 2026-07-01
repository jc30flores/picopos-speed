# Fase 2 — Docker base local/reproducible

## 1. Objetivo
Crear una base Docker local para validar PostgreSQL, Django/Gunicorn, frontend React/Vite compilado y Caddy como proxy, sin convertirla todavía en instalador Windows ni producción.

## 2. Relación con auditoría
Esta fase continúa `docs/AUDITORIA_DOCKER_WINDOWS.md`: primero se preparó runtime strict en Fase 1 y ahora se prueba una topología Docker mínima y reproducible.

## 3. Relación con Fase 1
Usa `DJANGO_CONFIG_MODE=strict`, `check_runtime_config`, health endpoints, rutas configurables y Gunicorn declarados en Fase 1.

## 4. Arquitectura implementada
Servicios: `db`, `bootstrap`, `backend`, `web`.

## 5. Diagrama textual
`host:127.0.0.1:${APP_HTTP_PORT}` → `web(Caddy:8080)` → `/api|/admin` → `backend(Gunicorn:8000)` → `db(PostgreSQL:5432 interno)`. Volúmenes: `postgres_data`, `media_data`, `static_data`, `dte_logs`.

## 6. Archivos creados
`backend/Dockerfile`, `frontend/Dockerfile`, `docker/caddy/Caddyfile`, `compose.yaml`, `compose.build.yaml`, `.env.docker.example`, `docs/FASE_2_DOCKER_BASE.md`.

## 7. Archivos modificados
`.gitignore` para ignorar `.env.docker`, `.env.docker.local`, `.env.docker.test`.

## 8. Imágenes base usadas
Backend: `python:3.12-slim-bookworm`. Frontend build: `node:24-bookworm-slim`. Web runtime: `caddy:2.8.4-alpine`. DB: `${POSTGRES_IMAGE}` por defecto `postgres:16-bookworm`.

## 9. Variables de `.env.docker`
Incluye imágenes, puerto local, secretos placeholder, DB, `ALLOWED_HOSTS`, CORS/CSRF, rutas POSIX, Gunicorn y placeholders DTE que serán ejecutados por servicios separados desde Fase 3.

## 10. Volúmenes
`postgres_data` para PostgreSQL, `media_data` para media, `static_data` para collectstatic, `dte_logs` para logs DTE locales no sensibles.

## 11. Puertos
Sólo `web` publica `127.0.0.1:${APP_HTTP_PORT}:8080`. PostgreSQL y backend no publican puertos al host.

## 12. Flujo bootstrap
Espera DB healthy y ejecuta: `check_runtime_config --strict`, `manage.py check`, `migrate --noinput`, `collectstatic --noinput`. No crea admin ni carga fixtures.

## 13. Healthchecks
DB usa `pg_isready`; backend usa `/api/health/ready/`; web usa `/api/health/live/` vía Caddy.

## 14. Build
`docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml build --pull`

## 15. Inicio
`docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml up -d`

## 16. Parada
`docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml down`

## 17. Logs
`docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml logs --no-color --tail=100 backend web bootstrap`

## 18. Salud
`docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml ps` y HTTP a `/`, `/api/health/live/`, `/api/health/ready/`.

## 19. Conservación de datos
Usar `down` sin `-v`; los volúmenes nombrados conservan PostgreSQL, media, static y logs.

## 20. Advertencia fuerte
No usar `docker compose down -v` en pruebas normales: borra volúmenes y datos persistentes.

## 21. Compatibilidad Ubuntu nativo
No reemplaza systemd, Caddy externo ni despliegue nativo. Sólo agrega archivos Docker y documentación.

## 22. Qué no se implementó
No se agregó `compose.windows.yaml`, scripts PowerShell, instalador, GitHub Actions, backup/restore, agente de impresión, acceso USB, CUPS host, worker DTE separado ni cambios funcionales POS.

## 23. Riesgos pendientes
El stack no está listo para producción Windows; faltan separar worker DTE, monitor DTE dedicado, backup/restore, scripts Windows, `compose.windows.yaml`, acceso LAN, agente impresión Windows, instalador `.exe`, actualización/rollback, prueba DTE real controlada, workers DTE separados y revisar migraciones pendientes si persisten.

## 24. Estado DTE
Fase 2 dejó `dte_logs` y configuración base. Fase 3 separa formalmente `dte-worker` y `dte-monitor`, mantiene DTE activo con placeholders seguros y evita que Gunicorn arranque procesos DTE internos mediante `DTE_BACKGROUND_MODE=external`.

## 25. Estado impresión
Docker usa `PRINTER_ENABLED=false`, `PRINTER_MODE=mock`, `RECEIPT_PRINTER_MODE=mock`, `CASH_DRAWER_ENABLED=false`, `CASH_DRAWER_MODE=mock`. No se montan USB, CUPS ni dispositivos.

## 26. Migraciones pendientes preexistentes
Fase 1 detectó drift en `employees`, `inventory`, `menu`. Esta fase no crea ni corrige migraciones; si el chequeo sigue fallando se clasifica como `BLOCKED/PREEXISTING`.

## 27. Pruebas ejecutadas
Resultados reales se mantienen en la entrega final del PR: validaciones locales, frontend, Docker/Compose si el entorno lo permite, health HTTP, logs y persistencia.

## 28. Resultado real
Usar clasificación `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`; no se debe declarar producción lista mientras existan bloqueos.

## 29. Rollback
Revertir el commit de Fase 2 elimina la base Docker y mantiene intacto el despliegue Ubuntu nativo.

## 30. Próxima fase recomendada
Fase 3: separar explícitamente worker/monitor DTE, diseñar `compose.windows.yaml`, backups, scripts Windows y agente de impresión Windows.

## Resultados reales de esta ejecución
- PASS: `npm ci` completó con advertencia npm histórica `Unknown env config "http-proxy"`.
- PASS: `npm run typecheck` completó correctamente.
- PASS: `npm run build` completó correctamente; Vite reportó advertencias de chunk grande/dynamic import.
- PASS: inspección específica de `frontend/dist` no encontró `centro-pdg.cuskatech.com`, `monaco-pdg.cuskatech.com`, `localhost:8102` ni `127.0.0.1:8102`.
- PASS: validación estática confirmó que `compose.yaml` no contiene `build`, `version`, `privileged` ni `network_mode`, y no publica `5432` ni `8000`; `compose.build.yaml` sí contiene `build`.
- FAIL/HISTÓRICO: `npm run lint` falla por errores preexistentes de TypeScript/ESLint no relacionados con Docker.
- BLOCKED/ENV: Docker CLI no está disponible (`docker: command not found`), por lo que `docker compose config`, `build --pull`, `up -d`, `ps`, HTTP, logs, reinicio y persistencia no pudieron ejecutarse en este entorno.
- BLOCKED/ENV: checks Django locales fallaron por dependencia no instalada en el entorno local (`ModuleNotFoundError: No module named 'requests'`), aunque `requests` está declarado en `backend/requirements.txt` y se instala en la imagen Docker.
- BLOCKED/NOT RUN: pruebas dentro de contenedor, `pip check`, `gunicorn` real, `makemigrations --check --dry-run` dentro de Docker y persistencia DB/media quedan pendientes hasta tener Docker disponible.
