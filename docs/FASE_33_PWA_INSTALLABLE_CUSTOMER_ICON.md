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

## Correccion de preview, manifest e iconos

Se corrigio la carga del logo de ticket para que Configuracion no use una ruta `/media/...` que puede quedar fuera del proxy del frontend. El endpoint `/api/settings/ticket/` ahora devuelve una URL publica y versionada de logo:

- `/api/public/pwa/customer-logo.png?v=<branding_version>`

Si el archivo no existe o esta corrupto, el endpoint devuelve `null` para el preview y los iconos PWA usan el fallback default, sin imagen rota ni 500.

La metadata publica de PWA queda centralizada en:

- `/api/public/pwa/metadata/`

Campos relevantes:

- `branding_version`
- `logo_version`
- `customer_logo_url`
- `ticket_logo_url`
- `manifest_url`
- `favicon_url`
- `apple_touch_icon_url`
- `icon_192_url`
- `icon_512_url`
- `maskable_icon_url`

El frontend actualiza `manifest`, `favicon`, `shortcut icon` y `apple-touch-icon` reemplazando links existentes en lugar de agregar duplicados. En consola, `document.querySelectorAll('link[rel="manifest"]').length` debe quedar en `1`.

## Versionado unico

El `branding_version` ahora cambia cuando cambia cualquiera de estos datos:

- nombre de app
- nombre corto
- color principal
- `updated_at` de apariencia
- nombre del logo
- `updated_at` del logo
- tamano del archivo de logo
- `mtime` del archivo de logo

El manifest usa esa misma version para todos los iconos. Asi se evita mezclar `/manifest.webmanifest?v=<viejo>` con iconos `?v=<nuevo>`.

## Cache y service worker

El service worker usa caches `gastroposv-static-v2` y `gastroposv-pwa-v2`, elimina caches PWA anteriores durante `activate` y trata manifest/metadata como `network-fresh`.

Reglas:

- manifest y metadata: siempre red primero, cache solo como respaldo.
- iconos PWA con `?v=<branding_version>`: cacheables por URL versionada.
- iconos PWA sin version: red primero.
- APIs normales, pagos, clientes, reportes, DTE, caja y configuracion sensible: no se cachean.

Cuando se sube o elimina un logo, Configuracion refresca metadata PWA para actualizar favicon/manifest en la sesion actual.

## Nota para apps ya instaladas

Chrome/Android puede conservar el icono de un acceso directo ya instalado aunque el manifest cambie correctamente. Para verificar el nuevo icono del cliente, desinstalar/eliminar el acceso directo anterior y volver a instalar la PWA despues de recargar el sistema.

## OpenGraph / WhatsApp sin branding externo

El HTML inicial ya no contiene metadata, imagenes ni referencias externas de herramientas de prototipado. Los tags base quedan con branding propio:

- `title`: `La Rosee POS - Sistema de Punto de Venta`
- `description`: `Sistema POS para restaurante`
- `og:title`: `La Rosee POS - Sistema de Punto de Venta`
- `og:description`: `Sistema POS para restaurante`
- `og:site_name`: `GastroPOSV`
- `og:image`: `/api/public/pwa/share-image.png`
- `twitter:image`: `/api/public/pwa/share-image.png`

WhatsApp y otras redes normalmente no ejecutan JavaScript, por eso estos valores existen directamente en `frontend/index.html`. En navegadores normales React tambien refresca esos tags con la metadata publica actual.

## Share image dinamica

La vista previa social usa:

- `/api/public/pwa/share-image.png?v=<branding_version>`

La imagen se genera en backend con tamano `1200x630`, `Content-Type: image/png` y la misma version de branding que manifest/iconos.

Reglas:

- Si hay logo valido del cliente, se usa ese logo en la imagen social.
- No se mezcla el monograma `GP` si existe logo del cliente.
- Si no hay logo, se usa fallback propio GastroPOSV/GP.
- Si el logo esta corrupto o no existe, no hay 500; se genera fallback.

## Iconos con logo del cliente

Cuando existe logo valido:

- `favicon.ico`
- `apple-touch-icon.png`
- `icon-192.png`
- `icon-512.png`
- `icon-maskable-512.png`

usan un canvas transparente con el logo centrado y padding seguro. No se agrega fondo GP ni monograma sobre el logo del cliente. El fallback GP solo se usa cuando no hay logo valido.

## Version sincronizada

`/api/public/pwa/metadata/` devuelve tambien:

- `site_name`
- `share_image_url`

Todas las rutas versionadas comparten `branding_version`, incluyendo manifest, favicon, iconos y share image.

## Cache de WhatsApp y shortcuts

WhatsApp, Facebook, Telegram, iMessage, Android y Chrome pueden cachear previews o iconos instalados fuera del control de la app.

Para probar cambios de preview:

- compartir `https://la-rosee.cuskatech.com/?v=<branding_version>`
- usar Facebook Sharing Debugger si aplica
- esperar invalidacion de cache de WhatsApp si la URL base ya fue compartida

Para probar icono de shortcut:

- desinstalar/eliminar el acceso directo anterior
- limpiar cache del navegador si hace falta
- reinstalar la PWA desde Chrome
