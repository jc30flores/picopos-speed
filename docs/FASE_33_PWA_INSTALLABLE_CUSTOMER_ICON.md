# Fase 33 - PWA instalable con icono del cliente

## Alcance

Esta fase agrega comportamiento PWA instalable para GastroPOSV / La Rosee POS sin tocar infraestructura, base de datos, puertos, dominios, Caddy, Cloudflare, systemd, tuneles ni `.env`.

Base validada: `roseedb`.

## Instalacion PWA

Chrome y navegadores compatibles pueden instalar la app desde el menu del navegador o desde el boton `Instalar app` cuando el evento `beforeinstallprompt` esta disponible.

Al instalarse, el acceso directo abre el sistema con `display: standalone`, sin barra de navegador ni pestanas, usando `start_url: /` y `scope: /`.

## Manifest dinamico

El manifest se sirve desde:

- `/api/public/manifest.webmanifest`

Incluye:

- `name`
- `short_name`
- `description`
- `start_url`
- `scope`
- `display: standalone`
- `orientation: any`
- `theme_color`
- `background_color`
- iconos `192x192`, `512x512` y `maskable`

El `Content-Type` es `application/manifest+json`.

## Logo del cliente

La fuente de icono PWA reutiliza el logo ya existente de Configuracion > Tickets.

Prioridad actual:

1. Logo de ticket configurado por el cliente.
2. Icono default generado de GastroPOSV si no hay logo, el archivo no existe o la imagen esta corrupta.

No se versionan logos reales del cliente.

## Iconos PWA

Rutas publicas:

- `/api/public/pwa/icon-192.png`
- `/api/public/pwa/icon-512.png`
- `/api/public/pwa/icon-maskable-512.png`
- `/api/public/pwa/apple-touch-icon.png`
- `/api/public/pwa/favicon.ico`
- `/api/public/pwa/favicon-32.png`

Los iconos se generan con Pillow:

- lienzo cuadrado
- fondo con color principal configurado
- logo centrado
- proporcion preservada
- padding mayor en `maskable` para respetar safe area
- fallback monograma `GP` si no hay logo

## Favicon dinamico

Al cargar la app se consulta `/api/public/pwa/metadata/` y se actualiza:

- `document.title`
- `link rel="manifest"`
- `link rel="icon"`
- `link rel="shortcut icon"`
- `link rel="apple-touch-icon"`
- `meta theme-color`
- `meta application-name`
- `meta apple-mobile-web-app-title`
- `meta mobile-web-app-capable`

El HTML inicial tambien contiene fallbacks PWA para que el navegador detecte el manifest antes de que React termine de cargar.

## Version y cache

La version de branding se calcula con:

- nombre de app
- nombre corto
- color principal
- `updated_at` de apariencia
- nombre y `updated_at` del logo de ticket

El manifest y metadata usan cache corto. Los iconos usan `ETag`, `Cache-Control` y query param `?v=<version>`.

Cuando cambia el logo o color, el navegador ve nuevas URLs. En Android, un acceso directo ya instalado puede conservar el icono anterior por cache del sistema; puede requerir reinstalar la PWA para ver el nuevo icono.

## Service worker

El service worker se sirve desde:

- `/sw.js`

Estrategia:

- `network-first` para navegacion y app shell.
- `cache-first` para assets estaticos con hash de Vite.
- `network-first` para manifest, metadata e iconos PWA.
- `network-only` para `/api/` normal y `/media/`.
- No cachea pagos, clientes, reportes, DTE, caja ni configuracion sensible.
- No bloquea el arranque si el navegador no soporta service workers.

## Boton Instalar app

Se agrego un boton discreto en:

- Login
- Menu principal

Solo aparece si Chrome emite `beforeinstallprompt` y la app no esta en modo standalone/fullscreen.

Textos:

- `Instalar app`
- `Instalar GastroPOSV en este dispositivo`

## Pruebas sugeridas

1. Abrir `/api/public/manifest.webmanifest` y validar JSON.
2. Abrir `/api/public/pwa/icon-192.png` y `/api/public/pwa/icon-512.png`.
3. Revisar favicon en Chrome.
4. DevTools > Application:
   - manifest valido
   - iconos validos
   - display standalone
   - service worker activo
5. En Android/tablet:
   - Chrome ofrece instalar.
   - El acceso directo usa el logo del cliente.
   - Al abrir, se ve standalone.
6. Cambiar logo desde Configuracion y recargar.

## Pendientes / riesgos

- Validar instalacion en dispositivo Android fisico.
- Los accesos directos ya instalados pueden mantener icono viejo por cache del sistema.
- Si el logo es muy claro u oscuro contra el color principal, puede requerir un logo especifico para app en una fase futura.
