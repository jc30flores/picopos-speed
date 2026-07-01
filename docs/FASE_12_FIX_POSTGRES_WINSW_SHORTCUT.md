# Fase 12: fix PostgreSQL WinSW y acceso directo

## Resultado de prueba 0.1.2-test

La prueba en Windows limpia confirmo que el instalador copiaba archivos en `C:\Program Files\PicoDeGallo` y `C:\ProgramData\PicoDeGallo`, y que registraba los cinco servicios esperados:

- `PicoDeGallo-PostgreSQL`
- `PicoDeGallo-Backend`
- `PicoDeGallo-DTE-Worker`
- `PicoDeGallo-DTE-Monitor`
- `PicoDeGallo-Caddy`

El problema fue que todos quedaban `Stopped`. No escuchaban los puertos `5432`, `8000` ni `9282`, y no habia procesos `postgres`, `python`, `waitress` o `caddy`.

## Causa raiz

El servicio PostgreSQL estaba definido para que WinSW ejecutara:

```text
pg_ctl.exe runservice -N PicoDeGallo-PostgreSQL -D "C:\ProgramData\PicoDeGallo\postgres\data" -w
```

Ese modo no funciono bajo WinSW y produjo `error code 1063`. WinSW debe supervisar un proceso foreground, por lo que PostgreSQL debe arrancar directamente con `postgres.exe`.

## Correccion

La plantilla `PicoDeGallo-PostgreSQL.xml` ahora ejecuta:

```text
postgres.exe -D "C:\ProgramData\PicoDeGallo\postgres\data"
```

`install-services.ps1` renderiza `POSTGRES_DATA_DIR`, valida las herramientas PostgreSQL requeridas, instala primero el servicio PostgreSQL, lo inicia y espera el puerto `DB_PORT` antes de continuar con `migrate`, `collectstatic`, `bootstrap_initial_admin`, backend, DTE y Caddy.

Si PostgreSQL no arranca, el instalador falla y deja ultimas lineas de logs utiles en:

- `C:\ProgramData\PicoDeGallo\logs\install-services.log`
- `C:\ProgramData\PicoDeGallo\logs\service-install.log`
- `C:\ProgramData\PicoDeGallo\logs\healthcheck.log`
- `C:\ProgramData\PicoDeGallo\logs\PicoDeGallo-PostgreSQL.wrapper.log`
- `C:\ProgramData\PicoDeGallo\logs\PicoDeGallo-PostgreSQL.err.log`
- `C:\ProgramData\PicoDeGallo\logs\postgres-init.log`

## Acceso directo

El acceso directo normal del escritorio ya no abre PowerShell. El instalador crea:

```text
Pico de Gallo.url
```

apuntando a:

```text
http://127.0.0.1:9282
```

El modo kiosk/fullscreen queda separado en `open-kiosk.ps1`, que el instalador ejecuta oculto despues de que los servicios y healthchecks terminan correctamente. Para salir del kiosk: `Alt+F4`.

## Como probar 0.1.3-test

1. Desinstalar la version anterior.
2. En VM de prueba limpia, borrar `C:\ProgramData\PicoDeGallo` solo si se quiere reiniciar datos completamente.
3. Instalar `PicoDeGallo-Setup-0.1.3-test.exe`.
4. Verificar servicios:

```powershell
Get-Service *PicoDeGallo*
```

5. Verificar health:

```powershell
Invoke-WebRequest http://127.0.0.1:9282/api/health/live/
Invoke-WebRequest http://127.0.0.1:9282/api/health/ready/
```

6. Abrir:

```text
http://127.0.0.1:9282
```

7. Login de prueba:

```text
usuario: admin
clave: 000000
```

## Advertencias

`admin/000000` es solo para pruebas del instalador y debe cambiarse antes de produccion.

DTE sigue activo. El build CI no envia DTE reales, no contacta Hacienda, no imprime fisicamente y no abre cajon fisico.
