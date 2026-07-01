# Fase 14: PostgreSQL con cuenta Windows no administradora

## Resultado real de 0.1.4-test

La instalacion nativa confirmo que `version.json` decia `0.1.4-test`, que la plantilla WinSW ya ejecutaba directamente:

```powershell
C:\Program Files\PicoDeGallo\postgres\bin\postgres.exe -D "C:\ProgramData\PicoDeGallo\postgres\data"
```

Tambien se confirmo que los binarios PostgreSQL 16.14, Python embeddable y las dependencias Django funcionaban, y que `initdb` terminaba correctamente.

El bloqueo real aparecio al arrancar PostgreSQL:

```text
Execution of PostgreSQL by a user with administrative permissions is not permitted.
The server must be started under an unprivileged user ID.
```

## Causa raiz

PostgreSQL para Windows no debe ejecutarse como administrador, `LocalSystem` ni otra cuenta con permisos administrativos. El instalador corre elevado y el servicio WinSW estaba quedando en un contexto privilegiado, por lo que `postgres.exe` abortaba antes de escuchar en `5432`.

## Solucion en 0.1.5-test

El instalador crea o actualiza el usuario local no administrador `PicoDeGalloSvc`. La contrasena se genera aleatoriamente en memoria, no se imprime, no se escribe en `.env`, no queda en logs y no queda en el XML final.

El usuario `PicoDeGalloSvc` se usa para:

- `initdb.exe`
- prueba foreground de `postgres.exe`
- servicio Windows `PicoDeGallo-PostgreSQL`

El XML temporal de WinSW incluye la contrasena solo durante `install`. Despues se reescribe el XML final con `serviceaccount` sin campo `password` y `autoRefresh=false` para que los arranques posteriores no intenten reconfigurar la cuenta sin credencial.

## Permisos

El instalador aplica ACLs especificas:

- `C:\ProgramData\PicoDeGallo\postgres`: Full para `PicoDeGalloSvc`
- `C:\ProgramData\PicoDeGallo\logs`: Modify para `PicoDeGalloSvc`
- `C:\Program Files\PicoDeGallo\postgres`: Read/Execute para `PicoDeGalloSvc`
- `C:\Program Files\PicoDeGallo\services`: Read/Execute para `PicoDeGalloSvc`

No se usa `Everyone Full`.

## Verificacion

En Windows, despues de instalar:

```powershell
Get-CimInstance Win32_Service -Filter "Name='PicoDeGallo-PostgreSQL'" |
  Select Name,StartName,State
```

`StartName` debe ser similar a:

```text
.\PicoDeGalloSvc
```

No debe ser `LocalSystem`, `NT AUTHORITY\SYSTEM`, `Administrador` ni el usuario administrador de caja.

Tambien revisar:

```powershell
C:\ProgramData\PicoDeGallo\logs\postgres-foreground-test.err.log
C:\ProgramData\PicoDeGallo\logs\PicoDeGallo-PostgreSQL.err.log
C:\ProgramData\PicoDeGallo\logs\PicoDeGallo-PostgreSQL.wrapper.log
```

El error de permisos administrativos de PostgreSQL no debe aparecer.

## Prueba limpia de 0.1.5-test

Para una prueba desde cero, desinstalar la version anterior, detener servicios si quedaron vivos y borrar manualmente `C:\ProgramData\PicoDeGallo` solo si se quiere descartar datos de prueba.

Instalar `0.1.5-test`, esperar a que termine el instalador y validar:

- `status.ps1` muestra `PicoDeGallo-PostgreSQL=Running StartName=.\PicoDeGalloSvc`.
- `POSTGRES_XML_SERVICEACCOUNT=present-no-password`.
- `POSTGRES_FOREGROUND_TEST_RUN_AS=PicoDeGalloSvc`.
- `http://127.0.0.1:9282/api/health/ready/` responde OK.

La cuenta `admin/000000` sigue siendo solo para prueba inicial y debe cambiarse antes de uso real.

DTE sigue activo: los servicios `PicoDeGallo-DTE-Worker` y `PicoDeGallo-DTE-Monitor` se instalan y arrancan despues de que PostgreSQL, migraciones y backend pasen las validaciones.
