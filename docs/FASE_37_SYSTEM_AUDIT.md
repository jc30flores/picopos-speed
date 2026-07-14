# Fase 37 - Auditoria incremental del sistema

Fecha: 2026-07-14

## Alcance

Revision conservadora posterior a la estabilizacion del flujo de mesas. No se tocaron puertos, dominios, Cloudflare, Caddy, systemd, tuneles, URLs publicas, `backend/.env`, PWA/iconos ni configuracion de base de datos.

Base verificada: `roseedb`.

## Correcciones aplicadas

### Autenticacion

- Se agrego throttle temporal al login normal por IP + identificador de usuario.
- El login por PIN ya tenia throttle; ahora tambien usa el mismo helper de IP para respetar proxy headers.
- No se registran PINs ni passwords en logs.
- Un login exitoso limpia el contador de intentos fallidos.

### Preview de tickets en reportes

- El preview de ticket de historial de ventas ya no inyecta HTML directamente en el DOM principal.
- El contenido se renderiza en un `iframe` con `sandbox` y `referrerPolicy="no-referrer"`.
- El fallback de ticket en texto plano escapa HTML antes de renderizar.

### Asistencia

- Se elimino un `return` dentro de `finally` en la validacion de asistencia para evitar estados ocultos o warnings de `no-unsafe-finally`.

### Deuda de tipos puntual

- Se corrigieron dos tipos vacios en componentes UI compartidos (`CommandDialogProps`, `TextareaProps`) sin cambiar comportamiento visual.

## Hallazgos no corregidos por alcance

### Seguridad de despliegue

`manage.py check --deploy` reporta configuraciones que deben resolverse desde entorno/infra:

- `DEBUG=True`.
- `DJANGO_SECRET_KEY` debil o de desarrollo.
- `SECURE_HSTS_SECONDS` no configurado.
- `SECURE_SSL_REDIRECT` no forzado desde Django.
- `SESSION_COOKIE_SECURE=False`.
- `CSRF_COOKIE_SECURE=False`.

No se cambiaron estos valores porque la iteracion no debe tocar `.env`, proxy, dominios ni configuracion de infraestructura.

### Lint frontend

`npm run lint -- --max-warnings=0` sigue fallando por deuda previa extensa:

- Uso amplio de `any` en `frontend/src/lib/api.ts`, `Index.tsx`, `Inventory.tsx`, `TablesEditor.tsx` y otros.
- Warnings de dependencias en hooks.
- `eslint-disable` sobrantes.
- Fast refresh warnings en algunos componentes UI.

No se corrigio toda esa deuda porque implicaria refactor amplio sobre flujos ya validados.

### Performance

`npm run build` pasa, pero Vite advierte que el bundle principal supera 500 kB. La mejora recomendable es code splitting por rutas/modulos pesados, pero se deja para una fase separada porque puede afectar carga de POS, reportes, cocina y configuracion.

## Validaciones realizadas

- `backend/venv/bin/python backend/manage.py check`: OK.
- `backend/venv/bin/python backend/manage.py check --deploy`: warnings de configuracion documentados.
- `npm run typecheck`: OK.
- `npm run build`: OK con warning de bundle grande.
- `git diff --check`: OK.
- Logs `journalctl -u la-rosee-project`: sin tracebacks, sin 500/422/404/403 relevantes en la ventana revisada.

## Pendientes recomendados

1. Endurecer variables de entorno de produccion: `DEBUG=False`, `DJANGO_SECRET_KEY` fuerte, cookies secure y HSTS.
2. Planificar code splitting del frontend para bajar el bundle inicial.
3. Reducir deuda de `any` en `frontend/src/lib/api.ts` por modulos, no en una sola pasada.
4. Revisar warnings de hooks en pantallas de reportes/inventario con pruebas funcionales por flujo.
