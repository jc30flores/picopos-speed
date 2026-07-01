# FASE 20 - PowerShell native stderr and backend preflight

## Resultado de 0.1.10-test

- PostgreSQL quedo operativo en Windows real.
- `PicoDeGallo-PostgreSQL` quedo ejecutando como `.\PicoDeGalloSvc`, no como una cuenta privilegiada del sistema.
- El puerto `5432` abrio y `setup-database` completo.
- El instalador se detuvo en `validate-backend-runtime` antes de `migrate`, `collectstatic`, bootstrap admin y servicios Backend/DTE/Caddy.

## Causa raiz

Windows PowerShell 5.1 puede convertir salida `stderr` de un comando nativo en `NativeCommandError` cuando el script corre con `$ErrorActionPreference = "Stop"`. El runner anterior ejecutaba comandos con redireccion de PowerShell y podia saltar al `catch` antes de evaluar `$LASTEXITCODE`.

Durante imports de Django, DTE emitia el aviso informativo `[DTE] background startup skipped mode=external` por logging de consola, que por defecto usa `stderr`. El proceso terminaba con codigo `0`, pero el instalador lo trataba como fallo de lanzamiento.

## Solucion

- `Invoke-LoggedCommand` ahora usa `System.Diagnostics.Process` con `UseShellExecute = false`.
- `stdout` y `stderr` se capturan por separado y se loguean con `STDOUT_BEGIN/END`, `STDERR_BEGIN/END` y `EXIT_CODE`.
- La decision de exito se basa en `ExitCode`.
- Si `ExitCode=0` y hay `stderr`, se registra `COMMAND_STDERR_NONFATAL` y el instalador continua.
- Si `ExitCode` es distinto de `0`, se preservan artefactos claros `failed-<step>-stdout.log` y `failed-<step>-stderr.log`, mas tails sanitizados.
- El preflight Django usa `PICO_INSTALLER_PREFLIGHT=1`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `DJANGO_SETTINGS_MODULE=config.settings`, `DJANGO_ENV_FILE` y `DOTENV_OVERRIDE=false`.
- El aviso DTE de background externo queda en `logger.debug` y se suprime durante preflight.

## Seguridad

- Los logs pasan por `Protect-Text`.
- No se escriben passwords, tokens ni secrets en logs.
- Las variables de entorno del runner se reportan por nombre, no por valor.
- El build no contacta Hacienda y no envia DTE reales.

## Idempotencia

0.1.11-test debe instalar encima del estado parcial de 0.1.10-test sin borrar `ProgramData`, `postgres\data` ni bases de datos. Si `PG_VERSION` existe, el flujo reusa el cluster, reaplica configuracion segura, revalida PostgreSQL y continua con backend.

## Siguientes pasos cubiertos

- `validate-backend-runtime` valida payload, imports, `manage.py help check_runtime_config`, `check_runtime_config` y `SELECT 1`.
- Despues siguen `migrate`, `collectstatic`, bootstrap admin de prueba para 0.1.x test, servicios Backend/DTE/Caddy y healthchecks.
- DTE sigue activo en modo externo con worker y monitor como servicios separados.

## Pruebas agregadas

- `scripts/ci/test_native_command_runner.ps1` cubre stdout, `stderr` con codigo `0`, stdout+stderr, `stderr` con codigo `5`, working directory con espacios, environment temporal y redaccion de secrets.
- El workflow `windows-native-installer.yml` ejecuta la prueba antes de construir el payload.
