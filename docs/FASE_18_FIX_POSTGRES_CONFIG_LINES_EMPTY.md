# Fase 18: lineas vacias en configuracion PostgreSQL

## Resultado real de 0.1.8-test

La prueba de `0.1.8-test` confirmo que la correccion de encoding funciono:

- `postgresql.conf` no tenia bytes NUL.
- No tenia BOM UTF-16.
- No tenia BOM UTF-8.
- `initdb` termino correctamente y dejo `PG_VERSION`.

El instalador fallo despues, en `configure-postgres`:

```text
STEP_ERROR configure-postgres No se puede enlazar el argumento con el parametro 'Lines' porque es una cadena vacia.
```

El error nacio en `Write-PostgresConfigLines`, llamado desde `Set-PostgresConfigValue`.

## Causa raiz

`postgresql.conf` y `pg_hba.conf` contienen lineas vacias normales. En Windows PowerShell 5.1, un parametro obligatorio `string[]` puede rechazar elementos `""` durante el binding. Por eso el script fallo antes de reescribir `postgresql.conf`, aunque el archivo tenia encoding valido.

## Solucion

`Write-PostgresConfigLines` ahora:

- acepta lineas vacias internas;
- no usa `ValidateNotNullOrEmpty`;
- no marca `Lines` como parametro obligatorio;
- normaliza con `@($Lines)`;
- escribe con UTF-8 sin BOM;
- mantiene newline final CRLF para archivos `.conf`.

`Set-PostgresConfigValue` ahora:

- preserva comentarios y lineas vacias;
- reemplaza solo la primera ocurrencia activa o comentada de la clave;
- agrega la clave al final si no existe;
- evita producir un archivo vacio por error;
- registra `POSTGRES_CONFIG_SET key=... replaced=True/False`.

## Validacion

Se agrego `scripts/ci/test_postgres_config_lines.ps1`. El test extrae las funciones reales desde `install-services.ps1`, edita un `postgresql.conf` temporal con lineas vacias y valida:

- las lineas vacias se preservan;
- no hay BOM UTF-16;
- no hay BOM UTF-8;
- no hay bytes NUL;
- el archivo termina con CRLF.

El workflow `windows-native-installer.yml` ejecuta este test antes de construir el instalador.

## Reinstalacion parcial

Si `initdb` ya termino y existe `PG_VERSION`, el instalador no borra ni recrea `C:\ProgramData\PicoDeGallo\postgres\data`. Puede re-ejecutar `configure-postgres` y continuar desde el estado parcial.

## DTE

DTE sigue activo. Esta fase no modifica payload legal DTE, contadores fiscales, worker, monitor, reintentos ni comunicacion con Hacienda.

## Admin inicial

`admin / 000000` sigue siendo credencial solo para pruebas.
