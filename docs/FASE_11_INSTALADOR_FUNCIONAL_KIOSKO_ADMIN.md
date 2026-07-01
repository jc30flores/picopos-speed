# Fase 11 - Instalador funcional, kiosko y admin de prueba

## 1. Problemas observados en 0.1.0-test

La prueba en Windows limpia mostro que el instalador copiaba `C:\Program Files\PicoDeGallo` y `C:\ProgramData\PicoDeGallo`, pero no dejaba el sistema operando. `Get-Service *PicoDeGallo*` no devolvia servicios, no habia procesos `postgres`, `caddy`, `python` o `waitress`, y `http://127.0.0.1:9282` rechazaba conexion.

Tambien se observo un fallo de GitHub Actions durante checkout por una ruta invalida para Windows: `:GITHUB_OUTPUT`. Ese archivo fue creado accidentalmente por una redireccion mal escrita y bloqueaba `windows-latest`.

Al ejecutar manualmente `install-services.ps1`, PowerShell fallo en `New-RandomSecret` con una conversion incorrecta de `System.Byte[]` a `System.Int32`.

## 2. Correcciones aplicadas

- Se elimino la ruta versionada `:GITHUB_OUTPUT`.
- Se agrego validacion para bloquear rutas Git incompatibles con Windows.
- `New-RandomSecret` ahora usa `[byte[]]::new($Bytes)` y `RandomNumberGenerator`.
- `install-services.ps1` instala servicios reales con WinSW, no placeholders.
- Se inicializa PostgreSQL en `C:\ProgramData\PicoDeGallo\postgres\data`.
- Se ejecutan `check_runtime_config`, `migrate`, `collectstatic` y `bootstrap_initial_admin`.
- Backend corre con Waitress: `python -m waitress --listen=127.0.0.1:8000 config.wsgi:application`.
- Caddy escucha en `127.0.0.1:9282`.
- Se agrego `open-kiosk.ps1` para abrir Edge en modo kiosko/fullscreen al terminar la instalacion.

## 3. Servicios instalados

El instalador registra y arranca estos servicios:

- `PicoDeGallo-PostgreSQL`
- `PicoDeGallo-Backend`
- `PicoDeGallo-DTE-Worker`
- `PicoDeGallo-DTE-Monitor`
- `PicoDeGallo-Caddy`

DTE sigue activo. El worker y monitor se instalan y arrancan con `DTE_BACKGROUND_MODE=external`. En CI no se contacta Hacienda ni se envian DTE reales.

## 4. Admin inicial de prueba

Para la version `0.1.2-test`, el instalador crea un usuario inicial:

- usuario: `admin`
- clave/PIN: `000000`

Esto se controla desde:

- `PICO_BOOTSTRAP_ADMIN_ENABLED=true`
- `PICO_BOOTSTRAP_ADMIN_USERNAME=admin`
- `PICO_BOOTSTRAP_ADMIN_PASSWORD=000000`

Advertencia: `admin/000000` es solo para pruebas del instalador. En produccion debe cambiarse por una contrasena segura o reemplazarse por un wizard de primer arranque.

## 5. Accesos directos y kiosko

El instalador crea un acceso directo de escritorio llamado `Pico de Gallo` y accesos en Start Menu para abrir, iniciar, detener, ver estado, diagnostico, backup y restore.

Al finalizar una instalacion exitosa, Inno Setup ejecuta `open-kiosk.ps1`. El script espera `http://127.0.0.1:9282/api/health/ready/` y luego:

1. Usa Microsoft Edge en modo kiosko fullscreen si existe.
2. Si se llama con `-AppMode`, usa `msedge.exe --app=http://127.0.0.1:9282`.
3. Si Edge no existe, usa el navegador predeterminado.

Para salir del modo kiosko: `Alt+F4`.

## 6. Logs generados

Los logs se escriben en `C:\ProgramData\PicoDeGallo\logs`:

- `install-services.log`
- `init-env.log`
- `postgres-init.log`
- `postgres-service.log`
- `db-setup.log`
- `check-runtime-config.log`
- `migrate.log`
- `collectstatic.log`
- `bootstrap-admin.log`
- `service-install.log`
- `healthcheck.log`
- `open-kiosk.log`

Los scripts sanitizan passwords, secrets y tokens antes de imprimir o empaquetar diagnosticos.

## 7. Checklist de prueba en Windows limpia

1. Descargar solo `PicoDeGallo-Setup-0.1.2-test.exe`.
2. Ejecutar como administrador.
3. Confirmar que se abre Pico de Gallo automaticamente.
4. Confirmar servicios: `Get-Service *PicoDeGallo*`.
5. Abrir `http://127.0.0.1:9282`.
6. Validar `http://127.0.0.1:9282/api/health/live/`.
7. Validar `http://127.0.0.1:9282/api/health/ready/`.
8. Entrar con `admin` / `000000`.
9. Ejecutar acceso de backup.
10. Ejecutar diagnostico y revisar ZIP.
11. Desinstalar y confirmar que `C:\ProgramData\PicoDeGallo` se conserva por defecto.

## 8. Riesgos pendientes

- Validar manualmente en VM Windows limpia con el instalador final publicado.
- Reemplazar `admin/000000` antes de produccion.
- Configurar credenciales DTE reales solo fuera de CI y fuera del build.
- Firmar el instalador para reducir advertencias de SmartScreen.
