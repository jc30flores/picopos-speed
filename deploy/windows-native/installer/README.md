# Build del instalador nativo Windows

Esta carpeta contiene infraestructura para generar `PicoDeGallo-Setup-x.y.z.exe` con Inno Setup. No contiene binarios de Python, PostgreSQL, Caddy, WinSW ni instaladores externos.

## Flujo esperado

1. Preparar runtimes externos fuera de Git:
   - Python embeddable/runtime para Windows.
   - PostgreSQL portable/runtime para Windows.
   - Caddy para Windows.
   - WinSW o wrapper equivalente.
2. Ejecutar `deploy/windows-native/package-release.ps1` con rutas reales a esos runtimes.
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

El resultado esperado es `release/installers/PicoDeGallo-Setup-1.2.3.exe` más checksum SHA256 y manifiesto de build.
