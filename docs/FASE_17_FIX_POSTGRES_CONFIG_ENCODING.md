# Fase 17: encoding compatible para configuracion PostgreSQL

## Resultado real de 0.1.7-test

La instalacion nativa `0.1.7-test` corrigio la ejecucion de `initdb` como `PicoDeGalloSvc`:

- `version.json` indico `0.1.7-test`.
- `.env` existia.
- `PicoDeGalloSvc` existia, no era administrador y tenia contrasena no expirable.
- Python runtime funciono.
- Los binarios PostgreSQL funcionaron.
- `initdb` fue exitoso.
- `configure-postgres` fue marcado como exitoso.

El flujo aborto en `postgres-foreground-test`, antes de renderizar XML/EXE finales o instalar servicios.

## Error

`postgres-foreground-test.err.log` mostro:

```text
syntax error in file "C:/ProgramData/PicoDeGallo/postgres/data/postgresql.conf" line 1, near end of line
FATAL: configuration file "C:/ProgramData/PicoDeGallo/postgres/data/postgresql.conf" contains errors
```

## Causa raiz

`postgresql.conf` quedo escrito con un encoding incompatible para PostgreSQL. En Windows PowerShell 5.1, escrituras con `Set-Content` y ciertos valores de `-Encoding` pueden producir BOM o formatos que PostgreSQL no interpreta como texto de configuracion valido.

El caso probable es que `postgresql.conf` se haya reescrito con BOM/UTF-16 o con bytes que PostgreSQL rechazo desde la primera linea.

## Solucion

`install-services.ps1` ahora escribe `postgresql.conf` y `pg_hba.conf` usando helpers dedicados:

- `Write-PostgresConfigText`
- `Write-PostgresConfigLines`
- `Test-PostgresConfigEncoding`

Los archivos se escriben como UTF-8 sin BOM usando `System.Text.UTF8Encoding($false)`.

## Validacion

Antes del foreground test, el instalador valida:

- el archivo no esta vacio;
- no inicia con BOM UTF-16 LE (`FF FE`);
- no inicia con BOM UTF-16 BE (`FE FF`);
- no contiene BOM UTF-8 (`EF BB BF`);
- no contiene bytes NUL;
- contiene valores requeridos como `listen_addresses = '127.0.0.1'` y `port = 5432`.

El diagnostico queda en:

```text
C:\ProgramData\PicoDeGallo\logs\postgres-config-validation.log
```

Logs esperados:

```text
POSTGRES_CONFIG_ENCODING_OK postgresql.conf
POSTGRES_CONFIG_ENCODING_OK pg_hba.conf
POSTGRES_CONFIG_PRE_FOREGROUND_OK postgresql.conf pg_hba.conf
```

## Como probar 0.1.8-test

Para prueba limpia en VM:

1. Desinstalar Pico de Gallo.
2. Borrar manualmente `C:\ProgramData\PicoDeGallo`.
3. Instalar `PicoDeGallo-Setup-0.1.8-test.exe` como administrador.
4. Revisar:

```powershell
Get-Content C:\ProgramData\PicoDeGallo\logs\postgres-config-validation.log -Tail 80
Get-CimInstance Win32_Service -Filter "Name='PicoDeGallo-PostgreSQL'" | Select Name,StartName,State
Get-Service *PicoDeGallo*
```

El foreground test no debe fallar por `syntax error` en la linea 1 de `postgresql.conf`.

## Admin inicial

`admin / 000000` sigue siendo solo credencial de prueba.

## DTE

DTE sigue activo. Esta fase no modifica payload legal DTE, contadores fiscales, worker, monitor, reintentos ni comunicacion con Hacienda.
