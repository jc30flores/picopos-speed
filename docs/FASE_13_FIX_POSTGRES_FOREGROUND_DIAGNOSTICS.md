# Fase 13: diagnostico foreground de PostgreSQL

## Resultado real de 0.1.3-test

La prueba limpia confirmo que `version.json` mostraba `0.1.3-test` y que los servicios `PicoDeGallo-*` si existian, pero todos quedaban `Stopped`.

No escuchaban los puertos `5432`, `8000` ni `9282`, y no habia procesos `postgres`, `caddy`, `python` ni `waitress`.

El XML instalado de PostgreSQL ya apuntaba a:

```text
C:\Program Files\PicoDeGallo\postgres\bin\postgres.exe
```

con argumentos:

```text
-D "C:\ProgramData\PicoDeGallo\postgres\data"
```

`initdb` completo correctamente, pero `postgres.exe` se cerraba poco despues de arrancar y WinSW reiniciaba el proceso en bucle. Los otros servicios no arrancaban porque PostgreSQL no quedaba escuchando.

## Cambio

`install-services.ps1` ahora valida el runtime PostgreSQL con:

```powershell
postgres.exe --version
initdb.exe --version
psql.exe --version
```

Despues de `initdb` y de escribir `postgresql.conf`/`pg_hba.conf`, el instalador ejecuta una prueba controlada:

```powershell
postgres.exe -D "C:\ProgramData\PicoDeGallo\postgres\data"
```

La deja correr unos 10 segundos. Si sigue viva, la detiene y continua con WinSW. Si sale antes, aborta la instalacion antes de `migrate`, backend, DTE y Caddy.

Los logs principales de esa prueba son:

```text
C:\ProgramData\PicoDeGallo\logs\postgres-foreground-test.out.log
C:\ProgramData\PicoDeGallo\logs\postgres-foreground-test.err.log
```

Tambien se archivan logs anteriores en:

```text
C:\ProgramData\PicoDeGallo\logs\archive\YYYYMMDD-HHMMSS
```

asi los mensajes viejos no se mezclan con una instalacion nueva.

## Configuracion PostgreSQL

El instalador fuerza:

```text
listen_addresses = '127.0.0.1'
port = DB_PORT
timezone = 'America/El_Salvador'
logging_collector = off
```

`pg_hba.conf` queda con autenticacion SCRAM para loopback IPv4 e IPv6:

```text
host all all 127.0.0.1/32 scram-sha-256
host all all ::1/128 scram-sha-256
```

No se escriben contrasenas en logs.

## Como probar 0.1.4-test

1. Instalar `PicoDeGallo-Setup-0.1.4-test.exe` en una VM Windows limpia.
2. Verificar servicios:

```powershell
Get-Service *PicoDeGallo*
```

3. Verificar puertos:

```powershell
Test-NetConnection 127.0.0.1 -Port 5432
Test-NetConnection 127.0.0.1 -Port 9282
```

4. Verificar health:

```powershell
Invoke-WebRequest http://127.0.0.1:9282/api/health/live/
Invoke-WebRequest http://127.0.0.1:9282/api/health/ready/
```

5. Abrir:

```text
http://127.0.0.1:9282
```

6. Login de prueba:

```text
usuario: admin
clave: 000000
```

## Si PostgreSQL falla

Revisar primero:

```powershell
Get-Content C:\ProgramData\PicoDeGallo\logs\postgres-foreground-test.err.log -Tail 120
Get-Content C:\ProgramData\PicoDeGallo\logs\postgres-service.log -Tail 120
Get-Content C:\ProgramData\PicoDeGallo\logs\service-install.log -Tail 160
```

`status.ps1` tambien muestra si el XML instalado usa `postgres.exe`, el estado de servicios, los puertos `5432`, `8000` y `9282`, health directo del backend y health via Caddy.

DTE sigue activo con worker y monitor separados. El workflow de build no envia DTE reales, no contacta Hacienda, no cambia payload legal y no cambia contadores fiscales.
