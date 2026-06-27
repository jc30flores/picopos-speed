# Pico de Gallo en Windows con Docker Desktop

Esta fase agrega operación local mediante scripts PowerShell. Todavía no es un instalador `.exe`; se trabaja desde la raíz del repositorio y se prepara la transición futura a `C:\Program Files\PicoDeGallo` y `C:\ProgramData\PicoDeGallo`.
> Nota comercial: este flujo Docker queda como ruta técnica/opcional para desarrollo, pruebas y despliegues controlados. Para clientes normales se está preparando un paquete nativo Windows que no requiere instalación manual de Docker Desktop.


## Requisitos

- Windows 64 bits.
- PowerShell 5+ o PowerShell 7+.
- Docker Desktop instalado, iniciado y con Docker Compose disponible.
- Puerto local libre, por defecto `9282`.

## DTE activo

El sistema corre con DTE activo. Para enviar DTE se requieren valores reales en `.env.docker`:

- `DTE_BASE_URL`
- `DTE_API_TOKEN`
- `DTE_BACKGROUND_MODE=external`

No subas tokens ni `.env.docker` a Git. `dte-worker` y `dte-monitor` corren como servicios separados. Si existen DTE pendientes, el worker puede procesarlos al iniciar con credenciales reales.

## Crear configuración

```powershell
deploy/windows/scripts/init-env.ps1
```

Con valores DTE reales:

```powershell
deploy/windows/scripts/init-env.ps1 -DteBaseUrl "https://proveedor.example" -DteApiToken "TOKEN_REAL"
```

Para pruebas técnicas sin valores reales:

```powershell
deploy/windows/scripts/init-env.ps1 -UsePlaceholders
```

## Instalar o levantar con build local

```powershell
deploy/windows/scripts/install.ps1 -UseLocalBuild
```

Para pruebas técnicas con placeholders DTE:

```powershell
deploy/windows/scripts/install.ps1 -UseLocalBuild -AllowDtePlaceholdersForLocalBuild
```

Esta ejecución no es válida para producción DTE.

## Abrir

```text
http://127.0.0.1:9282
```

## Operación diaria

```powershell
deploy/windows/scripts/start.ps1
deploy/windows/scripts/stop.ps1
deploy/windows/scripts/restart.ps1
deploy/windows/scripts/status.ps1
deploy/windows/scripts/logs.ps1 -Service backend -Tail 200
deploy/windows/scripts/logs.ps1 -Service dte-worker -Tail 200
deploy/windows/scripts/logs.ps1 -Service dte-monitor -Tail 200
```

## Backup, restore y diagnóstico

```powershell
deploy/windows/scripts/backup.ps1
deploy/windows/scripts/restore.ps1 -BackupPath "deploy/windows/backups/PicoDeGallo-Backup-YYYY-MM-DD-HHMMSS"
deploy/windows/scripts/diagnostics.ps1
```

Los diagnósticos se sanitizan y no deben incluir tokens, passwords ni `.env.docker` completo.

## Desinstalar sin borrar datos

```powershell
deploy/windows/scripts/uninstall.ps1
```

No usa `docker compose down -v` por defecto y conserva volúmenes, backups, diagnósticos y `.env.docker`. Para purgar datos se requiere:

```powershell
deploy/windows/scripts/uninstall.ps1 -PurgeData
```

El script exige escribir `BORRAR DATOS PICO DE GALLO`.

## Acceso LAN explícito

Por defecto sólo escucha en localhost. Para abrir en LAN, editar `.env.docker`:

```env
APP_BIND_ADDRESS=0.0.0.0
```

No abre firewall automáticamente.

## Advertencias

- No usar `docker compose down -v` en operación normal.
- No se implementa agente de impresión Windows todavía.
- No se modifica DTE legal, payload fiscal, contadores ni Hacienda.
- Esta fase sólo agrega operación Windows mediante scripts.
- Pendientes: instalador `.exe`, auto-update, publicación de imágenes, agente de impresión Windows y pruebas DTE reales controladas.
