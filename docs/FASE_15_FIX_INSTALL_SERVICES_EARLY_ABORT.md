# Fase 15: install-services robusto en Windows localizado

## Resultado real de 0.1.5-test

La instalacion nativa copio archivos y creo `C:\ProgramData\PicoDeGallo\config\.env`. `init-env.log` termino con `INIT_ENV_SUCCESS`, pero `install-services.log` solo dejo `INSTALL_SERVICES_BEGIN`.

No se instalaron servicios `PicoDeGallo-*`, no se generaron XML finales en `C:\Program Files\PicoDeGallo\services`, no se creo `PicoDeGalloSvc` y tampoco se genero `C:\Program Files\PicoDeGallo\caddy\Caddyfile`.

## Causa raiz

El instalador abortaba despues de `init-env` y antes de renderizar servicios. La prueba real mostro Windows en espanol: comandos de grupo local con nombres ingleses como `Administrators` o `Users` no aplican en ese entorno.

Ademas `install-services.ps1` no tenia un `try/catch` final alrededor del flujo principal, por lo que una excepcion temprana podia dejar solo `INSTALL_SERVICES_BEGIN` sin stack trace ni paso fallido.

## Correccion

`install-services.ps1` ahora usa `Invoke-InstallStep` para registrar:

- `STEP_BEGIN`
- `STEP_SUCCESS`
- `STEP_ERROR`

El catch final escribe detalles completos en:

- `C:\ProgramData\PicoDeGallo\logs\install-services.log`
- `C:\ProgramData\PicoDeGallo\logs\install-services-error.log`

Los detalles incluyen fase, ultimo paso, tipo de excepcion, mensaje, linea y script stack trace.

La cuenta local `PicoDeGalloSvc` se crea o actualiza sin depender de nombres de grupos en ingles. Para grupos builtin se usan SIDs:

- `S-1-5-32-544`: grupo administrativo builtin
- `S-1-5-32-545`: grupo estandar builtin

El nombre localizado se resuelve desde el SID cuando hace falta llamar a APIs o `net localgroup`.

## Servicios y Caddyfile

El instalador valida templates, copia `winsw.exe` por servicio, renderiza cada XML final y falla si falta algun `.exe` o `.xml`, o si queda un placeholder `{{...}}`.

Tambien renderiza `C:\Program Files\PicoDeGallo\caddy\Caddyfile` desde `Caddyfile.template` antes de instalar Caddy. Si el template falta o el archivo final no se genera, la instalacion falla con error claro.

## PostgreSQL

PostgreSQL sigue ejecutandose como `PicoDeGalloSvc`:

- `initdb.exe`
- prueba foreground
- servicio `PicoDeGallo-PostgreSQL`

El error de PostgreSQL por usuario privilegiado no debe aparecer:

```text
Execution of PostgreSQL by a user with administrative permissions is not permitted.
```

## Como probar 0.1.6-test

Para una prueba limpia, desinstalar la version previa y borrar manualmente `C:\ProgramData\PicoDeGallo` solo si se quieren descartar datos de prueba.

Despues de instalar `0.1.6-test`, verificar:

```powershell
Get-Service *PicoDeGallo*
Get-CimInstance Win32_Service -Filter "Name='PicoDeGallo-PostgreSQL'" |
  Select Name,StartName,State
Test-Path "C:\Program Files\PicoDeGallo\services\PicoDeGallo-PostgreSQL.xml"
Test-Path "C:\Program Files\PicoDeGallo\caddy\Caddyfile"
Get-Content "C:\ProgramData\PicoDeGallo\logs\install-services.log" -Tail 120
```

`StartName` de PostgreSQL debe ser similar a `.\PicoDeGalloSvc`.

La cuenta inicial `admin/000000` sigue siendo solo para pruebas y debe cambiarse antes de uso real.

DTE sigue activo: `PicoDeGallo-DTE-Worker` y `PicoDeGallo-DTE-Monitor` se instalan y arrancan despues de PostgreSQL, migraciones, bootstrap y backend.
