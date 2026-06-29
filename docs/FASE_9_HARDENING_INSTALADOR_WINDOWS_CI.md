# Fase 9 - Hardening del instalador Windows nativo en CI

## 1. Errores observados

- PowerShell parseaba con fallo previo en `diagnostics.ps1`.
- `package-release.ps1` intentaba copiar `.env.windows.example` antes de garantizar `ProgramData\PicoDeGallo\config`.
- `resolved-runtimes.json` podia quedar sin keys utiles, incluido `innoSetup`.
- Python embeddable fallaba con `python.exe: No module named pip`.
- PostgreSQL se copiaba desde la raiz completa del ZIP e incluia componentes no runtime como GUI y dependencias web.

## 2. Causa raiz

El flujo estaba validando tarde y copiando demasiado. `fetch-runtimes.ps1` resolvia PostgreSQL a la raiz extraida, `package-release.ps1` no tenia una validacion interna completa de payload y el workflow tenia validaciones parciales que descubrian errores despues de preparar un release incompleto.

## 3. Correcciones aplicadas

- `fetch-runtimes.ps1` valida manifest, URL HTTPS, versiones fijas, SHA256 y keys obligatorias.
- PostgreSQL ahora se prepara en `release/runtime-cache/prepared/postgres` copiando solo `bin/`, `lib/` y `share/`.
- `resolved-runtimes.json` apunta a rutas absolutas existentes para `python`, `postgres`, `caddy`, `winsw` e `innoSetup`.
- `package-release.ps1` crea todas las carpetas de `ProgramFiles` y `ProgramData` antes de copiar archivos.
- Python embeddable recibe dependencias con el Python de build mediante `pip install --target`.
- La validacion `Test-ReleasePayloadSafety` corre dentro de `package-release.ps1`.
- El workflow instala Inno Setup solo desde el runtime verificado y valida `ISCC.exe`.
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

Pendiente de ejecutar en GitHub Actions para esta revision.

## 12. Estado del instalador

Pendiente de confirmar si se genero `PicoDeGallo-Setup-0.1.0-test.exe`, su `.sha256` y `manifest.json`.

## 13. Artifact o release

Pendiente de registrar el `RUN_ID`, artifact o release generado.

## 14. Proximo paso

Ejecutar el workflow manual con `version=0.1.0-test`, `prerelease=true` y `skip_signing=true`. Si pasa, descargar el `.exe` desde GitHub Releases y probarlo en una VM Windows limpia.
