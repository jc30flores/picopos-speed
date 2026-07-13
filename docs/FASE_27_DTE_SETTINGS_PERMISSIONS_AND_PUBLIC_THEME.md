# Fase 27 - DTE Settings, Permisos y Tema Publico

## Objetivo

Corregir errores visibles posteriores a branding/superadmin/DTE inicial:

- Evitar 403 molestos en login por tema y `auth/me`.
- Mantener Apariencia con preview local y aplicar solo al guardar.
- Consolidar toda configuracion fiscal en Configuracion > Hacienda / DTE.
- Restringir Funciones y Hacienda / DTE a superadmin.
- Usar configuracion DB como fuente principal del runtime DTE.
- Mantener DTE apagado como POS local sin intentos de envio.

## Tema publico seguro

Se agrego `GET /api/public/appearance/` sin autenticacion. Devuelve solo branding visual seguro:

- `app_display_name`
- color principal
- variables CSS
- paleta recomendada
- modo visual

No devuelve datos fiscales, permisos, secretos ni token. El frontend usa este endpoint para bootstrap/login y mantiene `/api/settings/appearance/` como endpoint autenticado para administracion.

## Apariencia

La UI separa:

- `draftColor`: color seleccionado para vista previa.
- `activeColor`: color persistido y aplicado al sistema.

Seleccionar paleta o escribir HEX cambia solo la vista previa. El sistema completo cambia al presionar `Aplicar`.

Se amplio la paleta segura con verdes, azules, teal, celestes, morados, rosados/fucsias, rojo, naranja, ambar, gris/slate, negro suave y turquesa. Los rosados/fucsias seguros incluyen `#DB2777`, `#E11D48`, `#C026D3`, `#BE185D`, `#EC4899` y `#A21CAF`.

## Hacienda / DTE consolidado

Todo lo fiscal vive en Configuracion > Hacienda / DTE:

- Activar/desactivar Hacienda.
- Ambiente, URL API, token, timeout y reintentos.
- Emisor.
- Sucursal principal.
- Correlativos / last number.
- Envio fiscal por correo.
- Envio fiscal por WhatsApp.
- PDF fiscal.
- JSON fiscal.

Se quitaron los toggles fiscales de Configuracion > Funciones. Los registros historicos de `FeatureFlag` quedan por compatibilidad, pero se excluyen de la UI y del endpoint tecnico de funciones.

## Permisos

Solo superadmin puede ver y modificar:

- Configuracion > Funciones.
- Configuracion > Hacienda / DTE.
- `/api/settings/features/`
- `/api/settings/features/options/`
- `/api/settings/dte/`
- `/api/settings/dte/correlatives/`
- `/api/settings/dte/correlatives/initialize/`
- `/api/settings/dte/test-connection/`

Admin, gerente, cajero, cocina, kiosk y worker no ven esas pestanas y reciben 403 claro si llaman endpoints tecnicos.

## DB como fuente DTE

El runtime DTE consulta `DTEGlobalSettings` y `DTEBranchConfig` antes que `.env`.

Reglas:

- Si DB dice DTE apagado, no se usa `.env` para reactivar ni enviar.
- Si DB dice DTE activo pero faltan URL/token/emisor/sucursal/correlativos, queda `CONFIG_PENDING` y no contacta Hacienda.
- `.env` queda solo como fallback tecnico para rutas antiguas cuando no existe configuracion DB activa.
- El token DB nunca se devuelve completo al frontend.

## DTE apagado

Con Hacienda/DTE apagado:

- POS sigue vendiendo local.
- No se envia a Hacienda.
- No se encola outbox.
- No se muestran acciones fiscales segun flags runtime.
- Worker DTE duerme con backoff largo y log throttled `DTE_WORKER_DISABLED sleeping`.

## Pruebas realizadas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- Validacion DB `gastrodb`.
- `npm run build`
- Endpoint publico `/api/public/appearance/` sin auth.
- Endpoints DTE/Funciones con superadmin y admin normal.
- Smoke transaccional rollback de pagos divididos:
  - tarjeta + efectivo.
  - tarjeta + transferencia + efectivo.
  - pago parcial.
  - efectivo sobrepagado con cambio.

## Pendientes

- Multi-sucursal real.
- Portal remoto.
- Licencias.
- Cifrado avanzado de secretos.
- Sincronizacion cloud.
- Pruebas automatizadas mas profundas con permisos para crear base de test.
