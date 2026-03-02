# Welcome to your Lovable project

## Runtime ports

- Backend: http://localhost:8102
- Frontend: http://localhost:8182

### Menu images

- Product images are stored on disk in `backend/menu_image/<CATEGORIA>/`.
- Images are served locally from `http://localhost:8102/menu_image/...`.

### Startup order

1. Start the backend (`python backend/manage.py runserver`)
2. Start the frontend (`npm run dev` from `frontend/`)

### Database setup (required)

1. `python backend/manage.py dbcheck`
2. `python backend/manage.py migrate`
3. `python backend/manage.py schemacheck`
4. `python backend/manage.py initdb`
5. `python backend/manage.py runserver 0.0.0.0:8102`

### Core endpoints

- `GET /api/core/tax-config/active/` → active tax rate (IVA 13%)
- `GET /api/core/feature-flags/` → lista de funciones avanzadas
- `PATCH /api/core/feature-flags/{id}/` → activar/desactivar funciones

### Auth endpoints

- `GET /api/auth/csrf/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`

### Menu endpoints

- `GET /api/menu/discounts/`
- `POST /api/menu/discounts/`
- `PATCH /api/menu/discounts/{id}/`

### Reports endpoints

- `GET /api/reports/sales/` (filters: `date_from`, `date_to`, `service_type`, `status`)

### Employees/Settings endpoints

- `GET /api/employees/`
- `POST /api/employees/`
- `GET /api/employees/{id}/`
- `PATCH /api/employees/{id}/`
- `GET /api/employees/stats/`
- `GET /api/employees/attendance/` (filters: `date_from`, `date_to`, `employee_id`)
- `POST /api/employees/attendance/`
- `PATCH /api/employees/attendance/{id}/`
- `GET /api/employees/schedules/` (filter: `employee_id`)
- `POST /api/employees/schedules/`
- `PATCH /api/employees/schedules/{id}/`
- `DELETE /api/employees/schedules/{id}/`

### DTE (Facturación electrónica) env vars

Configura estas variables en tu entorno para el envío DTE:

- `MH_AMBIENTE`, `DTE_AMBIENTE`, `HACIENDA_AMBIENTE`
- `DTE_BASE_URL` (alias opcionales: `DTE_ENDPOINT`, `DTE_API_URL`)
- `DTE_API_AUTH_HEADER`, `DTE_API_AUTH_PREFIX`, `DTE_API_TOKEN`
- `DTE_TIMEOUT_SECONDS`
- `DTE_AUTORETRY_BACKOFF_SECONDS`, `DTE_AUTORETRY_BATCH_SIZE`, `DTE_MAX_RETRIES`
- `IVA_INCLUDED_DEFAULT`
- `DTE_EMISOR_DUI`, `DTE_NOMBRE_COMERCIAL`, `DTE_EMISOR_TELEFONO`, `DTE_EMISOR_CORREO`

Comando de reintento automático:

```sh
python backend/manage.py dte_autoresend --limit 25
```

### Payments endpoints

- `GET /api/payments/?order_id=`
- `POST /api/payments/`

### Refunds & voids endpoints

- `POST /api/refunds/`
- `GET /api/refunds/?order_id=`
- `POST /api/orders/{id}/void/`

### Printing endpoints (simulated)

- `POST /api/printing/jobs/`
- `GET /api/printing/jobs/?order_id=`
- `GET /api/printing/jobs/{id}/`
- `POST /api/printing/jobs/{id}/mark-printed/`
- `POST /api/printing/jobs/refund/`

Example: create employee

```sh
curl -X POST http://localhost:8102/api/employees/ \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Maria Gomez","email":"maria@example.com","role":"cashier","status":"active","branch_name_input":"Sucursal Centro"}'
```

Example: get active tax config

```sh
curl http://localhost:8102/api/core/tax-config/active/
```

Example: login (session + CSRF)

```sh
curl -c cookies.txt http://localhost:8102/api/auth/csrf/
curl -b cookies.txt -c cookies.txt \\
  -H "Content-Type: application/json" \\
  -H "X-CSRFToken: $(grep csrftoken cookies.txt | awk '{print $7}')" \\
  -d '{"username":"admin","password":"your-password"}' \\
  http://localhost:8102/api/auth/login/
```

Example: create payment

```sh
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $(grep csrftoken cookies.txt | awk '{print $7}')" \
  -d '{"order":123,"method":"cash","amount":25.00,"tip_amount":2.00}' \
  http://localhost:8102/api/payments/
```

Example: create print job (customer receipt)

```sh
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $(grep csrftoken cookies.txt | awk '{print $7}')" \
  -d '{"order_id":123,"type":"customer"}' \
  http://localhost:8102/api/printing/jobs/
```

Printing is simulated during development: jobs render to text/HTML and can be marked as printed.

Example: create refund

```sh
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $(grep csrftoken cookies.txt | awk '{print $7}')" \
  -d '{"order":123,"method":"cash","amount":5.00,"tip_refunded":0.00,"reason":"Cliente devolvió el producto"}' \
  http://localhost:8102/api/refunds/
```

Example: void order (unpaid)

```sh
curl -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $(grep csrftoken cookies.txt | awk '{print $7}')" \
  -d '{"reason":"Pedido duplicado"}' \
  http://localhost:8102/api/orders/123/void/
```

### Roles

- admin: full access
- manager: menu/settings/reports access
- cashier: POS/orders access
- kitchen: kitchen screen and order status updates

### Feature flags (módulos avanzados)

Los módulos nuevos se activan desde **Configuración > Funciones** o mediante la API. Flags disponibles:

- `FF_CUSTOMERS_LOYALTY`
- `FF_INVENTORY`
- `FF_SHIFTS_CASH`
- `FF_ADV_PERMISSIONS`
- `FF_REFUNDS`
- `FF_ADV_REPORTS`
- `FF_MULTI_BRANCH_ENFORCE`
- `FF_PUBLIC_API_WEBHOOKS`

### Create admin user

```sh
python backend/manage.py createadmin --email admin@example.com
```

### Reset database (development only)

```sh
python backend/manage.py resetdb --yes
```

Manual fallback (psql/cli):

```sh
dropdb gallo_db
createdb -O jarvis gallo_db
python backend/manage.py migrate
python backend/manage.py initdb
```

## Project info

**URL**: https://lovable.dev/projects/911d53b6-ed54-4a17-9c7c-a948722c3f8e

## How can I edit this code?

There are several ways of editing your application.

**Use Lovable**

Simply visit the [Lovable Project](https://lovable.dev/projects/911d53b6-ed54-4a17-9c7c-a948722c3f8e) and start prompting.

Changes made via Lovable will be committed automatically to this repo.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes. Pushed changes will also be reflected in Lovable.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## How can I deploy this project?

Simply open [Lovable](https://lovable.dev/projects/911d53b6-ed54-4a17-9c7c-a948722c3f8e) and click on Share -> Publish.

## Can I connect a custom domain to my Lovable project?

Yes, you can!

To connect a domain, navigate to Project > Settings > Domains and click Connect Domain.

Read more here: [Setting up a custom domain](https://docs.lovable.dev/features/custom-domain#custom-domain)

## POS rápido, ruteo de cocina y DTE

- **`requiresKitchen` en productos**: ahora cada producto tiene el flag `requires_kitchen` (`requiresKitchen` en frontend). Si está activo, la orden se enruta a cocina/customer display cuando aplica.
- **Qué cuenta como “extra de pago”**: en POS rápido solo se muestran modificadores con `price > 0` (por grupo/opción). Los grupos gratis/obligatorios no se muestran en caja.
- **Defaults en grupos requeridos (POS rápido)**: si un grupo requerido no se muestra y no recibe selección manual, el backend autocompleta con la primera opción activa del grupo para permitir guardar el ítem.
- **Fallo de Hacienda (DTE)**: al completar el pago, se crea/actualiza `OrderInvoice` y se intenta envío. Si falla, la venta no se pierde; queda `failed` con `hacienda_payload`, `hacienda_response` y `last_error` para reintentos.

## DTE module (Facturación electrónica)

### Variables de entorno
- `DTE_BRIDGE_MODE=mock|bridge` (por defecto `mock`).
- `DTE_BRIDGE_BASE_URL` y `DTE_BRIDGE_TOKEN` cuando se usa bridge real.
- `DTE_BRIDGE_CONNECT_TIMEOUT` y `DTE_BRIDGE_READ_TIMEOUT` para timeouts.

### Reintentos automáticos
Ejecutar:

```bash
python manage.py dte_autoresend --limit 50
```

### Pruebas locales con mock
En local usar `DTE_BRIDGE_MODE=mock`; el backend responderá aceptado o rechazado sin dependencia externa.
- Endpoints de envío a cliente (`/send-email/`, `/send-whatsapp/`) están en modo stub y responden `501 Not Implemented` hasta integrar proveedor real.
