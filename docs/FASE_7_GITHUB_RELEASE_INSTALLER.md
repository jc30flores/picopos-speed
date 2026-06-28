# Fase 7 — GitHub Release del instalador Windows nativo

## 1. Objetivo

La distribución comercial debe terminar en un único asset descargable desde GitHub Releases: `PicoDeGallo-Setup-x.y.z.exe`. El cliente final no clona el repositorio, no instala Docker Desktop, no instala WSL2, no instala Python, no instala Node.js, no instala PostgreSQL, no instala Caddy y no instala Inno Setup.

## 2. Flujo recomendado

GitHub Actions ejecuta `.github/workflows/windows-native-installer.yml` en `windows-latest`. El workflow descarga runtimes Windows fuera de Git, verifica SHA256, ejecuta `deploy/windows-native/package-release.ps1`, compila el instalador con `deploy/windows-native/installer/build-installer.ps1`, sube artifacts internos y publica assets en GitHub Releases.

## 3. Disparo por tag

Crear y publicar un tag `v1.0.0` dispara el workflow automáticamente. El release resultante debe incluir:

- `PicoDeGallo-Setup-v1.0.0.exe`
- `PicoDeGallo-Setup-v1.0.0.exe.sha256`
- `manifest.json`

## 4. Disparo manual

`workflow_dispatch` permite ejecutar el build con inputs:

- `version`: versión a publicar, por ejemplo `v1.0.0`.
- `prerelease`: marca el GitHub Release como prerelease.
- `skip_signing`: permite omitir firma si no hay certificado configurado.

## 5. Artifact vs GitHub Release

El artifact de Actions es evidencia interna del build y se retiene temporalmente. GitHub Release es el punto de descarga para clientes: ahí se publica el `.exe`, su `.sha256` y el manifest público.

## 6. Runtimes y hashes

Los binarios de Python, PostgreSQL, Caddy, WinSW e Inno Setup no se versionan en Git. El workflow usa `deploy/windows-native/vendor/runtime-manifest.json`, generado desde `runtime-manifest.example.json` o desde variables/secrets del repositorio. Cada runtime debe tener URL HTTPS versionada y SHA256 real. No se permite `latest`, URL acortada ni descarga sin hash.

## 7. Firma de código

La firma es opcional en CI. Si existen secrets:

- `WINDOWS_CODESIGN_CERT_BASE64`
- `WINDOWS_CODESIGN_CERT_PASSWORD`
- `WINDOWS_CODESIGN_TIMESTAMP_URL`

el workflow puede firmar el instalador. Si `skip_signing=true` o faltan secrets, el instalador se genera sin firma y Windows SmartScreen puede mostrar advertencias.

## 8. Validaciones de seguridad

El workflow valida PowerShell, XML de servicios, payload de release, archivos prohibidos, existencia del `.exe`, SHA256 y manifest. No debe subir `.env` real, secretos, media, dumps, backups, diagnostics ni runtimes por separado.

## 9. Offline vs online installer

La primera versión comercial recomendada es el instalador offline completo: un archivo grande que incluye Python, PostgreSQL, Caddy, WinSW y la aplicación. Un instalador online pequeño queda pendiente porque requiere infraestructura adicional para descargar durante instalación con hashes y manejo robusto de fallos.

## 10. Estado DTE

DTE sigue activo. El workflow solo compila y empaqueta; no envía DTE reales, no contacta Hacienda, no cambia payload fiscal, no cambia contadores y no apaga `dte-worker` ni `dte-monitor`.

## 11. Checklist antes de entregar a cliente

1. Configurar `runtime-manifest.json` con URLs HTTPS y SHA256 reales.
2. Revisar licencias y `THIRD_PARTY_NOTICES.md`.
3. Ejecutar workflow en tag o manual.
4. Descargar el artifact y validar SHA256.
5. Instalar en VM Windows limpia.
6. Confirmar servicios PostgreSQL, Backend, DTE Worker, DTE Monitor y Caddy.
7. Confirmar `http://127.0.0.1:9282` y healthchecks.
8. Probar backup, diagnostics, upgrade y uninstall conservando datos.
9. Configurar credenciales DTE reales solo en entorno seguro.

## 12. Rollback

Si un release falla, marcarlo como prerelease o retirarlo de GitHub Releases, conservar el tag anterior estable, y pedir a clientes que no actualicen hasta validar un nuevo instalador. Los datos de cliente permanecen en `C:\ProgramData\PicoDeGallo` y no deben borrarse por defecto.

## 13. Riesgos pendientes

- Completar manifest real de runtimes con hashes verificados.
- Validar licencia/distribución comercial de cada runtime.
- Configurar firma de código para reducir advertencias SmartScreen.
- Ejecutar prueba obligatoria en VM Windows limpia antes de entrega a clientes.
- Implementar instalador online solo cuando exista infraestructura segura de descarga.
