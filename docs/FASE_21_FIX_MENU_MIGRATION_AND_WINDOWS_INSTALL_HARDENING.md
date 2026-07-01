# Fase 21: migracion menu e instalador Windows 0.1.12-test

## Resultado real de 0.1.11-test

El instalador 0.1.11-test llego mas lejos que las versiones anteriores: escribio `version.json`, creo `C:\ProgramData\PicoDeGallo\config\.env`, mantuvo DTE en modo externo, inicializo PostgreSQL local y dejo el servicio `PicoDeGallo-PostgreSQL` corriendo como `PicoDeGalloSvc`. Tambien pasaron `setup-database`, `validate-backend-runtime` y `check-runtime-config`.

El flujo se detuvo antes de instalar backend, worker DTE, monitor DTE y Caddy. Los puertos 8000 y 9282 quedaron cerrados; PostgreSQL quedo sano en 5432.

## Fallo nuevo

El error real fue:

```text
psycopg2.errors.UndefinedTable: relation "menu_discount_active__c4f9aa_idx" does not exist
```

La migracion afectada fue `menu.0002_rename_menu_discount_active__c4f9aa_idx_menu_discou_active_b4fadc_idx_and_more`.

## Causa raiz

`menu` tenia dos migraciones `0002` paralelas:

- `0002_discount_rules` elimina el campo legacy `active` de `Discount`. PostgreSQL elimina tambien el indice asociado.
- `0002_rename_menu_discount...` intentaba renombrar ese indice legacy por nombre exacto.

Si Django aplicaba primero `0002_discount_rules`, el indice ya no existia cuando corria la rama de rename. El problema era propio de PostgreSQL y no se detectaba con una prueba basada solo en SQLite.

## Correccion

La migracion de rename ahora usa `SeparateDatabaseAndState`:

- En base de datos PostgreSQL renombra el indice solo si existe.
- Si el indice de producto falta, lo recrea con la definicion esperada.
- Si el indice legacy de descuento ya fue eliminado por la rama paralela, no lo recrea salvo que la columna legacy todavia exista.
- El estado de Django conserva los `RenameIndex` necesarios para que la cadena historica siga consistente.

La migracion `0014_alter_category_options_alter_modifier_options_and_more` ahora elimina el indice legacy de descuento con `DROP INDEX IF EXISTS`, porque ese indice puede no existir en bases que aplicaron primero la rama que elimina `active`.

Durante la nueva validacion `makemigrations --check --dry-run` tambien aparecieron diferencias de estado ya existentes por nombres autogenerados de indices en `employees`, `inventory` y auditoria de precios. Se alinearon los modelos con los nombres ya migrados. En `inventory` habia tres nombres historicos de `InventoryMovement` que no se pueden declarar en modelos porque exceden el limite que valida Django; se agrego `inventory.0007_rename_inventory_movement_indexes` con SQL defensivo para renombrarlos de forma idempotente.

## Prueba PostgreSQL limpia

Se agrego `scripts/ci/test_django_migrations_postgres.py`. La prueba crea una base y un rol temporales en PostgreSQL, configura `DJANGO_ENV_FILE` temporal sin secretos reales, ejecuta:

- `migrate --noinput`
- `migrate --noinput` de nuevo
- `showmigrations menu`
- `showmigrations --plan`
- `check_runtime_config --strict`
- `makemigrations --check --dry-run`
- `SELECT 1`
- verificacion de indices finales de `menu`

El workflow `windows-native-installer.yml` ejecuta esta prueba en un job Linux con PostgreSQL 16 antes de construir y publicar el instalador Windows.

## Windows, idioma y PowerShell 5.1

El instalador registra `Get-WindowsInstallProfile` con caption/version/build, arquitectura, PowerShell, CLR, cultura, UI culture, locale, code pages, usuario, dominio, rutas reales y disponibilidad de herramientas nativas. El log queda delimitado por:

```text
INSTALL_PROFILE_BEGIN
INSTALL_PROFILE clave=valor
INSTALL_PROFILE_END
```

El instalador valida Windows 10/11 x64 al inicio. La logica critica usa SIDs y APIs, no nombres localizados. Los helpers de comandos nativos usan `.Arguments` con quoting compatible con PowerShell 5.1; no dependen de `ProcessStartInfo.ArgumentList`.

## PostgreSQL local

Se mantiene PostgreSQL embebido/local. No se cambia a SQLite. PostgreSQL sigue:

- incluido en el instalador,
- escuchando solo en `127.0.0.1`,
- ejecutandose como `PicoDeGalloSvc`,
- configurado con UTF-8 sin BOM,
- sin desactivar `fsync`,
- con `pg_hba.conf` local seguro.

## Puertos

Se agrego seleccion de puertos con `PICO_PORT_MODE=auto`:

- DB: 5432, fallback 55432+
- Backend: 8000, fallback 18000+
- App/Caddy: 9282, fallback 9283+

Las decisiones quedan en logs como `PORT_DECISION port=... status=... selected=...`. Los puertos elegidos se guardan en `.env` y en `C:\ProgramData\PicoDeGallo\config\runtime-ports.json`. Backend, Caddyfile, healthchecks y acceso directo usan esos valores.

## Idempotencia sobre 0.1.11-test parcial

0.1.12-test esta preparado para instalar encima del estado parcial conocido:

- no borra `C:\ProgramData\PicoDeGallo`,
- no borra `postgres\data`,
- no repite `initdb` si `PG_VERSION` existe,
- revalida configuracion PostgreSQL,
- ejecuta migraciones de forma idempotente,
- continua con `collectstatic`, admin de prueba, servicios y healthchecks.

Si `migrate` falla, se guardan stdout/stderr, plan de migraciones, snapshot de `django_migrations` y snapshot de `pg_indexes`.

## Estado de instalacion

El instalador escribe `C:\ProgramData\PicoDeGallo\install-state.json` sin secretos. Incluye version, fase, ultima fase exitosa, fase fallida, puertos, perfil OS, estado de DB, PostgreSQL, migraciones, servicios y health.

## DTE y admin de prueba

DTE sigue activo en modo externo. El instalador no contacta Hacienda durante CI y no envia DTE reales. `admin/000000` es solo para builds 0.1.x de prueba y debe cambiarse o desactivarse antes de produccion.

## Pruebas manuales

1. Instalar 0.1.12-test encima del estado parcial de 0.1.11-test sin borrar `C:\ProgramData\PicoDeGallo`.
2. Verificar `PicoDeGallo-PostgreSQL`, `PicoDeGallo-Backend`, `PicoDeGallo-DTE-Worker`, `PicoDeGallo-DTE-Monitor` y `PicoDeGallo-Caddy`.
3. Verificar puertos desde `runtime-ports.json`.
4. Probar `/api/health/live/` y `/api/health/ready/` en backend directo y via Caddy.
5. Si falla, ejecutar `diagnostics.ps1` de 0.1.12-test y revisar el zip generado.
6. Repetir en VM limpia Windows 10/11 x64.
