# Fase 39: Mesero, endpoints públicos, horario y cierre de caja

## Alcance

Esta fase corrige el bloqueo del rol Mesero en POS de mesas, el acceso público a branding/PWA, el bloqueo temprano del cierre de caja con cuentas abiertas y agrega configuración de horario de atención con autocierre seguro.

## Causa raíz

Los endpoints públicos de branding/PWA quedaban dentro del filtro de acceso por rol y algunas vistas no declaraban explícitamente `AllowAny`. En el frontend, las llamadas públicas pasaban por el mismo cliente de requests privados, por lo que un 403 público podía generar ruido de sesión.

El Mesero quedaba bloqueado porque el POS ejecutaba la verificación de caja como requisito general de entrada. Ese flujo aplica a cajero/gerente/admin/superadmin, pero no al servicio de mesas.

## Permisos de Mesero

Mesero puede entrar al mapa de mesas, crear órdenes de mesa, agregar productos, enviar a cocina, ver la cuenta de mesa, ver cocina en modo lectura y marcar productos terminados como servidos.

Mesero no puede abrir caja, cerrar caja, cobrar, usar el cobro de POS rápido ni operar reportes/configuración sensible.

Si Mesero intenta abrir caja, el backend responde: `El rol Mesero no puede abrir caja.`
Si Mesero intenta cobrar, el backend responde: `El rol Mesero no puede cobrar.`

## Permisos de caja

Pueden abrir caja y cobrar: cajero, gerente, admin y superadmin.

No puede abrir caja ni cobrar: Mesero.

La consulta de caja actual para Mesero responde 200 sin sesión abierta y explica que no necesita caja abierta para tomar órdenes en mesas.

## Endpoints públicos

Quedan públicos y sin dependencia de sesión:

- `/api/public/appearance/`
- `/api/public/pwa/metadata/`
- `/api/public/pwa/favicon.ico`
- `/api/public/pwa/icon-192.png`
- `/api/public/pwa/icon-512.png`
- `/api/public/pwa/apple-touch-icon.png`
- `/api/public/pwa/icon-maskable-512.png`
- `/api/public/manifest.webmanifest`
- `/api/public/pwa/share-image.png`

El frontend usa requests públicos sin credenciales y no dispara manejo de sesión por fallos públicos. Si branding/PWA falla, el POS conserva fallback visual.

## Horario de atención

Se agregó configuración en `Configuración > Funciones`:

- Activar horario de atención.
- Hora de apertura.
- Hora de cierre.
- Horas de gracia después del cierre, rango 0 a 24, default 4.
- Cerrar caja automáticamente si queda olvidada.
- Zona horaria default `America/El_Salvador`.

Gerente, admin y superadmin pueden configurar esta sección. Mesero, cocina y cajero común no.

## Autocierre de caja

El helper `maybe_auto_close_expired_cash_sessions(now=None)` corre desde endpoints de caja/cobro y también existe el comando:

```bash
backend/manage.py auto_close_cash_sessions
```

Solo actúa si el horario y el autocierre están activados. Detecta sesiones abiertas vencidas después de `hora de cierre + horas de gracia`, soporta cierres después de medianoche y es idempotente.

Si no hay cuentas abiertas en la sucursal de la caja, cierra la sesión con conteos en 0, `close_type=automatic_after_hours` y nota:

`Cierre automático por horario de atención. Conteo registrado en 0 por cierre olvidado.`

No toca pagos ya hechos ni DTE/Hacienda.

## Cuentas abiertas

Si existen cuentas abiertas, el autocierre no cierra la caja. Registra y reporta:

`Cierre automático omitido: existen cuentas abiertas.`

El cierre manual también bloquea desde el inicio cuando existen cuentas abiertas. El mensaje visible queda en español:

`No puedes cerrar la caja porque hay 2 cuentas abiertas. Resuelve o cobra esas cuentas antes de cerrar.`

El botón de confirmación queda deshabilitado desde el primer paso del cierre.

## Pruebas realizadas

- `backend/venv/bin/python backend/manage.py check`: OK.
- `backend/venv/bin/python backend/manage.py migrate`: OK, aplicó `cashier.0011` y `core.0024`.
- Confirmación DB: `roseedb` / `roseedb`.
- `backend/venv/bin/python backend/manage.py ensure_superadmin`: OK.
- `npm run build`: OK.
- Lint acotado a archivos nuevos/tocados de configuración: OK.
- `npm run lint -- --max-warnings=0`: falla por deuda previa amplia de `any`, hooks y fast refresh en archivos existentes.
- Tests Django seleccionados no corrieron porque PostgreSQL no permite crear base de test: `permission denied to create database`.
- `curl -I` públicos en dominio: appearance, metadata y favicon respondieron 200.
- Django `Client` con host público: todos los endpoints públicos listados respondieron 200.
- Smoke Mesero por API: caja actual 200 sin bloqueo; abrir caja 403 español; cobrar 403 español.
- Smoke autocierre con rollback: sucursal aislada sin cuentas cerró en 0 con `automatic_after_hours`; sucursal con cuentas abiertas omitió cierre.
- Logs recientes: endpoints públicos 200/304; sin `Forbidden` en `/api/public/*` durante la validación.

## Pendientes y riesgos

No se configuró cron/systemd para el comando de autocierre por instrucción de no tocar infraestructura. Por ahora corre al usar endpoints de caja/cobro y queda listo para programarse después.

Hay cuentas abiertas reales en la sucursal actual; por seguridad, el autocierre las omite hasta que se resuelvan o cobren.

El árbol de trabajo tenía cambios previos no relacionados antes de esta fase. Los commits de esta fase deben seleccionar solo los hunks correspondientes.
