# Fase 23 - Caddy HTTP local sin auto TLS

## Resultado real de 0.1.13-test

La version 0.1.13-test ya dejo funcionando el tramo principal del instalador nativo Windows:

- PostgreSQL embebido/local quedo instalado, configurado y en ejecucion.
- La base `picopos` quedo disponible y las migraciones Django pasaron.
- `collectstatic` y `bootstrap_initial_admin` pasaron.
- Backend, DTE Worker, DTE Monitor y Caddy quedaron instalados como servicios.
- Los puertos 5432, 8000 y 9282 quedaron abiertos.

El fallo restante ocurrio en `healthcheck`: el backend respondia por HTTP directo en 8000, pero la ruta por Caddy en 9282 devolvia HTTP 400.

## Causa raiz

El Caddyfile usaba una direccion local sin esquema. Para Caddy, eso habilito automatic HTTPS para `127.0.0.1`, intento gestionar un certificado local y activo redireccionamientos HTTP a HTTPS. El instalador, el acceso directo y el modo kiosko prueban HTTP simple, por lo que la solicitud HTTP contra el listener TLS devolvia 400.

Este comportamiento tambien provocaba logs de Caddy sobre automatic TLS, root certificate y certificado local para loopback. Para POS local no se desea TLS automatico ni prompts de certificados: la app debe servirse solo en loopback por HTTP.

## Correccion en 0.1.14-test

El Caddyfile nativo ahora declara el contrato local explicitamente:

- `auto_https off` en opciones globales.
- `http://127.0.0.1:<puerto>` como direccion del sitio.
- `bind 127.0.0.1` dentro del bloque.
- Rutas Windows `root` siempre entre comillas.

Con esto Caddy sirve `http://127.0.0.1:9282` sin certificados root locales, sin automatic TLS y sin redireccion HTTPS.

## Seguridad local

La app se publica en loopback. Caddy mantiene bloqueo para archivos sensibles como `.env`, logs, backups, diagnostics, dumps y SQL. Los directorios `static`, `media` y `frontend` se sirven desde las rutas instaladas por el paquete.

El servicio Caddy usa directorios de datos/config bajo `C:\ProgramData\PicoDeGallo\caddy`, para evitar escribir estado bajo el perfil de sistema.

## Idempotencia desde 0.1.13-test parcial

0.1.14-test debe poder instalarse encima del estado parcial de 0.1.13-test:

- No borra `C:\ProgramData\PicoDeGallo`.
- No borra `postgres\data`.
- Revalida PostgreSQL, DB y backend.
- Re-renderiza el Caddyfile con HTTP local.
- Valida Caddyfile.
- Reinstala o reinicia Caddy de forma idempotente.
- Ejecuta healthchecks por backend directo y por Caddy.
- Termina con `phase=complete`, `servicesInstalled=true` y `healthOk=true`.

## DTE

DTE sigue activo. Si `DTE_BASE_URL` o el token son placeholders, worker y monitor reportan `CONFIG_PENDING` y no contactan una API externa falsa. El aviso queda rate-limited usando al menos el backoff de configuracion pendiente. Antes de operar fiscalmente se deben configurar credenciales reales.

## Pruebas

Para validar 0.1.14-test:

1. Instalar encima del estado parcial 0.1.13-test sin borrar ProgramData.
2. Verificar servicios: PostgreSQL, Backend, DTE Worker, DTE Monitor y Caddy.
3. Verificar puertos: 5432, 8000 y 9282.
4. Verificar backend directo:
   - `http://127.0.0.1:8000/api/health/live/`
   - `http://127.0.0.1:8000/api/health/ready/`
5. Verificar Caddy:
   - `http://127.0.0.1:9282/`
   - `http://127.0.0.1:9282/api/health/live/`
   - `http://127.0.0.1:9282/api/health/ready/`
6. Revisar logs de Caddy y confirmar que no aparecen automatic TLS ni intentos de instalar root certificate.
7. Si falla, correr diagnostics de 0.1.14 y revisar `caddyfile-http-local.txt`, `caddy-auto-tls-evidence.txt`, `health.txt` y `netstat-9282-bind.txt`.

## CI

Se agrego `scripts/ci/test_caddyfile_windows_http_local.ps1`. La prueba renderiza el Caddyfile con rutas Windows y valida:

- HTTP local explicito.
- `auto_https off`.
- `bind 127.0.0.1`.
- Ausencia de direccion local sin esquema.
- Rutas `Program Files` entre comillas.
- `caddy validate` cuando `caddy.exe` esta disponible.
- Si Caddy esta disponible, arranque real en un puerto temporal y GET HTTP al frontend.
