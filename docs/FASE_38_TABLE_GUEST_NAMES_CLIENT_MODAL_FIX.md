# Fase 38 - Nombres de personas y modal Cliente

## Alcance

Esta fase agrega nombres personalizados persistentes para las personas de una orden de mesa y corrige el modal Cliente que se abría tarde al cambiar de flujo.

No se cambió base de datos configurada, puertos, dominios, Cloudflare, Caddy, systemd, túneles, PWA, favicon, manifest ni `backend/.env`.

## Renombrar personas

En órdenes de mesa con modo `Por persona`, cada botón de persona mantiene su click normal para seleccionar:

- `Persona 1`
- `Persona 2`
- `Persona 3`

Para renombrar:

- Desktop: mantener presionado el botón unos 600 ms o usar click derecho.
- Touch/tablet: mantener presionado unos 600 ms.

Se abre un modal pequeño con:

- Título: `Nombre de persona`
- Input vacío.
- Botón `Asignar`.
- Botón `Borrar`.

`Asignar` guarda el texto escrito, recortado y limitado a 40 caracteres. `Borrar` limpia el nombre personalizado y vuelve al texto base, por ejemplo `Persona 1`.

## Persistencia backend

Se agregó `TableGuest.display_name` como campo opcional. El serializer expone:

- `label`: nombre final visible (`display_name` si existe, si no `Persona N`).
- `base_label`: nombre base.
- `display_name` / `custom_name`: nombre personalizado guardado.

Endpoint:

```http
POST /api/orders/tables/sessions/<session_id>/guests/<guest_number>/rename/
```

Payload para asignar:

```json
{ "name": "Carlos" }
```

Payload para borrar:

```json
{ "name": "" }
```

El endpoint valida que la sesion de mesa este activa, que sea una orden por persona y que el numero de persona pertenezca a esa sesion.

## Donde se muestran los nombres

El nombre personalizado se usa en:

- Selector de personas del POS de mesa.
- Cuenta de mesa.
- Resumen de cocina de mesas.
- Pantalla de cocina.
- Listos para servir.
- Ticket local / precuenta.
- Recibo pagado cuando el cobro se construye desde el alcance de la persona.

Los items siguen vinculados por `table_guest_id`, no por texto, para evitar mezclar productos si dos personas tienen nombres parecidos.

## Modal Cliente

Causa raiz: en el mapa de mesas el boton Cliente dentro del cobro ejecutaba `setIsCustomerDteOpen(true)`, pero el dialogo Cliente solo estaba montado en el retorno del POS de productos. El estado quedaba pendiente y el modal aparecia despues al navegar a ese flujo.

Correccion:

- El flujo de mapa de mesas monta su propio dialogo Cliente/DTE y selector de cliente.
- Click en Cliente abre el modal en esa misma pantalla.
- Al cerrar, tambien se limpia el selector interno.
- En POS rapido se mantiene el flujo existente con administracion/creacion rapida.
- En mesa se permite seleccionar cliente o volver a Consumidor final sin dejar banderas pendientes.

## Pruebas ejecutadas

- `git diff --check`: OK.
- `backend/venv/bin/python backend/manage.py check`: OK.
- `backend/venv/bin/python backend/manage.py migrate`: OK, sin migraciones pendientes.
- `backend/venv/bin/python backend/manage.py ensure_superadmin`: OK.
- Verificacion DB por Django y PostgreSQL: `roseedb` / `roseedb`.
- `cd frontend && npm run build`: OK.
- `cd frontend && npm run lint -- --max-warnings=0`: falla por deuda existente fuera de esta fase (`any`, hooks y fast-refresh en multiples archivos).
- `journalctl -u la-rosee-project --since "2026-07-14 20:12:00" --no-pager`: sin tracebacks ni 500 nuevos; solo HMR de Vite.

## Pendientes y riesgos

- Las pruebas manuales completas dependen de una sesion real en navegador con mesas activas.
- El build mantiene warnings existentes de Browserslist desactualizado y chunk grande de Vite.
- `migrate` avisa que `employees`, `inventory` y `menu` tienen cambios de modelo sin migracion; son cambios no relacionados ya presentes en el worktree.
- Hay cambios no relacionados ya presentes en el worktree; esta fase debe commitear solo los archivos de nombres de persona, modal Cliente y esta documentacion.
