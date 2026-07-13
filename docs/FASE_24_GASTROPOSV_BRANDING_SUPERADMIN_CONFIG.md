# Fase 24 - GastroPOSV Branding, Superadmin y Configuración

## Base de trabajo

- Rama: `codex/gastroposv-config-superadmin-branding`
- Base local esperada: `gastrodb`
- La base legacy `gallo_db` no debe usarse para migraciones ni pruebas de esta fase.

## Marca visible

La marca visible del frontend pasa a `GastroPOSV` en título del navegador, login y menú principal.
Los nombres técnicos internos y rutas críticas del instalador Windows se mantienen sin renombrar en esta fase para reducir riesgo.

Constantes frontend:

- `APP_DISPLAY_NAME = "GastroPOSV"`
- `APP_SHORT_NAME = "GastroPOSV"`
- `APP_LEGACY_NAME = "Pico de Gallo"`

## Superadmin

Se agrega el rol `superadmin` en perfiles de usuario.

Reglas implementadas:

- `superadmin` tiene acceso completo.
- No aparece en el selector de roles del formulario de empleados.
- La API normal de empleados rechaza crear o asignar `superadmin`.
- Los empleados ligados a perfil `superadmin` no aparecen en el listado normal.
- El comando `python manage.py ensure_superadmin` garantiza el usuario técnico idempotente.

Credenciales iniciales:

- Usuario: `superadmin`
- PIN/clave: `102938`

La clave se guarda hasheada por Django. El comando no imprime la clave en logs.

## Apariencia

Se agrega Configuración > Apariencia.

Permite:

- Elegir color principal desde paleta segura.
- Ingresar color HEX personalizado.
- Validar contraste para modo claro y oscuro.
- Generar variantes CSS:
  - `--color-primary`
  - `--color-primary-hover`
  - `--color-primary-soft`
  - `--color-primary-border`
  - `--color-primary-text`
  - `--color-primary-contrast`
- Previsualizar botón principal, secundario, tarjeta, menú, toggle, badge y gráfico simple.
- Restaurar color predeterminado.

El color se guarda en DB y se carga al iniciar el frontend.

## Hacienda / DTE

Se agrega Configuración > Hacienda / DTE con configuración global inicial.

Campos:

- Envíos Hacienda activos.
- Ambiente pruebas/producción.
- URL API.
- Token/API key enmascarado.
- Timeout.
- Reintentos.
- Estado de configuración.
- Último error sanitizado.

Solo `superadmin` puede modificar configuración técnica, activar/desactivar Hacienda o cambiar producción.

Cuando Hacienda/DTE está apagado:

- El POS sigue funcionando localmente.
- Los envíos DTE se bloquean antes de crear outbox.
- Acciones manuales DTE responden con mensaje de desactivación.
- El tab DTE en reportes se oculta en frontend.

## Módulos

Configuración > Funciones queda visible solo para `superadmin`.

Se agregan toggles persistentes para:

- POS.
- Pedidos abiertos.
- Kiosk.
- Cocina.
- Pantalla cliente.
- Menú & descuentos.
- Inventario avanzado.
- Reportes.
- Clientes.
- Configuración para administradores.
- DTE / Hacienda.
- WhatsApp fiscal.
- Correo fiscal.
- Imágenes de productos en POS.
- Mapa de mesas.
- Totales esperados en cierre de caja.

Superadmin conserva acceso para reactivar módulos.

## Reportes

Cambios incluidos:

- El acceso a DTE en pestañas de reportes se oculta cuando Hacienda/DTE está desactivado.
- Superadmin se trata como rol administrativo para registros.
- El build frontend mantiene los reportes existentes sin romper endpoints.

## Cómo probar

1. Verificar DB:
   `python manage.py shell -c "from django.db import connection; print(connection.settings_dict['NAME'])"`
2. Aplicar migraciones en `gastrodb`:
   `python manage.py migrate`
3. Crear/verificar superadmin:
   `python manage.py ensure_superadmin`
4. Login superadmin:
   usuario `superadmin`, PIN `102938`.
5. Abrir Configuración:
   - Superadmin ve Funciones.
   - Admin no ve Funciones técnicas.
6. Cambiar color en Apariencia y verificar persistencia tras recargar.
7. Apagar Hacienda/DTE y verificar que desaparece el tab DTE en reportes.
8. Encender Hacienda/DTE solo como superadmin y completar URL/token antes de usar envíos reales.

## Pendiente

- Multi-sucursal completo.
- Portal remoto.
- Licencias.
- Sincronización cloud.
- Instalador Windows con nueva marca interna.
- Migrar toda referencia técnica interna legacy cuando Windows tenga una fase dedicada.
