# Auditoría técnica para Docker Windows/WSL2 - Pico de Gallo

Fecha de auditoría: 2026-06-25. Alcance: inspección del repositorio sin modificar código funcional ni configuración de producción. Único archivo creado: `docs/AUDITORIA_DOCKER_WINDOWS.md`.

## 1. Resumen ejecutivo

El proyecto es una aplicación POS Django + React/Vite con PostgreSQL, impresión local por CUPS/USB/ESC-POS y módulo DTE con outbox persistido en base de datos. La ruta más segura hacia Docker es crear contenedores Linux para backend, frontend estático, proxy y PostgreSQL, manteniendo intacto el despliegue Ubuntu nativo actual.

Conclusión principal: **Docker es viable**, pero no debe implementarse hasta resolver o aislar los siguientes riesgos:

| Severidad | Cantidad | Resumen |
|---|---:|---|
| BLOQUEANTE | 5 | secretos/defaults inseguros, impresión USB/CUPS acoplada al host, workers DTE arrancan dentro del proceso web/autoreload, `ALLOWED_HOSTS` no configurable, ausencia de healthcheck HTTP backend explícito. |
| ALTO | 9 | frontend compila `VITE_API_BASE`, media solo se sirve en DEBUG, CORS/CSRF con dominios quemados, rutas de logs DTE relativas/no persistentes, comandos `lp/lpstat`, dependencia de `RUN_MAIN`, falta versión PostgreSQL declarada, backup/restore no automatizado, Caddy/systemd no versionados en repo. |
| MEDIO | 12 | venv y media están dentro de `backend/`, lockfile npm convive con bun, puertos quemados, impresora Star fija, dominios históricos, scripts SQL/dumps sueltos, `.env` simple, static/media mezclan responsabilidades, pruebas dependen de DB local, locales/encoding no declarados, permisos USB/udev Ubuntu, Windows firewall/antivirus. |
| BAJO | 8 | documentación inconsistente (`backend/menu_image` vs `backend/media/menu_image`), `print()` en settings, `README` Lovable residual, ausencia de `.nvmrc`, ausencia de `.python-version`, archivos raíz de prueba/respuesta, nombres con espacios potenciales no probados. |

## 2. Arquitectura actual

### 2.1 Estructura backend

- Backend Django ubicado en `backend/` con `manage.py`, `config/` y aplicaciones en `backend/apps/`.
- Apps detectadas: `core`, `users`, `menu`, `orders`, `kitchen`, `reports`, `employees`, `payments`, `printing`, `cashier`, `dte`, `inventory`.
- Configuración principal: `backend/config/settings.py`.
- URLConf principal: `backend/config/urls.py` expone rutas `/api/*`, `/admin/`, y media solo si `settings.DEBUG`.
- WSGI y ASGI existen: `backend/config/wsgi.py` y `backend/config/asgi.py`.
- Archivos persistentes actuales bajo `backend/media/`, incluyendo `categories/`, `menu_image/` y `receipts/`.
- Entorno virtual local dentro del repo: `backend/venv/` (no debe copiarse a imagen Docker).

### 2.2 Estructura frontend

- Frontend React + TypeScript + Vite ubicado en `frontend/`.
- Código en `frontend/src/`, con componentes, páginas, hooks, contexto y `frontend/src/lib/api.ts`.
- Scripts NPM en `frontend/package.json`: `dev`, `build`, `build:dev`, `lint`, `typecheck`, `preview`.
- Lockfiles: `frontend/package-lock.json` y `frontend/bun.lockb`; el gestor verificable por scripts es npm.

### 2.3 Versiones reales verificadas

| Elemento | Evidencia | Resultado |
|---|---|---|
| Python del entorno inspeccionado | `python --version` | Python 3.14.4 |
| Python usado por venv del repo | ruta `backend/venv/lib/python3.12` y bytecode `settings.cpython-312.pyc` | Python 3.12 probable del entorno previo |
| Django requerido | `backend/requirements.txt` | `Django>=5.1,<6.0` |
| Django instalado | no se ejecutó import por no activar venv ni modificar entorno | debe verificarse con `backend/venv/bin/python -m django --version` en host real |
| Node del entorno inspeccionado | `node --version` | v24.15.0 |
| npm del entorno inspeccionado | `npm --version` | 11.4.2 |
| PostgreSQL esperado | `ENGINE=django.db.backends.postgresql`, `DB_PORT` default `5432`; no hay versión declarada | Recomendada imagen `postgres:16` o igualar versión de producción con `SELECT version();` antes de migrar |

### 2.4 Comandos actuales

- Backend dev/documentado: `python backend/manage.py runserver` y `python backend/manage.py runserver 0.0.0.0:8102`.
- Secuencia DB documentada: `dbcheck`, `migrate`, `schemacheck`, `initdb`, `runserver`.
- Frontend dev: `npm run dev` en `frontend/` con puerto 8182.
- Frontend build: `npm run build` (`vite build`).
- DTE retry: `python backend/manage.py dte_autoresend --limit 25`.

### 2.5 Servidores, proxy y systemd

- WSGI/ASGI: existen ambos módulos, pero no se encontró `gunicorn`, `uvicorn` ni `daphne` en `requirements.txt`.
- Proxy: no hay Caddyfile/Nginx versionado en el repo. Solo Vite dev proxy `/api -> http://127.0.0.1:8102`.
- systemd: no se encontraron `.service` ni `.timer` versionados dentro del repo.
- Conclusión: el despliegue actual de Ubuntu probablemente tiene Caddy/systemd fuera del repo; debe inventariarse en el host antes de Docker.

### 2.6 Puertos y dependencias entre procesos

| Puerto | Uso | Evidencia |
|---:|---|---|
| 8102 | Django dev backend | README y Vite proxy |
| 8182 | Vite dev frontend | README y `vite.config.ts` |
| 9102 | CSRF trusted origin adicional | `settings.py` |
| 5432 | PostgreSQL | `settings.py` default |
| 80/443 | proxy recomendado | no versionado actualmente |

Dependencias: frontend consume backend por `/api` por defecto o `VITE_API_BASE`; backend requiere PostgreSQL; DTE requiere internet/API externa; impresión requiere host con CUPS/USB o backend con acceso a dispositivos; media/static deben servirse por Django en DEBUG o por proxy en producción.

## 3. Inventario de servicios

| Servicio/proceso | Actual | Docker recomendado | Observaciones |
|---|---|---|---|
| Backend Django | `runserver` documentado | `gunicorn config.wsgi:application` | Falta dependencia gunicorn. |
| Frontend Vite dev | `npm run dev` | build estático servido por Caddy/Nginx | No requiere Node en runtime si se genera `dist`. |
| PostgreSQL | host externo/local con defaults | contenedor `postgres` opcional | Mantener Ubuntu nativo intacto. |
| DTE monitor/outbox | se inicia en `apps.dte.apps.ready()` cuando `RUN_MAIN=true` | worker dedicado o comando separado | Evitar múltiples workers por réplicas/procesos. |
| Impresión | backend llama USB/CUPS/lp | agente nativo host o servicio Ubuntu con CUPS | Windows requiere agente o impresora de red. |
| Proxy | no versionado | Caddy/Nginx contenedor | Debe servir `/`, `/api`, `/media`, `/static`. |

## 4. Inventario de variables de entorno

Reglas de lectura: backend carga `backend/.env` mediante `python-dotenv` con `override=True`; fallback manual solo soporta líneas `KEY=value` simples sin expansión ni quoting avanzado. En Windows `.env` funciona si está en UTF-8, con LF o CRLF; rutas Windows con backslash deben escaparse o preferir `/` dentro de contenedores.

| Variable | Uso/archivo | Obligatoria | Default | Sensible | Fase | Si falta |
|---|---|---:|---|---:|---|---|
| `DJANGO_SECRET_KEY` | `backend/config/settings.py` | Sí prod | `dev-secret-key` | Sí | runtime | Arranca inseguro. |
| `DJANGO_DEBUG` | settings | Sí prod | `true` | No | runtime | DEBUG activo. |
| `DB_HOST` | settings | Sí | `localhost` | No | runtime | En Docker apunta al contenedor equivocado si no se cambia. |
| `DB_USER` | settings | Sí | `jarvis` | Sí | runtime | Usa usuario quemado. |
| `DB_PASSWORD` | settings | Sí | `diez2030` | Sí | runtime | Usa password quemado. |
| `DB_NAME` | settings | Sí | `gallo_db` | No | runtime | Usa BD quemada. |
| `DB_PORT` | settings | Sí | `5432` | No | runtime | Usa puerto estándar. |
| `CORS_ALLOWED_ORIGINS`, `CORS_ALLOWED_ORIGINS_EXTRA` | settings | Opcional hoy; requerida multi-dominio | defaults localhost/centro-pdg | No | runtime | Dominios default solamente. |
| `CSRF_TRUSTED_ORIGINS`, `CSRF_TRUSTED_ORIGINS_EXTRA` | settings | Opcional hoy; requerida multi-dominio | defaults localhost/9102/centro-pdg | No | runtime | Fallos CSRF fuera de defaults. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | settings | Recomendado prod | `not DEBUG` | No | runtime | Cookies inseguras si DEBUG true. |
| `SESSION_COOKIE_SAMESITE`, `CSRF_COOKIE_SAMESITE` | settings | Opcional | `Lax` | No | runtime | Lax. |
| `CASH_DRAWER_*` | settings/cashier | Opcional según hardware | mock/None/25/250 | No | runtime | Cajón desactivado o sin dispositivo. |
| `PRINTER_*`, `RECEIPT_PRINTER_*`, `PRINTER_SIZE(_MM)` | settings/printing | Opcional según hardware | usb/80mm/heredados de cash drawer | No | runtime | Puede intentar USB sin IDs; PDFs 80mm. |
| `MH_AMBIENTE`, `DTE_AMBIENTE`, `HACIENDA_AMBIENTE` | settings, DTE migrations/services | Sí DTE prod | `00` o fallback | No | runtime/migration | Ambiente de pruebas o normalización inconsistente. |
| `DTE_BASE_URL` | settings/DTE HTTP | Sí DTE real | vacío | No | runtime | Envío HTTP falla por URL vacía. |
| `DTE_API_TOKEN`, `DTE_API_AUTH_HEADER`, `DTE_API_AUTH_PREFIX` | settings/DTE HTTP | Token sí | token vacío, Authorization/Bearer | Sí | runtime | Auth ausente; fallo externo. |
| `DTE_TIMEOUT_SECONDS`, `DTE_CONNECT_TIMEOUT`, `DTE_READ_TIMEOUT` | settings | Opcional | 30/5/timeout | No | runtime | Timeouts default. |
| `DTE_HEALTH_ENDPOINT`, `DTE_HEALTH_TIMEOUT_SECONDS`, `DTE_MONITOR_*` | settings/monitor | Opcional | `/health`, 5, 10/30/enabled | No | runtime | Monitor activo por defecto. |
| `DTE_OUTBOX_*`, `DTE_MAX_RETRIES`, `DTE_*BACKOFF*`, `DTE_PENDING_BATCH_SIZE` | settings/outbox | Opcional | activo, 1 concurrencia, 5 reintentos | No | runtime | Worker activo por defecto. |
| `DTE_LOG_*` | settings/DTE | Opcional | INFO, truncado, dir `tmp/dte_payloads` | Puede ser sensible | runtime | Logs solo consola o ruta relativa. |
| `DTE_EMISOR_NIT`, `DTE_NOMBRE_COMERCIAL`, `COMPANY_NAME` | settings/payload entrega | Sí DTE prod según datos BD | vacío | Sí/PII | runtime | Payload incompleto/fallback. |
| `DTE_BRIDGE_*` | `apps/dte/services/client.py`, `dte_sender.py` | Solo bridge legado | mode `http`, base/token vacío | Sí | runtime | Lanza error si bridge sin URL. |
| `DTE_REQUIRE_AMBIENTE_01` | ambiente | Opcional | falso | No | runtime | No fuerza producción. |
| `DTE_AUTORETRY_BATCH_SIZE`, `DTE_AUTORETRY_BACKOFF_SECONDS` | command `dte_autoresend` | Opcional | 25/60 | No | runtime | Defaults. |
| `DELIVER_EMAIL_API_*`, `EMAIL_API_*` | delivery_config | Sí para correo real | vacío, endpoint `/send` | Sí | runtime | Envío correo no configurado. |
| `WHATSAPP_DTE_API_*`, `WHATSAPP_API_*`, `WHATSAPP_DEFAULT_TO_PHONE`, `WHATSAPP_ALLOW_DEFAULT_FALLBACK`, `WHATSAPP_EMPRESA_NOMBRE`, `WHATSAPP_COMPANY_NAME` | delivery_config | Sí para WhatsApp real | vacío/false | Sí/PII | runtime | WhatsApp no configurado/falla. |
| `BRANCH_ID`, `POS_BRANCH_ID`, `DEFAULT_BRANCH_ID`, `ACTIVE_BRANCH_CODE` | settings/branch_profile | Opcional | None/empty | No | runtime | Usa lógica/BD por defecto. |
| `CODE_CHANGE_PRICE` | settings | Opcional | vacío | No | runtime | Sin código especial. |
| `RUN_MAIN` | DTE AppConfig | Interna Django autoreload | no default | No | runtime | Workers no arrancan fuera de `runserver` autoreload si no se replica. |
| `TZ` | manage/wsgi/asgi setdefault | Opcional | `America/El_Salvador` | No | runtime | Se fija si falta. |
| `VITE_API_BASE` | `frontend/src/lib/api.ts` | Opcional | `/api` | No | build | Queda embebida en bundle; cambiar `.env` post-build no cambia. |
| `VITE_AUTH_DEBUG`, `VITE_ATTENDANCE_DEBUG`, `VITE_DEBUG`, `DEV` | frontend | Opcional | false/DEV | No | build/dev | Solo logs/debug. |

## 5. Hallazgos clasificados

### BLOQUEANTE

1. **Secretos y defaults de producción inseguros.** `DJANGO_SECRET_KEY`, `DB_USER` y `DB_PASSWORD` tienen defaults quemados. Solución: exigir variables/secretos en producción y fallar rápido si faltan.
2. **Impresión USB/CUPS acoplada al host Linux.** `SystemPrinterService` ejecuta `lpstat` y `lp`; `UsbPrinterService` requiere `pyusb/python-escpos` y permisos USB. Windows Docker no puede acceder de forma fiable a USB térmico sin agente nativo o impresora de red.
3. **Workers DTE arrancan desde `AppConfig.ready()` condicionado por `RUN_MAIN`.** En Gunicorn/containers puede no arrancar, arrancar varias veces o depender del tipo de proceso. Solución: worker dedicado (`manage.py dte_outbox_worker` o comando supervisado) e idempotencia con locking.
4. **`ALLOWED_HOSTS` no es configurable por env.** Está quemado a localhost/127/0.0.0.0/centro-pdg. Solución: `ALLOWED_HOSTS` env list.
5. **No hay endpoint de salud backend explícito y versionado.** Hay healthcheck DTE externo, pero no `/api/health/` simple para Docker healthchecks.

### ALTO

- `VITE_API_BASE` se evalúa en build; cambios de `.env` después de compilar no cambian el bundle.
- Media se sirve en `urls.py` solo con `DEBUG`; producción requiere proxy sirviendo `/media/`.
- CORS/CSRF incluyen `centro-pdg.cuskatech.com` y localhost quemados; falta dominio por instalación.
- Logs DTE a archivo usan rutas relativas (`tmp/dte_payloads`) que pueden perderse si no hay volumen.
- `requirements.txt` no incluye Gunicorn/Uvicorn, aunque existen WSGI/ASGI.
- No hay versión PostgreSQL declarada; existen dumps/SQL (`gallo.dump`, `geo_catalogs.sql`, `backup_menu_data.sql`) sin estrategia versionada.
- No hay Caddy/Nginx/systemd versionados; despliegue actual depende de host.
- Comandos CUPS (`lp`, `lpstat`) requieren paquetes `cups-client` y cola existente dentro/host.
- `DTE_BASE_URL` vacío no falla al arranque, falla al enviar.

### MEDIO

- `backend/venv` dentro del repo puede contaminar builds si no se excluye.
- `backend/media` contiene datos persistentes dentro del árbol de código.
- Lockfiles npm y bun simultáneos.
- Puertos 8102/8182/9102 quemados en documentación/config.
- `STAR_QUEUE = "TSP143-(STR_T-001)"` fija una cola concreta.
- `MEDIA_ROOT.mkdir()` y `MENU_IMAGE_ROOT.mkdir()` ejecutan escritura al importar settings.
- DTE entrega email/WhatsApp tiene endpoints por env, pero sin cola persistida específica para reintentos de entrega más allá de `DteDeliveryAttempt` básico.
- Ausencia de `.nvmrc`/`.python-version`.
- Scripts SQL/dumps no integrados a migrations.
- Test/dev README usa `runserver`, no producción.
- `DTE_LOG_SECRETS` puede mostrar token si se activa.
- `print("ENV LOADED FROM:")` en settings genera ruido en logs.

### BAJO

- README aún dice “Lovable project”.
- Documentación de imágenes menciona `backend/menu_image`, pero el código usa `backend/media/menu_image`.
- Archivos raíz de respuesta/prueba (`response_body.json`, `respuesta`, `error`, etc.) deberían clasificarse antes de Docker.
- No se encontró WebSocket; riesgo bajo para proxy WS.

## 6. Valores quemados y soluciones propuestas

| Archivo | Línea aproximada | Valor | Problema | Solución propuesta |
|---|---:|---|---|---|
| `backend/config/settings.py` | 61-62 | `dev-secret-key`, DEBUG true | Inseguro prod | Variables obligatorias en perfil prod. |
| `backend/config/settings.py` | 64 | hosts fijos | Dominios no portables | `ALLOWED_HOSTS` env list. |
| `backend/config/settings.py` | 126-130 | DB localhost/jarvis/diez2030/gallo_db/5432 | No portable/secreto | `.env`/secrets por instalación. |
| `backend/config/settings.py` | 181-205 | localhost/8182/9102/centro-pdg | CORS/CSRF rígidos | `APP_DOMAIN`, `PUBLIC_ORIGIN`, listas completas por env. |
| `frontend/vite.config.ts` | 12-16 | 8182 y 127.0.0.1:8102 | Dev-only | Mantener solo dev; prod por proxy `/api`. |
| `frontend/src/lib/api.ts` | 2 | `VITE_API_BASE ?? /api` | build-time | Runtime config `/config.js` o rutas relativas. |
| `backend/apps/printing/services/system_printer.py` | 9-10 | cola Star y comando `lp` | Linux/CUPS fijo | Configurar cola por env/BD y agente host. |
| `backend/config/settings.py` | 287,293 | `tmp/dte_payloads` | Ruta relativa no persistente | Volumen `/app/var/dte_logs`. |
| `backend/manage.py`, `wsgi.py`, `asgi.py` | 7/5 | `America/El_Salvador` | Correcto pero fijo | Mantener default; permitir `TZ`. |
| `docs/cash-drawer-setup.md` | 47-57 | `/etc/udev`, `sudo udevadm` | Ubuntu host-specific | Documentar como modo Ubuntu nativo/host, no Windows. |

## 7. Dependencias nativas

Python dependencies relevantes:

- `psycopg2-binary`: conexión PostgreSQL. En imagen slim se puede usar binary, pero para producción preferir `psycopg` o compilar con `libpq-dev`, `gcc`.
- `Pillow`: requiere librerías de imagen (`libjpeg`, `zlib`, `libpng`, `freetype` según wheel/base).
- `python-escpos`, `pyusb`: requiere `libusb-1.0-0`, permisos `/dev/bus/usb` y reglas udev en host Linux.
- `reportlab`, `qrcode`, `pypdf`: PDF/QR; ReportLab puede requerir fuentes disponibles.
- `requests`, `python-dotenv`: sin paquetes nativos relevantes.

Paquetes Debian/Ubuntu mínimos recomendados para backend container:

```text
ca-certificates curl tzdata locales libpq5 libjpeg62-turbo zlib1g libpng16-16 libfreetype6 libusb-1.0-0 cups-client fonts-dejavu-core
```

Si se compilan wheels dentro del builder:

```text
build-essential gcc python3-dev libpq-dev libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev libusb-1.0-0-dev
```

No se encontraron WeasyPrint, wkhtmltopdf, Cairo, Pango ni libmagic en `requirements.txt`.

## 8. Frontend

- La URL API se define como `import.meta.env.VITE_API_BASE ?? "/api"`.
- En desarrollo Vite proxya `/api` a `http://127.0.0.1:8102`.
- En producción, si `VITE_API_BASE` se define al compilar, queda embebido en JS. Cambiar `.env` tras `npm run build` **no** cambia la URL.
- Si se usa default `/api`, puede servirse detrás de Caddy/Nginx con proxy inverso sin recompilar por dominio.
- Media se resuelve por paths relativos `/media/...` y `window.location.origin`, compatible con proxy si `/media` apunta a backend/volumen.
- No se encontraron WebSockets.
- Descargas PDF/ZIP se hacen por endpoints API y Blob; requieren cookies/CSRF y proxy con timeouts adecuados.
- Build puede servirse desde Caddy/Nginx como SPA (`try_files /index.html`).
- No hay dependencia de Node en runtime si se sirve `dist`.

Propuesta runtime sin implementar: usar rutas relativas por defecto (`/api`, `/media`) y un archivo `window.__APP_CONFIG__` servido por el proxy (`/config.js`) para overrides de nombre de instalación/dominio sin recompilar. Mantener `VITE_*` solo para dev/debug.

## 9. Django

- Producción actual no está separada: `DEBUG` default true, `SECRET_KEY` default dev.
- `STATIC_URL=/static/`, `STATIC_ROOT=BASE_DIR/static`; collectstatic no está documentado en secuencia de arranque.
- `MEDIA_URL=/media/`, `MEDIA_ROOT=BASE_DIR/media`; media se crea al importar settings.
- `urls.py` sirve media solo en DEBUG.
- No hay Gunicorn/Uvicorn en dependencias.
- CORS/CSRF permiten credenciales y dominios default.
- `USE_X_FORWARDED_HOST=True` y `SECURE_PROXY_SSL_HEADER` están listos para proxy HTTPS, pero requieren configurar hosts/orígenes.
- Sesiones usan DB (`django.contrib.sessions.backends.db`).
- PostgreSQL usa timezone `America/El_Salvador` en options.
- Migraciones existen por app; `initdb`, `dbcheck`, `schemacheck`, `createadmin` son comandos útiles para bootstrap.
- Logs: consola y logger `apps.dte`; logs DTE a archivo opcional deben persistirse.
- Zona horaria de El Salvador está configurada en Django y setdefault `TZ`.

## 10. PostgreSQL

- Compatible por Django 5.1 con PostgreSQL moderno; versión real del servidor actual no está en repo.
- Apps usan `django.contrib.postgres`, JSONField e índices/constraints estándar; no se detectó extensión PostgreSQL explícita (`CREATE EXTENSION`) en migraciones inspeccionadas por búsqueda.
- Encoding/locale/timezone no declarados para creación de base. Recomendado: `UTF8`, `C.UTF-8` o `es_SV.UTF-8` si disponible, TZ `America/El_Salvador`.
- Datos esperados: BD transaccional POS + DTE + inventario; media/PDF fuera de DB.
- Scripts manuales: `geo_catalogs.sql`, `backup_menu_data.sql`, `gallo.dump` y `_backup/`/`_local_backup_git_conflicts/` requieren clasificación antes de empaquetar.

Estrategia comprobable backup/restore:

```sh
pg_dump --format=custom --no-owner --no-acl --file backups/picopos_$(date +%Y%m%d_%H%M%S).dump "$DATABASE_URL"
pg_restore --list backups/archivo.dump > backups/archivo.list
createdb -E UTF8 -T template0 gallo_restore_test
pg_restore --dbname=gallo_restore_test --no-owner --no-acl backups/archivo.dump
python backend/manage.py migrate --check
python backend/manage.py check_dte_counters
```

Para Docker: ejecutar backup antes de `compose pull/up`, retener N copias, probar restore en contenedor temporal y documentar rollback.

## 11. DTE y servicios externos

- DTE principal usa `DTE_BASE_URL`, token/header/prefix y endpoints documentados para factura/CCF/sujeto excluido/nota crédito/invalidación.
- Bridge legado usa `DTE_BRIDGE_BASE_URL`, `DTE_BRIDGE_TOKEN`, `DTE_BRIDGE_MODE`.
- WhatsApp y correo se configuran por `WHATSAPP_DTE_API_BASE`/`WHATSAPP_DTE_API_KEY` y `DELIVER_EMAIL_API_BASE_URL`/`DELIVER_EMAIL_API_KEY`.
- Persistencia DTE: `DTERecord`, `DTETransmissionLog`, `DTEOutbox`, `DTEInvalidation`, `CreditNote`, `DteInvalidationAttempt`, `DteDeliveryAttempt` están en PostgreSQL.
- Reintentos: `DTEOutbox` tiene status/attempts/next_attempt_at; `dte_autoresend` reintenta pendientes; monitor/outbox arrancan en `AppConfig.ready()` bajo `RUN_MAIN`.
- Sin internet: el diseño conserva estados pendientes/fallidos en DB, por lo que reiniciar contenedores **no debería perder DTE pendientes** si PostgreSQL persiste y si no hay transacciones a medio commit. Riesgo: workers múltiples pueden duplicar intentos si no hay locking suficiente.
- JSON/PDF: payloads DTE están en DB; PDFs de recibos se guardan en `MEDIA_ROOT/receipts`. Logs de payload opcionales deben estar en volumen si se activan.

## 12. Impresión

- Impresión actual backend: endpoints `/api/printing/jobs/` crean trabajos; `SystemPrinterService` imprime texto/PDF con CUPS (`lpstat`, `lp`) y fallback PDF en `media/receipts`.
- Cajón/USB: docs describen `python-escpos`, `pyusb`, `lsusb`, reglas udev y endpoints cashier.
- Cola fija actual: `TSP143-(STR_T-001)`.
- Si impresora desconectada o cola no existe, backend devuelve error y genera PDF fallback en algunos flujos.
- Impresora de red: viable si CUPS dentro del contenedor/host tiene cola IPP/socket configurada, o si el agente nativo imprime por red.
- USB en Ubuntu Docker: requiere montar `/dev/bus/usb`, `--privileged` o reglas específicas, `libusb`, grupo/permisos; no recomendado para primera fase.
- Windows Docker Desktop/WSL2: acceso USB y CUPS desde contenedor Linux a impresora Windows no es confiable. **Se recomienda agente de impresión nativo para Windows** (servicio/PowerShell/.NET/Node) que reciba jobs por HTTP local o lea cola DB/API y use drivers Windows.

## 13. Persistencia

| Tipo | Ejemplos | Clasificación | Docker volumen/secreto |
|---|---|---|---|
| Código | `backend/apps`, `frontend/src` | Inmutable | imagen |
| Configuración | `.env`, dominios, puertos | Config | env files por instalación |
| Secretos | DB password, DTE tokens, email/WhatsApp keys, secret key | Secreto | Docker secrets o archivos protegidos |
| Base de datos | PostgreSQL | DB | volumen `postgres_data` + backups |
| Media | `backend/media/menu_image`, `categories`, uploads | Persistente | volumen `media_data` |
| Static | `backend/static`, frontend dist | Generado/inmutable | imagen o volumen readonly |
| Logos | ticket logo/media/assets | Persistente si editable | `media_data` |
| DTE JSON | payloads DB, logs opcionales | DB/log persistente | DB + `dte_logs` si a archivo |
| PDF | `backend/media/receipts` | Persistente | `media_data` |
| Certificados/firma | no se detectaron rutas explícitas en código; si existen deben ser secretos | Secreto | secret/volumen readonly |
| Reportes | PDFs/exports API | Temporal/persistente según negocio | `media_data` o temp |
| Logs | consola, DTE file optional | Log | stdout + volumen opcional |
| Temporales | `tempfile`, `/tmp`, `tmp/dte_payloads` | Temporal/log | tmpfs/volumen si se necesita retención |
| Backups | `gallo.dump`, futuros dumps | Backup | carpeta externa no borrada por uninstall |

## 14. Compatibilidad Windows

Riesgos:

- CRLF/LF: Python/TS toleran; scripts `.sh` futuros deben usar LF.
- Permisos ejecutables: Git en Windows puede perder bit executable; invocar scripts con `bash script.sh` o usar PowerShell.
- Case sensitivity: Linux containers son case-sensitive; Windows bind mounts no siempre. Evitar nombres que difieran solo por mayúsculas.
- Rutas con espacios/backslashes: usar rutas POSIX dentro contenedores; no poner `C:\...` en settings Django.
- UTF-8: configurar `PYTHONUTF8=1`, locale `C.UTF-8`, Postgres UTF8.
- Bind mounts: performance y bloqueo por antivirus; preferir volúmenes nombrados para DB/media.
- Puertos ocupados: 80/443/5432/8102/8182 pueden colisionar; compose windows debe permitir overrides.
- Firewall: abrir puerto público del proxy si otras PCs accederán.
- Reinicios Windows/Docker Desktop: configurar restart policies y procedimiento de arranque.
- Acceso LAN: usar IP del host Windows/proxy, `ALLOWED_HOSTS`, CSRF/CORS y firewall correctos.
- Impresión: requiere agente nativo o impresora de red; no depender de USB directo en contenedor.

## 15. Compatibilidad Ubuntu

No modificar despliegue actual. Deben coexistir tres modos:

1. **Ubuntu nativo actual:** systemd/Caddy/DB existentes fuera del repo; no se tocan.
2. **Ubuntu Docker opcional:** compose con puertos alternos o proxy dedicado; puede usar Postgres contenedor o DB externa. Impresión USB solo si se configura explícitamente.
3. **Windows Docker:** compose Windows con volúmenes nombrados, proxy y agente de impresión nativo/recomendado.

El modo Docker debe usar nombres de proyecto y puertos que no colisionen con el modo nativo hasta que se planifique migración.

## 16. Cambios mínimos necesarios

1. Añadir configuración env-driven segura: `ALLOWED_HOSTS`, secret required en prod, DB URL opcional.
2. Separar procesos: web, DTE worker/monitor y comandos admin.
3. Añadir Gunicorn y health endpoint.
4. Servir frontend con rutas relativas y runtime config opcional.
5. Externalizar media/static/logs/backups a volúmenes.
6. Definir estrategia de impresión Windows (agente) antes de producción.
7. Versionar Dockerfiles/compose sin tocar systemd/Caddy existentes.
8. Definir backup/restore/rollback scripts.

## 17. Archivos que deberán modificarse (fase futura, no en esta auditoría)

- `backend/config/settings.py`: configuración env segura, hosts, paths, static/media/logs.
- `backend/config/urls.py` o app core: endpoint health.
- `backend/requirements.txt`: servidor WSGI y posiblemente psycopg moderno.
- `backend/apps/dte/apps.py`/nuevo management command: sacar workers del ciclo web.
- `frontend/src/lib/api.ts`: runtime config si se decide no usar solo `/api`.
- `frontend/vite.config.ts`: mantener dev proxy, documentar prod.
- `.gitignore`/dockerignore futuros: excluir venv, media opcional, dumps, caches.

## 18. Archivos nuevos que deberán crearse (fase futura)

- `compose.yaml`, `compose.build.yaml`, `compose.windows.yaml`, `compose.ubuntu.yaml`.
- `backend/Dockerfile`, `frontend/Dockerfile`.
- `docker/proxy/Caddyfile` o `docker/proxy/nginx.conf`.
- `docker/env/*.example`.
- `scripts/windows/*.ps1`: install, start, stop, backup, restore, diagnose, uninstall-sin-borrar-datos.
- `scripts/linux/*.sh`: install, backup, restore, rollback, diagnose.
- `docs/DOCKER_WINDOWS.md`, `docs/DOCKER_UBUNTU.md`, `docs/BACKUP_RESTORE.md`.
- Agente de impresión Windows (repo separado o carpeta `print-agent/`) si se aprueba.

## 19. Arquitectura Docker recomendada

### Compose base

- `db`: `postgres:16`, volumen `postgres_data`, healthcheck `pg_isready`.
- `backend`: imagen versionada `registry/picopos-backend:<version>`, depende de DB healthy, env file, volúmenes `media_data`, `dte_logs`, healthcheck HTTP.
- `dte-worker`: misma imagen backend, comando dedicado, una réplica.
- `frontend`: build multietapa genera estáticos; alternativamente integrado al proxy.
- `proxy`: Caddy/Nginx, expone 80/443 o puerto configurable, sirve SPA, proxy `/api`, `/admin`, `/media`, `/static`.

### Overlays

- `compose.build.yaml`: contextos locales y tags versionados.
- `compose.windows.yaml`: puertos Windows, volúmenes nombrados, no USB, endpoint agente impresión `host.docker.internal` si aplica.
- `compose.ubuntu.yaml`: opcional USB/CUPS o `network_mode`/devices si se aprueba; puertos no conflictivos con nativo.

### Dockerfiles

- Backend multietapa: builder instala wheels; runtime slim con libs nativas, usuario no root, `collectstatic`, `gunicorn`.
- Frontend multietapa: Node LTS build con npm ci; runtime Caddy/Nginx copia `dist`.

### Operación

- Imágenes versionadas y publicadas en registro privado.
- Backup obligatorio antes de actualizar.
- Restore probado con `pg_restore --list` y contenedor temporal.
- Rollback: `compose pull <version anterior>` + restore si migraciones destructivas.
- Diagnóstico: script que recopile `docker compose ps`, healthchecks, logs últimos N, DB check, espacio en disco, conectividad DTE, impresión.
- Desinstalación sin borrar datos: `compose down` sin `-v`; comando separado y explícito para purgar volúmenes.

## 20. Plan de implementación por fases

1. **Fase 0 - Auditoría (esta):** documento, sin cambios funcionales.
2. **Fase 1 - Preparación segura:** settings env, healthcheck, gunicorn, dockerignore, docs de configuración.
3. **Fase 2 - Docker dev/local:** Dockerfiles y compose base con Postgres y proxy, sin impresión USB.
4. **Fase 3 - DTE worker:** separar worker y pruebas de reintento/persistencia.
5. **Fase 4 - Windows:** scripts PowerShell, volúmenes, firewall, agente impresión o impresora red.
6. **Fase 5 - Ubuntu opcional:** compose ubuntu paralelo sin tocar systemd/Caddy nativo.
7. **Fase 6 - Piloto:** backup/restore, actualización/rollback, prueba DTE real controlada.

## 21. Plan de pruebas Windows

- `docker compose -f compose.yaml -f compose.windows.yaml up -d` levanta todos los servicios.
- Healthchecks DB/backend/proxy pasan.
- Acceso desde host y otra PC LAN.
- Login, POS, pago, creación de DTE pendiente/aceptado, retry sin internet y luego con internet.
- Media: subir logo/imagen y verificar persistencia tras restart.
- PDF tickets: generar y descargar tras restart.
- Impresión: impresora red o agente Windows; probar desconexión y fallback.
- Backup/restore en otra carpeta/volumen.
- Reinicio de Windows y Docker Desktop: servicios vuelven sin pérdida.

## 22. Plan de regresión Ubuntu

- No cambiar servicios nativos existentes.
- Ejecutar Docker en puertos alternos.
- Comparar endpoints críticos con `smoketest_api`.
- Validar que DB nativa no se toca si Docker usa DB contenedor.
- Validar Caddy/systemd nativos siguen activos.
- Probar impresión nativa fuera de Docker como baseline.
- Backup antes/después y restore test.

## 23. Criterios exactos de aceptación

- El modo Ubuntu nativo arranca igual que antes y no requiere Docker.
- El modo Windows Docker arranca con un comando documentado y healthchecks verdes.
- Ningún secreto productivo queda en imagen ni commit.
- `ALLOWED_HOSTS`, CORS, CSRF y dominios son configurables por instalación.
- Frontend puede cambiar dominio/IP sin recompilar si usa rutas relativas/runtime config.
- DTE pendiente persiste en PostgreSQL y se reintenta tras restart.
- Backup y restore se prueban con `pg_restore --list` y DB temporal.
- Media/PDF/logs requeridos sobreviven `docker compose down` y restart.
- Impresión tiene decisión explícita: agente Windows o impresora de red; no prometer USB Docker Desktop.
- Desinstalación documentada no borra datos salvo comando de purga separado.

## 24. Evidencia de inspección

Comandos usados durante la auditoría:

```sh
find .. -name AGENTS.md -print
rg --files -g '!node_modules' -g '!venv' -g '!dist' -g '!build'
sed -n '1,260p' backend/config/settings.py
sed -n '220,520p' backend/config/settings.py
sed -n '1,220p' backend/requirements.txt
cat frontend/package.json
cat frontend/vite.config.ts
rg -n "os\.environ|getenv|_env_|import\.meta\.env|VITE_|localhost|127\.0\.0\.1|systemctl|journalctl|sudo|apt|lp\b|usb|serial" backend frontend README.md docs -g '!backend/venv/**' -g '!backend/media/**'
python --version
node --version
npm --version
find . -maxdepth 4 -type f \( -name '*.service' -o -iname '*caddy*' -o -iname '*nginx*' -o -name '*.timer' -o -name '*.sh' \) -print
```

## 25. Confirmación de alcance

No se cambió código funcional, no se modificaron configuraciones existentes de producción, no se eliminó ni reemplazó systemd/Caddy/backend/frontend, no se hizo merge/rebase/reset/checkout destructivo. Solo se creó este archivo de auditoría.
