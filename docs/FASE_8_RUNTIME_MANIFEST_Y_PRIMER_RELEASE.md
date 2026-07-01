# Fase 8 — Runtime manifest y primer release del instalador

## 1. Objetivo

Preparar el primer build verificable de `PicoDeGallo-Setup-x.y.z.exe` en GitHub Actions. El cliente final descarga únicamente el instalador desde GitHub Releases; no clona el repositorio y no instala Docker, Python, PostgreSQL, Node.js, Caddy ni Inno Setup.

## 2. Qué faltaba después de Fase 7

Fase 7 dejó el workflow, `fetch-runtimes.ps1` y `runtime-manifest.example.json`. Faltan las URLs versionadas definitivas y SHA256 verificados de Python, PostgreSQL, Caddy, WinSW e Inno Setup. Sin esos hashes no se debe declarar listo un release comercial.

## 3. Decisión de manifest

No se versiona todavía `deploy/windows-native/vendor/runtime-manifest.json` definitivo porque en esta fase no se verificaron todos los SHA256 desde fuentes confiables. Se mantiene la opción segura por variable o secret `WINDOWS_RUNTIME_MANIFEST_JSON` y se conserva `runtime-manifest.example.json` solo como contrato de estructura.

## 4. Opción archivo versionado

Se puede versionar `deploy/windows-native/vendor/runtime-manifest.json` únicamente cuando todas las URLs sean públicas, HTTPS, de versión fija, sin tokens, sin `latest`, sin redirecciones temporales y con SHA256 real verificado. No se deben inventar hashes ni usar placeholders.

## 5. Opción variable o secret GitHub

Si alguna URL es privada, temporal o administrada por infraestructura interna, configure `WINDOWS_RUNTIME_MANIFEST_JSON` como variable o secret del repositorio. El workflow acepta ambos orígenes y falla si no existe manifest real o si contiene placeholders.

## 6. Cómo obtener URLs versionadas

Para cada runtime registre:

- `name`: python, postgres, caddy, winsw o innoSetup.
- `version`: versión exacta.
- `url`: HTTPS y de versión fija.
- `sha256`: hash real de 64 caracteres hexadecimales.
- `archiveType`: `zip`, `file` o `installer`.
- `extractTo` y `expectedExecutable` si aplica.
- `licenseNote`: nota para revisión de licencias/notices.

## 7. Cómo verificar SHA256

Descargue el artefacto desde la fuente oficial o controlada, calcule SHA256 en una máquina confiable y compare con el valor publicado por el proveedor cuando exista. En PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\runtime.zip
```

Si el proveedor no publica hash o no puede verificarse el origen, clasifique como `BLOCKED/HASH_NOT_VERIFIED` y no use ese runtime para un release estable.

## 8. Ejecutar fetch-runtimes.ps1 localmente

Cuando exista un manifest real:

```powershell
pwsh -NoProfile -File deploy/windows-native/vendor/fetch-runtimes.ps1 `
  -ManifestPath deploy/windows-native/vendor/runtime-manifest.json `
  -OutputDir .runtime-cache-test
```

El script debe rechazar placeholders, `latest`, URL no HTTPS, hash faltante y hash incorrecto. Tambien debe generar `resolved-runtimes.json` con rutas absolutas para `python`, `postgres`, `caddy`, `winsw` e `innoSetup`. `.runtime-cache-test` no debe agregarse a Git.

## 9. Ejecutar workflow_dispatch

1. Abrir GitHub.
2. Ir a Actions.
3. Seleccionar `Build native Windows installer`.
4. Ejecutar `Run workflow`.
5. Inputs recomendados para primera prueba:
   - `version`: `0.1.0-test`
   - `prerelease`: `true`
   - `skip_signing`: `true`
6. Revisar artifacts.
7. Confirmar:
   - `PicoDeGallo-Setup-0.1.0-test.exe`
   - `PicoDeGallo-Setup-0.1.0-test.exe.sha256`
   - `manifest.json`

El runtime PostgreSQL del release debe ser el directorio preparado por allowlist (`bin/`, `lib/`, `share/`), no la raiz completa del ZIP fuente.

## 10. Publicar por tag

Para primer prerelease por tag:

```bash
git tag v0.1.0-test
git push origin v0.1.0-test
```

Resultado esperado en GitHub Releases:

- Release `v0.1.0-test`.
- `PicoDeGallo-Setup-v0.1.0-test.exe`.
- `PicoDeGallo-Setup-v0.1.0-test.exe.sha256`.
- `manifest.json`.

No entregar este prerelease a clientes hasta validarlo en una VM Windows limpia.

## 11. Descargar artifact

El artifact de Actions sirve para inspección interna del build y tiene retención limitada. Úselo para diagnosticar antes de publicar o validar un prerelease.

## 12. Descargar desde GitHub Releases

El cliente final debe descargar el instalador desde la página del Release estable de GitHub, no desde artifacts de Actions y no desde el repositorio fuente.

## 13. Test release vs release estable

`0.1.0-test` o `v0.1.0-test` debe tratarse como prerelease técnico. Un release estable requiere runtimes verificados, licencias revisadas, instalación en VM Windows limpia, backup/restore probado, desinstalación segura y DTE configurado con credenciales reales solo en entorno seguro.

## 14. Firma y SmartScreen

Si no hay certificado, use `skip_signing=true`. Un instalador sin firma puede mostrar advertencia de Windows SmartScreen. Para distribución comercial se recomienda certificado de firma de código y configurar:

- `WINDOWS_CODESIGN_CERT_BASE64`
- `WINDOWS_CODESIGN_CERT_PASSWORD`
- `WINDOWS_CODESIGN_TIMESTAMP_URL`

Nunca agregue certificados al repositorio.

## 15. Checklist antes de cliente

1. Manifest real sin placeholders.
2. SHA256 verificado para todos los runtimes.
3. Licencias y notices revisados.
4. Workflow verde en `windows-latest`.
5. Instalador probado en VM Windows limpia.
6. Backup, diagnostics, upgrade y uninstall probados.
7. DTE activo con credenciales reales solo en instalación autorizada.
8. No hay secretos ni binarios en Git.

## 16. Estado DTE

DTE sigue activo. El workflow solo descarga runtimes, compila frontend, empaqueta backend y compila el instalador. No envía DTE, no contacta Hacienda, no prueba invalidaciones, no prueba notas de crédito, no usa `DTE_API_TOKEN` real y no apaga `dte-worker` ni `dte-monitor`.

## 17. Riesgos pendientes

- `BLOCKED/HASH_NOT_VERIFIED`: falta completar SHA256 reales de todos los runtimes.
- Falta validar la distribución comercial de cada runtime.
- Falta certificado de firma para reducir SmartScreen.
- Falta primer build en GitHub Actions con manifest real.
- Falta validar en Actions que Python embeddable importe `django`, `waitress`, `psycopg2` y `requests`.
- Falta prueba completa en VM Windows limpia.

## 18. Próxima fase

Configurar `WINDOWS_RUNTIME_MANIFEST_JSON` o versionar un manifest real verificado, ejecutar `workflow_dispatch` con `0.1.0-test`, analizar resultados, corregir fallos por categoría y promover únicamente después de una instalación completa en VM Windows limpia.
