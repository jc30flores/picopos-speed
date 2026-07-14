import type { AuthUser } from "@/lib/api";

export type AppRole = AuthUser["role"];
export type AppModuleKey =
  | "pos"
  | "pending"
  | "kiosk"
  | "kitchen"
  | "orders_customers"
  | "menu_discounts"
  | "inventory"
  | "registers"
  | "dte"
  | "clients"
  | "settings"
  | "tables_editor";

export type AppModuleConfig = {
  key: AppModuleKey;
  label: string;
  path: string;
  requiredRoles: AppRole[];
};

export type RoleAccessUser = Pick<AuthUser, "role" | "isSuperuser"> | null;

export const appModules: AppModuleConfig[] = [
  { key: "pos", label: "POS", path: "/pos", requiredRoles: ["admin", "manager", "cashier", "waiter"] },
  { key: "pending", label: "PEDIDOS ABIERTOS", path: "/open-orders", requiredRoles: ["admin", "manager", "cashier"] },
  { key: "tables_editor", label: "Editor de mesas", path: "/tables/editor", requiredRoles: ["admin", "manager"] },
  { key: "kiosk", label: "KIOSK", path: "/kiosk", requiredRoles: ["admin", "kiosk"] },
  { key: "kitchen", label: "COCINA", path: "/kitchen", requiredRoles: ["admin", "manager", "kitchen", "waiter"] },
  { key: "orders_customers", label: "PEDIDOS CLIENTES", path: "/customer-display", requiredRoles: ["admin"] },
  { key: "menu_discounts", label: "MENÚ & DESCUENTOS", path: "/menu", requiredRoles: ["admin", "manager"] },
  { key: "inventory", label: "INVENTARIO", path: "/inventory", requiredRoles: ["admin", "manager"] },
  { key: "registers", label: "REPORTES", path: "/registros/ventas", requiredRoles: ["admin"] },
  { key: "dte", label: "DTE", path: "/dte", requiredRoles: ["superadmin"] },
  { key: "clients", label: "CLIENTES", path: "/clientes", requiredRoles: ["admin", "manager"] },
  { key: "settings", label: "CONFIGURACIÓN", path: "/settings", requiredRoles: ["admin"] },
];

export const canAccessModule = (user: RoleAccessUser, module: AppModuleConfig) => {
  if (!user) return false;
  if (user.role === "superadmin") return true;
  return module.requiredRoles.includes(user.role);
};

export const filterModulesForUser = (user: RoleAccessUser, modules: AppModuleConfig[] = appModules) =>
  modules.filter((module) => canAccessModule(user, module));

export const allowedRoutesByRole: Record<AppRole, string[]> = {
  superadmin: ["/", "/pos", "/tables/editor", "/open-orders", "/pendientes", "/kiosk", "/kitchen", "/customer-display", "/clientes", "/menu", "/inventory", "/registros/ventas", "/registros/caja", "/registros/reportes", "/registros/dte", "/registros/empleados", "/dte", "/settings"],
  admin: ["/", "/pos", "/tables/editor", "/open-orders", "/pendientes", "/kiosk", "/kitchen", "/customer-display", "/clientes", "/menu", "/inventory", "/registros/ventas", "/registros/caja", "/registros/reportes", "/registros/empleados", "/settings"],
  manager: ["/", "/pos", "/tables/editor", "/open-orders", "/pendientes", "/kitchen", "/menu", "/inventory", "/clientes"],
  cashier: ["/", "/pos", "/open-orders", "/pendientes"],
  waiter: ["/pos", "/kitchen"],
  kitchen: ["/kitchen"],
  kiosk: ["/kiosk"],
  worker: ["/"],
  accountant: ["/"],
};

export const allowedNavItemsByRole: Record<AppRole, Array<{ label: string; path: string }>> = {
  superadmin: [
    { label: "POS", path: "/" },
    { label: "Kiosk", path: "/kiosk" },
    { label: "Cocina", path: "/kitchen" },
    { label: "Pedidos Clientes", path: "/customer-display" },
    { label: "Menú & Descuentos", path: "/menu" },
    { label: "Inventario", path: "/inventory" },
    { label: "Reportes", path: "/registros/ventas" },
    { label: "Clientes", path: "/clientes" },
    { label: "Configuración", path: "/settings" },
  ],
  admin: [
    { label: "POS", path: "/" },
    { label: "Kiosk", path: "/kiosk" },
    { label: "Cocina", path: "/kitchen" },
    { label: "Pedidos Clientes", path: "/customer-display" },
    { label: "Menú & Descuentos", path: "/menu" },
    { label: "Inventario", path: "/inventory" },
    { label: "Reportes", path: "/registros/ventas" },
    { label: "Clientes", path: "/clientes" },
    { label: "Configuración", path: "/settings" },
  ],
  manager: [
    { label: "POS", path: "/" },
    { label: "Cocina", path: "/kitchen" },
    { label: "Menú & Descuentos", path: "/menu" },
    { label: "Inventario", path: "/inventory" },
    { label: "Clientes", path: "/clientes" },
  ],
  cashier: [
    { label: "POS", path: "/pos" },
  ],
  waiter: [
    { label: "Mapa de mesas", path: "/pos" },
    { label: "Cocina", path: "/kitchen" },
  ],
  kitchen: [{ label: "Cocina", path: "/kitchen" }],
  kiosk: [{ label: "Kiosk", path: "/kiosk" }],
  worker: [{ label: "Centro de Control", path: "/" }],
  accountant: [{ label: "POS", path: "/" }],
};

const landingRouteByRole: Record<AppRole, string> = {
  superadmin: "/",
  admin: "/",
  manager: "/",
  cashier: "/pos",
  waiter: "/pos",
  kitchen: "/kitchen",
  kiosk: "/kiosk",
  worker: "/",
  accountant: "/",
};

export const getLandingRouteForRole = (role: AppRole, isSuperuser = false) => {
  if (isSuperuser && role === "superadmin") return "/";
  return landingRouteByRole[role] ?? "/";
};

export const isRouteAllowed = (role: AppRole, path: string, isSuperuser = false) => {
  if (isSuperuser && role === "superadmin") return true;
  if (path.startsWith("/registros")) {
    if (path === "/registros/caja") return role === "admin";
    return allowedRoutesByRole[role].includes(path);
  }
  return allowedRoutesByRole[role].some((allowed) => path === allowed || path.startsWith(`${allowed}/`));
};

export const canAccessPath = isRouteAllowed;
