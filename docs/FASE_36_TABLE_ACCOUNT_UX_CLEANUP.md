# FASE 36 - Limpieza de menú de mesa y Cuenta de mesa

## Alcance

Esta fase ajusta solo la experiencia visual del menú contextual de mesas y del modal `Cuenta de mesa`. No se tocaron infraestructura, puertos, dominios, `.env`, PWA, DTE ni backend de pagos.

## Menú contextual de mesa

Se eliminaron estas acciones del menú contextual:

- `Enviar cocina`
- `Dividir cuenta`
- `Cerrar`

El menú queda más directo:

- Mesa libre: `Nueva orden`, `Unir mesa` si aplica.
- Mesa ocupada: `Agregar productos`, `Ver cuenta`, `Cobrar`, `Mover mesa`, `Unir mesa`, `Liberar mesa`.
- Grupo: `Agregar productos`, `Ver cuenta conjunta`, `Cobrar grupo`, `Mover grupo`, `Unir mesa`, `Separar mesa`, `Liberar grupo`.

El menú se sigue cerrando al tocar fuera, con `Escape` o al seleccionar una acción.

## Cuenta de mesa

El modal se redujo a un ancho máximo compacto de 48rem, con header, body y footer más densos. El resumen superior ahora muestra mesa, personas, estado, total, pagado y pendiente en una línea compacta.

Los filtros se separaron:

- Fila 1: botones de personas (`Todos`, `Persona 1`, `Persona 2`, etc.).
- Fila 2: selector único `Estado`, con `Todos`, `Pendiente de enviar`, `En cocina`, `Terminados`, `Servidos` y `Pagados`.

Los productos se filtran combinando persona y estado. En `Todos`, se mantiene el agrupado por persona.

## Estados visuales

Cada producto conserva su chip de estado:

- Pendiente de enviar: azul suave.
- En cocina: ámbar.
- Terminado: verde.
- Servido: azul.
- Pagado: violeta.

Los colores usan variantes con contraste compatible con modo claro y oscuro.

## Pruebas realizadas

- `git diff --check`
- `backend/venv/bin/python backend/manage.py check`
- `backend/venv/bin/python backend/manage.py migrate`
- verificación de DB `roseedb`
- `backend/venv/bin/python backend/manage.py ensure_superadmin`
- `cd frontend && npm run build`

## Pendientes

- `migrate` sigue reportando cambios de modelo previos en `employees`, `inventory` y `menu` sin migración. No pertenecen a esta fase.
- La confirmación visual final debe hacerse en navegador con una mesa activa para validar ancho, filtros y footer en tablet/móvil real.
