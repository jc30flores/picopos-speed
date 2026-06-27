# Fase 1 — Preparación runtime backend

Objetivo: preparar el backend para futuros despliegues Docker Windows sin reemplazar Ubuntu nativo.

Según la auditoría `docs/AUDITORIA_DOCKER_WINDOWS.md`, esta fase sólo centraliza variables, validación runtime, healthchecks y Gunicorn declarado.

Archivos creados: `backend/config/env.py`, `backend/config/runtime.py`, `backend/apps/core/health.py`, `backend/apps/core/management/commands/check_runtime_config.py`, `backend/.env.example`, `.dockerignore`.

Archivos modificados: `backend/config/settings.py`, `backend/config/urls.py`, `backend/requirements.txt`.

Variables nuevas: `DJANGO_CONFIG_MODE`, `DOTENV_OVERRIDE`, `DJANGO_MEDIA_ROOT`, `DJANGO_STATIC_ROOT`, `DTE_LOG_DIR`; también se formalizan `ALLOWED_HOSTS`, CORS y CSRF por entorno.

Modo legacy: predeterminado, conserva fallbacks heredados para Ubuntu nativo. Estos fallbacks deben retirarse en una fase posterior.

Modo strict: exige variables críticas, no usa secretos inseguros de fallback y no imprime secretos.

Precedencia `.env`: variables del sistema, luego `backend/.env`, luego defaults legacy. `DOTENV_OVERRIDE=true` permite reemplazar variables existentes; el valor recomendado es `false`.

`ALLOWED_HOSTS`: configurable por coma; en strict es obligatorio, no acepta URLs completas ni `*`.

CORS/CSRF: las variables principales reemplazan la base; las variables `*_EXTRA` agregan valores; se validan orígenes `http://` o `https://`.

Health endpoints: `GET/HEAD /api/health/live/` no consulta DB; `GET/HEAD /api/health/ready/` ejecuta `SELECT 1` y no expone secretos.

`check_runtime_config`: valida configuración humana o JSON con `--json`; `--strict` devuelve error si faltan críticos.

Gunicorn declarado: futuro comando `gunicorn config.wsgi:application --bind 0.0.0.0:8000`. No reemplaza systemd/runserver actual.

Compatibilidad Ubuntu nativo: se mantienen defaults legacy y no se modifica systemd, Caddy externo, impresión, worker DTE ni frontend.

Qué no se tocó: POS, ventas, inventario, pagos, caja, DTE funcional, impresión, worker DTE, migraciones, frontend.

Riesgos pendientes: secretos heredados sólo encapsulados en legacy hasta migración definitiva.

Pruebas ejecutadas: ver entrega final del PR para resultado real.

Rollback: revertir el commit de esta fase restaura settings estáticos previos.

Próximo paso recomendado: diseñar Dockerfiles y Compose después de validar strict en Ubuntu.

Pendientes expresos: Dockerfiles, compose.yaml, PostgreSQL Docker, Caddy Docker, separación worker DTE, agente impresión Windows, backup/restore, scripts PowerShell, instalador .exe.
