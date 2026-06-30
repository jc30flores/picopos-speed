# Fase 19: PostgreSQL WinSW Service Account

## Resultado real de 0.1.9-test

La prueba en Windows confirmo que las correcciones anteriores quedaron activas:

- `version.json` reporto `0.1.9-test`.
- `initdb` termino correctamente.
- `configure-postgres` termino correctamente.
- `postgresql.conf` y `pg_hba.conf` quedaron sin UTF-16, sin BOM UTF-8 y sin bytes NUL.
- El foreground test de PostgreSQL paso y escucho temporalmente en `127.0.0.1:5432`.

El nuevo fallo ocurrio en `install-postgres-service`. El XML final de `PicoDeGallo-PostgreSQL` tenia un bloque `serviceaccount`, pero Windows SCM registro el servicio como `LocalSystem`. Al iniciar manualmente, PostgreSQL rechazo ejecutarse bajo una cuenta privilegiada.

## Causa raiz

El instalador confiaba demasiado en el XML final de WinSW. En Windows real, ese XML no fue suficiente para dejar el servicio registrado con la cuenta local `PicoDeGalloSvc`. Para PostgreSQL, la fuente de verdad es `Win32_Service.StartName`, no solo el XML del wrapper.

## Solucion

El instalador ahora:

- renderiza el XML de instalacion de PostgreSQL con `domain`, `user`, `password` y `allowservicelogon`;
- reescribe el XML final sin password;
- valida `Win32_Service.StartName` con `Get-CimInstance`;
- si SCM no quedo en `PicoDeGalloSvc`, corrige la cuenta con `ChangeServiceConfig` de `advapi32.dll`;
- rechaza arrancar PostgreSQL si `StartName` sigue siendo `LocalSystem`, `SYSTEM`, `LocalService`, `NetworkService` o una cuenta administrativa conocida;
- registra `POSTGRES_SERVICE_START_NAME actual=... expected=PicoDeGalloSvc ok=True/False`.

El cambio de cuenta usa API nativa en memoria, no `sc.exe config` con password en argumentos. Esto evita imprimir o persistir la contrasena en logs.

## Seguridad

- La contrasena de `PicoDeGalloSvc` vive solo en memoria durante la instalacion.
- El XML final no contiene `<password>`.
- Los logs se escriben con sanitizacion.
- Despues de instalar se escanean logs relevantes y XML final para asegurar que la contrasena no quedo persistida.
- `install-services-transcript.log` tambien se incluye en la revision.

## Idempotencia desde estado parcial 0.1.9-test

El instalador puede ejecutarse encima del estado parcial dejado por `0.1.9-test`:

- conserva `C:\ProgramData\PicoDeGallo\postgres\data`;
- no vuelve a ejecutar `initdb` si existe `PG_VERSION`;
- reaplica permisos y configuracion PostgreSQL;
- detecta `PicoDeGallo-PostgreSQL` aunque exista como `LocalSystem`;
- detiene, desinstala o elimina el servicio corrupto;
- reinstala PostgreSQL con `PicoDeGalloSvc`;
- continua con base de datos, Django, servicios DTE, Caddy y healthcheck.

## Backend runtime

El diagnostico de `0.1.9-test` tambien mostro un posible `ModuleNotFoundError: No module named 'config'`.

La revision del repo confirma que el backend fuente contiene:

- `backend/manage.py`
- `backend/config/settings.py`
- `backend/config/wsgi.py`
- `backend/apps/core/management/commands/check_runtime_config.py`

Para detectar un payload incompleto antes de migrar, el instalador agrega `validate-backend-runtime`. Ese paso importa `config.settings` y `config.wsgi`, y verifica que Django vea el comando `check_runtime_config`, usando el mismo `DJANGO_ENV_FILE` y `DJANGO_SETTINGS_MODULE` que el instalador.

El empaquetado tambien valida esos archivos dentro del staging del release.

## Como probar 0.1.10-test

Primero instalar encima del estado parcial de `0.1.9-test`, sin borrar `C:\ProgramData\PicoDeGallo`.

Verificaciones principales:

```powershell
Get-CimInstance Win32_Service -Filter "Name='PicoDeGallo-PostgreSQL'" | Select Name,StartName,State
Get-Service PicoDeGallo*
Test-NetConnection 127.0.0.1 -Port 5432
Test-NetConnection 127.0.0.1 -Port 9282
Invoke-WebRequest http://127.0.0.1:9282/api/health/live/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:9282/api/health/ready/ -UseBasicParsing
```

`StartName` debe ser `.\PicoDeGalloSvc` o `<EQUIPO>\PicoDeGalloSvc`.

Despues, si se necesita una prueba limpia, hacerla en VM de pruebas y recrear el entorno manualmente. El instalador no borra datos persistentes.

## Notas

- DTE sigue activo.
- `admin / 000000` es solo para instaladores `0.1.x-test`; no es una recomendacion de produccion.
- No se modifica payload legal DTE ni contadores fiscales.
