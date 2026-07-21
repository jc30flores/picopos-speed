# Fase 45 - Seguridad de sesión y login táctil

## Causa de sesiones vivas por días

El sistema usaba sesión Django, pero el cierre por inactividad dependía del temporizador frontend. Si la página se cerraba, ese temporizador dejaba de correr. Django conservaba la cookie/sesión con su duración por defecto, por lo que una sesión podía seguir siendo aceptada días después.

## Expiración real en backend

Se agregó validación centralizada en backend con `SessionSecurityMiddleware`.

Al iniciar sesión por PIN o por usuario/PIN, el backend guarda en la sesión:

- `auth_login_at`
- `auth_last_activity`

En cada request autenticado no público se valida:

- `auth_last_activity` no debe exceder el timeout de inactividad.
- `auth_login_at` no debe exceder la edad máxima absoluta.

La actividad actualiza `auth_last_activity`, pero nunca renueva `auth_login_at`.

## Defaults nuevos

- `GASTROPOSV_IDLE_TIMEOUT_SECONDS=600`: 10 minutos.
- `GASTROPOSV_SESSION_MAX_AGE_SECONDS=43200`: 12 horas.
- `GASTROPOSV_SESSION_EXPIRE_AT_BROWSER_CLOSE=false`: configurable por entorno.

También se ajustó `SESSION_COOKIE_AGE` al máximo absoluto de 12 horas por defecto.

## Respuestas de expiración

Cuando la sesión expira, el backend ejecuta logout y responde `401` con payload JSON:

```json
{
  "detail": "Tu sesión expiró. Ingresa nuevamente.",
  "code": "session_expired"
}
```

Para inactividad:

```json
{
  "detail": "Tu sesión se cerró por inactividad.",
  "code": "idle_timeout"
}
```

Para duración máxima:

```json
{
  "detail": "Tu sesión venció por seguridad. Ingresa nuevamente.",
  "code": "max_session_age"
}
```

## Endpoints públicos excluidos

La validación no aplica a:

- `/api/public/appearance/`
- `/api/public/manifest.webmanifest`
- `/api/public/pwa/metadata/`
- `/api/public/pwa/favicon.ico`
- `/api/public/pwa/icon-192.png`
- `/api/public/pwa/icon-512.png`
- `/api/public/pwa/apple-touch-icon.png`
- `/api/public/pwa/icon-maskable-512.png`
- `/api/public/pwa/share-image.png`
- assets estáticos/media y healthchecks simples.
- login, PIN login, CSRF y logout.

`/api/auth/me/` sí detecta expiración y fuerza volver al login.

## Manejo frontend

`api.ts` detecta `session_expired`, `idle_timeout` y `max_session_age`. Cuando aparecen:

- emite evento de sesión expirada;
- limpia estado local de autenticación;
- limpia `selected_branch_id`, drafts POS y datos `auth:*` de `sessionStorage`;
- redirige a `/login`;
- muestra mensaje español sin exponer errores técnicos.

## Login PIN táctil

El teclado PIN ahora registra números en `onPointerDown`, no espera al `click` final. Para evitar duplicados, el `click` posterior del mismo toque se ignora.

También se ajustó:

- `touch-action: manipulation`;
- `user-select: none`;
- `-webkit-user-select: none`;
- `-webkit-tap-highlight-color: transparent`;
- transiciones cortas de 75ms;
- tamaño visual equivalente;
- refs internas para no perder dígitos en toques rápidos;
- bloqueo de ingreso mientras hay login en curso.

## Pruebas realizadas

- `manage.py check`: OK.
- Suite Django específica: no pudo crear DB de test por permisos PostgreSQL (`permission denied to create database`).
- Smoke transaccional sobre `roseedb` con rollback: OK.
  - Login nuevo guarda `auth_login_at` y `auth_last_activity`.
  - `auth/me` activo responde 200 y actualiza actividad.
  - `auth_last_activity` viejo responde 401 `idle_timeout`.
  - `auth_login_at` de una semana responde 401 `max_session_age`.
  - Endpoint público `/api/public/pwa/metadata/` responde 200 sin sesión.

## Pendientes y riesgos

- La prueba táctil completa debe validarse en tablet/celular real por latencia de hardware/navegador.
- El suite Django completo requiere permisos `CREATEDB` o una base de test precreada.
- Queda deuda previa de lint frontend no relacionada.
