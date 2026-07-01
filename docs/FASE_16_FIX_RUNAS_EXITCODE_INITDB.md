# Fase 16: exit code confiable para initdb como cuenta de servicio

## Resultado real de 0.1.6-test

La instalacion nativa de Windows `0.1.6-test` avanzo mas que las versiones anteriores:

- `version.json` instalado indico `0.1.6-test`.
- `.env` se creo correctamente.
- `init-env` fue exitoso.
- `PicoDeGalloSvc` se creo correctamente.
- `PicoDeGalloSvc` no era administrador y pertenecia a `Usuarios`.
- Las ACL se aplicaron.
- Python embeddable importo `django`, `waitress`, `psycopg2` y `requests`.
- Los binarios PostgreSQL 16.14 respondieron correctamente.
- `initdb` se ejecuto como `PicoDeGalloSvc` y escribio el mensaje de exito de PostgreSQL.

El instalador fallo despues de `initdb` con:

```text
STEP_ERROR initdb Comando como PicoDeGalloSvc fallo con codigo .
```

## Causa raiz

`initdb` no fallo. Fallo la captura del exit code.

`Start-Process -Credential` no entrego un `$process.ExitCode` confiable en ese entorno. El proceso termino bien, pero el instalador interpreto un exit code vacio como error y aborto antes de renderizar XML finales, copiar wrappers WinSW, instalar servicios, generar `Caddyfile`, iniciar PostgreSQL, migrar y crear el admin inicial.

## Solucion

`Invoke-AsPicoServiceAccount` ahora ejecuta los comandos esperados a terminar mediante un wrapper PowerShell temporal bajo `PicoDeGalloSvc`.

El wrapper:

- ejecuta el EXE real con sus argumentos;
- redirige stdout/stderr;
- captura `$LASTEXITCODE`;
- si `$LASTEXITCODE` queda nulo sin excepcion, usa `0`;
- escribe `runas-<guid>.exitcode`;
- escribe `runas-<guid>.done`;
- sale con el codigo capturado.

El instalador lee el archivo sentinel `.exitcode` y ya no depende de `$process.ExitCode` como unica fuente para procesos lanzados con `-Credential`.

## Cuenta de servicio

`PicoDeGalloSvc` mantiene una contrasena aleatoria solo en memoria. La instalacion ahora valida que la contrasena no expire usando `PasswordNeverExpires` y fallback con `PasswordExpires=False` cuando aplique.

La descripcion se redujo a:

```text
Servicio local Pico de Gallo
```

Esto evita el limite observado de 48 caracteres en Windows localizado.

## Directorio de datos PostgreSQL

`Initialize-PostgresDataDirectory` es idempotente:

- si existen `PG_VERSION`, `postgresql.conf` y `pg_hba.conf`, continua sin reinicializar;
- si el directorio existe pero esta incompleto, falla con mensaje claro;
- no borra datos automaticamente.

Esto permite que una instalacion interrumpida despues de un `initdb` exitoso pueda continuar en `0.1.7-test`.

## Como probar 0.1.7-test

Para una prueba limpia en VM:

1. Desinstalar Pico de Gallo si existe.
2. Borrar manualmente `C:\ProgramData\PicoDeGallo`.
3. Instalar `PicoDeGallo-Setup-0.1.7-test.exe` como administrador.
4. Verificar:

```powershell
Get-CimInstance Win32_Service -Filter "Name='PicoDeGallo-PostgreSQL'" | Select Name,StartName,State
Get-Service *PicoDeGallo*
Get-LocalUser PicoDeGalloSvc | Select Name,Enabled,PasswordExpires
```

`PicoDeGallo-PostgreSQL` debe correr como `.\PicoDeGalloSvc`, no como `LocalSystem`, y `PasswordExpires` debe estar vacio o indicar que no expira.

## Admin inicial

`admin / 000000` sigue siendo credencial solo para pruebas.

## DTE

DTE sigue activo. Esta fase no modifica payload legal DTE, contadores fiscales, reintentos, worker, monitor ni comunicacion con Hacienda.
