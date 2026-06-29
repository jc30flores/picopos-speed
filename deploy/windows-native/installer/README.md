# Build del instalador nativo Windows

Esta carpeta contiene infraestructura para generar `PicoDeGallo-Setup-x.y.z.exe` con Inno Setup. No contiene binarios de Python, PostgreSQL, Caddy, WinSW ni instaladores externos.

## Flujo esperado

1. Preparar runtimes externos fuera de Git:
   - Python embeddable/runtime para Windows.
   - PostgreSQL portable/runtime para Windows.
   - Caddy para Windows.
   - WinSW o wrapper equivalente.
2. Ejecutar `deploy/windows-native/package-release.ps1` con rutas reales a esos runtimes. PostgreSQL debe apuntar al runtime minimo preparado, no a la raiz completa de un instalador que incluya herramientas GUI.
3. Ejecutar `deploy/windows-native/installer/build-installer.ps1` apuntando al release generado.
4. Probar el instalador en una VM Windows limpia.
5. No subir a Git el instalador, los runtimes ni el release generado.

## Ejemplo

```powershell
deploy/windows-native/package-release.ps1 `
  -Version "1.2.3" `
  -OutputDir "release/windows-native" `
  -PythonRuntimePath "C:\runtimes\python" `
  -PostgresRuntimePath "C:\runtimes\postgres" `
  -CaddyPath "C:\runtimes\caddy.exe" `
  -WinSWPath "C:\runtimes\winsw.exe"

deploy/windows-native/installer/build-installer.ps1 `
  -Version "1.2.3" `
  -ReleaseDir "release/windows-native" `
  -OutputDir "release/installers" `
  -InnoSetupCompilerPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
  -SkipSigning
```

El resultado esperado es `release/installers/PicoDeGallo-Setup-1.2.3.exe`, `release/installers/PicoDeGallo-Setup-1.2.3.exe.sha256` y `release/installers/manifest.json`.


## Flujo recomendado en CI

El build local es opcional. Para distribucion comercial, usa `.github/workflows/windows-native-installer.yml` en GitHub Actions. El workflow corre en `windows-latest`, descarga runtimes desde `deploy/windows-native/vendor/runtime-manifest.json` o `WINDOWS_RUNTIME_MANIFEST_JSON`, verifica SHA256, prepara PostgreSQL minimo, ejecuta `package-release.ps1`, ejecuta `build-installer.ps1`, sube artifacts internos y publica en GitHub Releases.

Para publicar una versión estable, crea un tag como `v1.0.0`. Para una prueba controlada, usa `workflow_dispatch` con `prerelease=true`. Si no hay certificado de firma configurado, usa `skip_signing=true`; el instalador será funcional pero Windows SmartScreen puede advertir que no está firmado.

Assets esperados del release:

- `PicoDeGallo-Setup-${VERSION}.exe`
- `PicoDeGallo-Setup-${VERSION}.exe.sha256`
- `manifest.json`

El instalador ejecuta `install-services.ps1` como paso obligatorio. Si falla la instalacion de servicios, migraciones, `collectstatic`, bootstrap admin o health checks, Inno Setup devuelve error. Si todo queda listo, ejecuta `open-kiosk.ps1` para abrir Pico de Gallo.

En `0.1.2-test`, el bootstrap inicial crea `admin` / `000000` solo para pruebas de instalador. Debe cambiarse antes de produccion.

No subas a Git los instaladores generados, runtimes, certificados, `.env` reales ni releases finales.

## Primer release con runtime manifest real

Antes de ejecutar el workflow, configure uno de estos orígenes:

- `deploy/windows-native/vendor/runtime-manifest.json` versionado con URLs públicas HTTPS y SHA256 reales verificados.
- `WINDOWS_RUNTIME_MANIFEST_JSON` como variable o secret de GitHub si alguna URL no debe quedar en Git.

No use `runtime-manifest.example.json` como manifest real. El workflow lo rechazara por placeholders. Para la prueba manual use `workflow_dispatch` con `version=0.1.2-test`, `prerelease=true` y `skip_signing=true`. Si el build falla, clasifique el error como `CHECKOUT_INVALID_PATH`, `RUNTIME_MANIFEST`, `RUNTIME_DOWNLOAD`, `HASH_MISMATCH`, `RUNTIME_RESOLVE`, `POWERSHELL_PARSE`, `XML_TEMPLATE`, `FRONTEND_BUILD`, `PYTHON_EMBEDDED_DEPS`, `POSTGRES_RUNTIME_BLOAT`, `RELEASE_PAYLOAD_SAFETY`, `INNO_INSTALL`, `INNO_BUILD`, `SIGNING`, `ARTIFACT_UPLOAD` o `RELEASE_UPLOAD` antes de corregir.
