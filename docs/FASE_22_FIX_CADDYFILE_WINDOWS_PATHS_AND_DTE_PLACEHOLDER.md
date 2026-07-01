# FASE 22 - Fix Caddyfile Windows paths and DTE placeholder

## Resultado real de 0.1.12-test

La prueba en Windows real confirmó que `0.1.12-test` avanzó bastante más que las versiones anteriores:

- PostgreSQL quedó instalado, configurado y corriendo en `127.0.0.1:5432`.
- La cuenta del servicio PostgreSQL fue `PicoDeGalloSvc`.
- `setup-database`, `check_runtime_config`, `migrate`, `collectstatic` y `bootstrap_initial_admin` pasaron.
- Backend quedó corriendo en `127.0.0.1:8000`.
- `/api/health/live/` y `/api/health/ready/` del backend respondieron `200`.
- DTE Worker y DTE Monitor quedaron instalados como servicios separados.

El fallo nuevo apareció en `render-caddyfile`: Caddy rechazó el `Caddyfile` porque la ruta `C:/Program Files/PicoDeGallo/frontend` quedó sin comillas.

## Causa raíz

El template generaba:

```caddyfile
root * C:/Program Files/PicoDeGallo/frontend
```

Caddy separó esa línea como dos argumentos de path: `C:/Program` y `Files/PicoDeGallo/frontend`. La validación falló con `too many arguments`.

## Corrección

Se agregaron helpers PowerShell compatibles con Windows PowerShell 5.1:

- `ConvertTo-CaddyPath`
- `ConvertTo-CaddyfileLiteral`
- `Quote-CaddyPath`

El instalador ahora renderiza rutas absolutas Windows como literales Caddy:

```caddyfile
root * "C:/ProgramData/PicoDeGallo/static"
root * "C:/ProgramData/PicoDeGallo/media"
root * "C:/Program Files/PicoDeGallo/frontend"
```

`caddy validate --config Caddyfile` sigue siendo obligatorio. Si falla, el instalador guarda `caddy-validate.log`, stdout/stderr fallidos y diagnostics incluye el Caddyfile numerado.

## Idempotencia sobre 0.1.12 parcial

`0.1.13-test` está diseñado para instalarse encima del estado parcial de `0.1.12-test`:

- No borra `C:\ProgramData\PicoDeGallo`.
- No borra `postgres\data`.
- Re-renderiza el Caddyfile corregido.
- Valida Caddy antes de reinstalar servicios web/DTE.
- Reinstala o reutiliza servicios WinSW de forma idempotente.
- Instala e inicia `PicoDeGallo-Caddy`.
- Debe abrir `127.0.0.1:9282` y pasar health vía Caddy.

El orden final queda:

1. Migraciones.
2. `collectstatic`.
3. Bootstrap admin.
4. Render y validate de Caddyfile.
5. Backend.
6. DTE Worker.
7. DTE Monitor.
8. Caddy.
9. Healthchecks.

## DTE placeholder

DTE sigue activo con `DTE_BACKGROUND_MODE=external`. La instalación de prueba puede traer:

```env
DTE_BASE_URL=replace-with-dte-api-base-url
DTE_API_TOKEN=replace-with-dte-api-token
```

Eso se trata como configuración pendiente, no como endpoint real. Worker y Monitor no hacen requests a esa URL y registran:

```text
[DTE] CONFIG_PENDING reason=... action=not_contacting_external_api
```

Las credenciales reales deben configurarse antes de operar fiscalmente. CI y el instalador de prueba no contactan Hacienda ni transmiten DTE reales.

## Prueba requerida

Primero instalar `0.1.13-test` encima del estado parcial de `0.1.12-test`, sin limpiar ProgramData. Verificar:

- `5432` abierto.
- `8000` abierto.
- `9282` abierto.
- Backend live/ready `200`.
- Caddy live/ready `200`.
- Frontend responde en `http://127.0.0.1:9282/`.
- `install-state.json` termina con `phase=complete`, `servicesInstalled=true`, `healthOk=true`.

Si falla, correr diagnóstico `0.1.13` y revisar `caddyfile-numbered.txt`, `caddy-validate-stdout.txt`, `caddy-validate-stderr.txt`, `runtime-ports.json`, `install-state.json` y logs de servicios.
