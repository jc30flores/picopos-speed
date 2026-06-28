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

## Build del instalador

1. Preparar runtimes externos fuera de Git.
2. Ejecutar `package-release.ps1` para producir `release/windows-native`.
3. Ejecutar `installer/build-installer.ps1` para compilar con Inno Setup.
4. Probar el instalador en Windows limpio.
5. No subir binarios generados, releases ni instaladores a Git.


## Release automatizado por GitHub Actions

El flujo recomendado para distribución comercial ya no es que el cliente ni el operador construyan localmente. Al crear un tag `v*` o ejecutar manualmente el workflow `Build native Windows installer`, GitHub Actions prepara runtimes Windows verificados por SHA256, genera el release nativo, compila `PicoDeGallo-Setup-${VERSION}.exe` y lo publica como asset de GitHub Releases.

El build local con `package-release.ps1` y `installer/build-installer.ps1` queda como ruta técnica opcional para validación. El cliente final descarga únicamente el `.exe` publicado; no clona el repositorio y no instala Docker Desktop, WSL2, Python, Node.js, PostgreSQL, Caddy ni Inno Setup.

Para habilitar CI se debe configurar `deploy/windows-native/vendor/runtime-manifest.json` fuera de placeholders, con URLs HTTPS versionadas y SHA256 reales. No subas runtimes, releases ni instaladores generados a Git.
