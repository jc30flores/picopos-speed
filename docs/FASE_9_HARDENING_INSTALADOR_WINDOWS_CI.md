# Fase 9 - Hardening del instalador Windows nativo en CI

## 1. Errores observados

- PowerShell parseaba con fallo previo en `diagnostics.ps1`.
- `package-release.ps1` intentaba copiar `.env.windows.example` antes de garantizar `ProgramData\PicoDeGallo\config`.
- `resolved-runtimes.json` podia quedar sin keys utiles, incluido `innoSetup`.
- Python embeddable fallaba con `python.exe: No module named pip`.
- PostgreSQL se copiaba desde la raiz completa del ZIP e incluia componentes no runtime como GUI y dependencias web.
- En GitHub Actions se detectaron fallos adicionales durante el endurecimiento: uso de `$host` en PowerShell, validacion de `OrderedDictionary` con metodo incorrecto, falso positivo de token `Bearer` por regex multilinea, splatting de parametros con arreglo al llamar `build-installer.ps1`, comillas `\"` invalidas en Inno Setup y cache de pip inexistente en el post-step de `actions/setup-python`.

## 2. Causa raiz

El flujo estaba validando tarde y copiando demasiado. `fetch-runtimes.ps1` resolvia PostgreSQL a la raiz extraida, `package-release.ps1` no tenia una validacion interna completa de payload y el workflow tenia validaciones parciales que descubrian errores despues de preparar un release incompleto. Ademas, algunos errores eran propios de PowerShell/Inno en Windows y no se podian reproducir completamente desde Linux sin ejecutar el workflow.

## 3. Correcciones aplicadas

- `fetch-runtimes.ps1` valida manifest, URL HTTPS, versiones fijas, SHA256 y keys obligatorias.
- PostgreSQL ahora se prepara en `release/runtime-cache/prepared/postgres` copiando solo `bin/`, `lib/` y `share/`.
- `resolved-runtimes.json` apunta a rutas absolutas existentes para `python`, `postgres`, `caddy`, `winsw` e `innoSetup`.
- `package-release.ps1` crea todas las carpetas de `ProgramFiles` y `ProgramData` antes de copiar archivos.
- Python embeddable recibe dependencias con el Python de build mediante `pip install --target`.
- La validacion `Test-ReleasePayloadSafety` corre dentro de `package-release.ps1`.
- El workflow instala Inno Setup solo desde el runtime verificado y valida `ISCC.exe`.
- La llamada a `build-installer.ps1` usa splatting con hashtable para parametros nombrados.
- `PicoDeGallo.iss` usa comillas duplicadas de Inno Setup en `Parameters`, no escapes `\"`.
- Se elimino el cache de pip de `actions/setup-python`, porque el empaquetado usa `pip --no-cache-dir`.
- `build-installer.ps1` genera `.exe`, `.sha256` y `manifest.json`.
- Se agrego `scripts/ci/validate_windows_native_packaging.py` para validaciones estaticas desde Linux.

## 4. Prevencion de regresiones

El workflow falla temprano por categoria (`RUNTIME_MANIFEST`, `HASH_MISMATCH`, `RUNTIME_RESOLVE`, `POWERSHELL_PARSE`, `POSTGRES_RUNTIME_BLOAT`, `RELEASE_PAYLOAD_SAFETY`, `INNO_INSTALL`, `INNO_BUILD`). El payload se valida dos veces: al cerrar `package-release.ps1` y antes de compilar con Inno Setup.

## 5. Estado de runtimes

Los runtimes no se versionan en Git. El manifest real debe venir de `deploy/windows-native/vendor/runtime-manifest.json` o de `WINDOWS_RUNTIME_MANIFEST_JSON`. El ejemplo sigue siendo solo contrato y debe contener placeholders.

## 6. Estado del Python embeddable

El runtime embeddable no usa pip propio. CI usa `actions/setup-python@v5` con Python 3.12, instala dependencias a `Lib\site-packages`, habilita `import site` en `python*._pth`, desactiva cache/bytecode y verifica `django`, `waitress`, `psycopg2` y `requests`.

## 7. Estado del PostgreSQL runtime minimo

El ZIP fuente se extrae en cache, luego se prepara una carpeta limpia con allowlist `bin/`, `lib/` y `share/`. Deben existir `postgres.exe`, `pg_ctl.exe`, `initdb.exe`, `psql.exe`, `pg_dump.exe`, `pg_restore.exe` y `createdb.exe`. El flujo falla si aparecen componentes GUI, dependencias web o artefactos de gestores JS.

## 8. Estado de Inno Setup

`innoSetup` es obligatorio en `resolved-runtimes.json`, debe apuntar a un `.exe` dentro de `release/runtime-cache`, se instala en modo silencioso y se valida `ISCC.exe` en rutas comunes de Inno Setup 6.

## 9. Estado de payload safety

El release rechaza `.env` reales, secretos obvios, media real, dumps, backups, diagnostics, caches, bytecode Python, carpetas VCS, dependencias frontend sin compilar, componentes GUI de PostgreSQL y archivos SQL/dump no requeridos.

## 10. Estado de DTE

DTE sigue activo con `DTE_BACKGROUND_MODE=external`. El workflow solo compila y empaqueta. No envia DTE reales, no contacta Hacienda, no usa tokens reales, no cambia payload fiscal, no cambia contadores y no apaga `dte-worker` ni `dte-monitor`.

## 11. Resultado del workflow final

Workflow ejecutado en GitHub Actions con:

- Rama: `codex/implementar-cambios-para-configuraciones-runtime-xyowqd`
- Version: `0.1.0-test`
- `prerelease=true`
- `skip_signing=true`
- `RUN_ID`: `28341637334`
- Resultado: `success`
- URL: `https://github.com/jc30flores/picopos-speed/actions/runs/28341637334`

Pasaron todos los pasos: manifest, descarga y SHA256 de runtimes, `resolved-runtimes.json`, parseo PowerShell, XML, lint de Inno Setup, `npm ci`, `package-release.ps1`, payload safety, instalacion de Inno Setup, build del instalador, validacion de salida, artifact y GitHub Release.

## 12. Estado del instalador

Se genero el instalador de prueba:

- `PicoDeGallo-Setup-0.1.0-test.exe`
- `PicoDeGallo-Setup-0.1.0-test.exe.sha256`
- `manifest.json`

El asset `.exe` publicado pesa aproximadamente 66.5 MB. El instalador no esta firmado porque la ejecucion uso `skip_signing=true`.

## 13. Artifact o release

Artifact del workflow:

- Nombre: `PicoDeGallo-Installer-0.1.0-test`
- `RUN_ID`: `28341637334`
- Estado: no expirado al momento de la revision

GitHub Release:

- Tag: `0.1.0-test`
- Prerelease: si
- URL: `https://github.com/jc30flores/picopos-speed/releases/tag/0.1.0-test`
- Assets publicados: `PicoDeGallo-Setup-0.1.0-test.exe`, `PicoDeGallo-Setup-0.1.0-test.exe.sha256`, `manifest.json`

## 14. Proximo paso

Descargar unicamente `PicoDeGallo-Setup-0.1.0-test.exe` desde GitHub Releases y probarlo en una VM Windows limpia sin Python, Node.js, PostgreSQL, Caddy, Inno Setup, Docker Desktop ni WSL2 preinstalados. Validar instalacion, servicios, migraciones, frontend, DTE configurado con placeholders seguros y arranque sin envio fiscal real.
