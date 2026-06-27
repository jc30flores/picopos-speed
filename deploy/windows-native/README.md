# Pico de Gallo — base de paquete nativo Windows

Esta carpeta prepara la ruta comercial para un único instalador futuro `PicoDeGallo-Setup.exe`. El cliente final no deberá instalar Docker Desktop, WSL2, Python, Node.js, PostgreSQL ni Caddy manualmente.

Docker se conserva como herramienta técnica opcional para desarrollo, pruebas y despliegues controlados; no es el requisito objetivo para clientes normales.

## Estructura

- `layout/ProgramFiles/PicoDeGallo/`: archivos de programa que empaquetará el release.
- `layout/ProgramData/PicoDeGallo/`: datos persistentes, configuración, media, static, logs DTE, backups y diagnósticos.
- `scripts/`: operación nativa sin Docker.
- `service-templates/`: plantillas WinSW para servicios Windows.
- `caddy/Caddyfile.template`: Caddy nativo sin HTTPS automático.
- `installer/`: placeholders para Inno Setup futuro.
- `vendor/`: documentación de binarios externos no versionados.

## Servicios Windows previstos

- `PicoDeGallo-PostgreSQL`
- `PicoDeGallo-Backend`
- `PicoDeGallo-DTE-Worker`
- `PicoDeGallo-DTE-Monitor`
- `PicoDeGallo-Caddy`

## Backend Windows

Gunicorn se mantiene para Docker/Linux. Para Windows nativo se prepara Waitress como servidor WSGI compatible:

```powershell
python -m waitress.runner --listen=127.0.0.1:8000 config.wsgi:application
```

## DTE activo

DTE sigue activo. `DTE_BACKGROUND_MODE=external` separa backend web, worker y monitor. El instalador final deberá escribir `DTE_BASE_URL` y `DTE_API_TOKEN` reales en `C:\ProgramData\PicoDeGallo\config\.env`.

## Release local

`package-release.ps1` prepara una carpeta de release y marca el resultado como `NOT_INSTALLABLE` si faltan binarios externos.

Ejemplo:

```powershell
deploy/windows-native/package-release.ps1 -Version "1.0.0" -OutputDir "release/windows-native" -SkipFrontendBuild -SkipDependencyInstall
```

No descarga dependencias ni agrega binarios al repo.
