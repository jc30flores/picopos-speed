# Fase 28 - Permisos, tema, rendimiento y servicio en mesas

## Alcance

Esta fase corrige problemas reales detectados en la rama `codex/gastroposv-config-superadmin-branding` sobre la base local `gastrodb`.

## Permisos finales

- `Configuracion > Funciones` queda visible solo para usuarios con rol de producto `superadmin`.
- `Configuracion > Hacienda / DTE` queda visible solo para usuarios con rol de producto `superadmin`.
- Un usuario `admin`, aunque tenga `is_superuser=True` en Django, ya no se trata como superadmin de GastroPOSV.
- Los endpoints tecnicos `/api/settings/features/`, `/api/settings/dte/` y correlativos DTE devuelven `403` para admin/gerente/cajero/worker y `200` para `superadmin`.

## Menu principal

- El menu ya no renderiza modulos reales hasta tener usuario, permisos y feature flags.
- Durante la carga se muestra skeleton.
- Si falla la carga de flags, se muestra error claro y no se muestran todos los modulos por defecto.
- DTE y Pedidos abiertos no se muestran como botones del menu principal.

## Tema dinamico

- Se agregaron variables globales:
  - `--color-primary`
  - `--color-primary-hover`
  - `--color-primary-active`
  - `--color-primary-soft`
  - `--color-primary-muted`
  - `--color-primary-surface`
  - `--color-primary-border`
  - `--color-primary-ring`
  - `--color-primary-contrast`
  - `--color-primary-text`
  - `--color-primary-chart`
- Se agregaron utilidades CSS `gp-primary-*` para evitar hardcodes verdes.
- Se aplico el tema a reloj, panel de asistencia, controles clave del POS, ventas recientes, descuentos y editor/mapa de mesas.

## Rendimiento

- El tema publico se cachea en `localStorage` y se aplica antes de refrescarlo desde backend.
- En login no se llama `/api/auth/me/`; la pantalla puede cargar sin sesion.
- Las imagenes de producto en POS usan `loading="lazy"` y `decoding="async"`.
- El POS ya no bloquea el render esperando todas las imagenes.

## Modo de operacion

Configuracion desde `Configuracion > Funciones`:

- `quick_pos`: entra directo al POS rapido y desactiva mapa/editor de mesas.
- `table_service`: entra al mapa de mesas primero.
- `both`: permite POS rapido y servicio en mesas.

Tambien se guardan opciones:

- entrada inicial al POS (`quick_pos` o `table_map`)
- permitir unir mesas
- permitir mover mesa
- permitir dividir por persona
- permitir dividir por productos

La configuracion se guarda en metadata del flag `table_map_enabled`, sin migracion nueva.

## Flujo de mesas

- El POS respeta `operation_mode`.
- En modo mesas, se muestra mapa operativo.
- Nueva orden permite definir cantidad de personas y modo de orden por mesa o por persona.
- Se puede abrir orden asociada a mesa, volver a la mesa, unir mesa libre a sesion abierta y cobrar desde la mesa.
- El editor de mesas queda inaccesible cuando el modo de operacion es `quick_pos`.

## DTE apagado

- DTE/Hacienda sigue restringido a superadmin.
- Usuarios no superadmin no consultan configuracion DTE desde reportes.
- La pestana DTE y el boton "Enviar DTE" se ocultan para usuarios sin permiso o con DTE apagado.
- No se contacta Hacienda en pruebas.

## Pruebas realizadas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- Validacion DB: `gastrodb` / `gastrodb`
- `npm run build`
- Smoke con `APIClient` sobre `gastrodb`:
  - admin: `/api/settings/features/` 403
  - admin: `/api/settings/dte/` 403
  - superadmin: `/api/settings/features/` 200
  - superadmin: `/api/settings/dte/` 200

## Pendientes

- Flujo avanzado de cocina por mesa.
- Reservas.
- Multi-sucursal real.
- Portal remoto.
- Licencias.
- Optimizacion avanzada de imagenes/CDN.
- App movil para meseros, si aplica.
- Pruebas automatizadas completas cuando el usuario PostgreSQL tenga permiso `CREATE DATABASE`.
