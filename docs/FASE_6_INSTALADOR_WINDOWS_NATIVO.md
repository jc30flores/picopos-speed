# Fase 6 — Instalador nativo Windows con Inno Setup

## 1. Objetivo
Crear infraestructura real para compilar `PicoDeGallo-Setup-x.y.z.exe` desde un release nativo generado previamente.

## 2. Qué hace el instalador
Instala archivos en `C:\Program Files\PicoDeGallo`, crea estructura de datos en `C:\ProgramData\PicoDeGallo`, instala servicios Windows, genera configuración local y arranca servicios.

## 3. Qué no hace todavía
No descarga binarios, no publica releases, no fuerza firma si no hay certificado, no implementa auto-update ni impresión Windows real.

## 4. Por qué no requiere Docker Desktop
El paquete incluye runtimes externos preparados por la máquina de build: Python, PostgreSQL, Caddy y WinSW. Docker queda sólo como herramienta técnica opcional.

## 5. Program Files
Contiene `backend`, `frontend`, `caddy`, `python`, `postgres`, `services`, `scripts`, `version.json` y `THIRD_PARTY_NOTICES.md` si existe.

## 6. ProgramData
Contiene `config\.env`, `postgres\data`, `media`, `static`, `dte_logs`, `logs`, `backups` y `diagnostics`.

## 7. Servicios instalados
`PicoDeGallo-PostgreSQL`, `PicoDeGallo-Backend`, `PicoDeGallo-DTE-Worker`, `PicoDeGallo-DTE-Monitor`, `PicoDeGallo-Caddy`.

## 8. PostgreSQL nativo
El instalador conserva data dir en ProgramData. `install-services.ps1` prepara carpetas e inicializa PostgreSQL si el runtime y data dir lo permiten.

## 9. Backend con Waitress
Windows nativo usa Waitress; Docker/Linux puede seguir con Gunicorn. No se usa `runserver` como servicio productivo.

## 10. Caddy nativo
Caddy se genera desde `Caddyfile.template`, escucha en `APP_BIND_ADDRESS:APP_HTTP_PORT`, sirve frontend/static/media y proxy a backend local.

## 11. DTE worker/monitor nativos
DTE sigue activo. `dte_outbox_worker` y `dte_monitor` se ejecutan como servicios Windows separados con `DTE_BACKGROUND_MODE=external`.

## 12. Configuración DTE
La configuración real vive en `C:\ProgramData\PicoDeGallo\config\.env`; placeholders DTE no son operativos para producción.

## 13. Build del release
Ejecutar `deploy/windows-native/package-release.ps1` con rutas a runtimes externos. El script no descarga binarios ni copia secretos.

## 14. Build del instalador
Ejecutar `deploy/windows-native/installer/build-installer.ps1 -Version x.y.z -ReleaseDir release/windows-native -OutputDir release/installers -InnoSetupCompilerPath ...`.

## 15. Desinstalación segura
El uninstaller detiene/desinstala servicios y borra Program Files, pero conserva ProgramData por defecto. La purga queda en `uninstall-services.ps1 -PurgeData`.

## 16. Actualización existente
En actualización, el instalador intenta detener servicios y crear backup previo antes de actualizar Program Files, conservando ProgramData, `.env`, PostgreSQL data, media, backups y logs DTE.

## 17. Backups
Los backups nativos usan `pg_dump`, media, dte_logs y manifest.json sin secretos.

## 18. Diagnostics
Diagnostics genera ZIP sanitizado con servicios, logs, health y configuración no sensible.

## 19. Licencias/terceros
`THIRD_PARTY_NOTICES.template.md` lista componentes esperados y deja placeholders para revisión legal antes de distribución comercial.

## 20. Pruebas requeridas en Windows limpio
Compilar release, compilar instalador, instalar en VM limpia, verificar servicios, health endpoints, login/admin, backup, diagnostics y uninstall conservando datos.

## 21. Limitaciones
No se generan binarios en este entorno, no se ejecutó Inno Setup, no se firmó código y no se probó en Windows limpio.

## 22. Riesgos pendientes
Validar permisos de `.env`, dependencia final de WinSW, inicialización real de PostgreSQL portable, estrategia de backup previo en upgrade y firma de código.

## 23. Próxima fase recomendada
Ejecutar la cadena completa en Windows con runtimes reales, ajustar wizard de configuración DTE y preparar firma/publicación controlada.

## Estado explícito
DTE sigue activo. No se enviaron DTE reales durante pruebas automatizadas. No se contactó Hacienda durante pruebas automatizadas. No se agregaron binarios pesados ni secretos.
