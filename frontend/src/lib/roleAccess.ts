import type { AuthUser } from "@/lib/api";

export type AppRole = AuthUser["role"];
export type AppModuleKey =
  | "pos"
  | "kiosk"
  | "kitchen"
  | "orders_customers"
  | "menu_discounts"
  | "registers"
  | "dte"
  | "clients"
  | "settings";

export type AppModuleConfig = {
  key: AppModuleKey;
  label: string;
  path: string;
  requiredRoles: AppRole[];
};

export const appModules: AppModuleConfig[] = [
  { key: "pos", label: "POS", path: "/pos", requiredRoles: ["admin", "manager", "cashier"] },
  { key: "kiosk", label: "KIOSK", path: "/kiosk", requiredRoles: ["admin"] },
  { key: "kitchen", label: "COCINA", path: "/kitchen", requiredRoles: ["admin", "kitchen"] },
  { key: "orders_customers", label: "PEDIDOS CLIENTES", path: "/customer-display", requiredRoles: ["admin"] },
  { key: "menu_discounts", label: "MENÚ & DESCUENTOS", path: "/menu", requiredRoles: ["admin", "manager"] },
  { key: "registers", label: "REGISTROS", path: "/registros/ventas", requiredRoles: ["admin", "manager", "cashier"] },
  { key: "dte", label: "DTE", path: "/dte", requiredRoles: ["admin"] },
  { key: "clients", label: "CLIENTES", path: "/clientes", requiredRoles: ["admin", "manager"] },
  { key: "settings", label: "CONFIGURACIÓN", path: "/settings", requiredRoles: ["admin"] },
];

export const canAccessModule = (user: Pick<AuthUser, "role" | "isSuperuser"> | null, module: AppModuleConfig) => {
  if (!user) return false;
  if (user.isSuperuser) return true;
  return module.requiredRoles.includes(user.role);
};

export const filterModulesForUser = (user: Pick<AuthUser, "role" | "isSuperuser"> | null, modules: AppModuleConfig[] = appModules) =>
  modules.filter((module) => canAccessModule(user, module));

export const allowedRoutesByRole: Record<AppRole, string[]> = {
  admin: ["/", "/pos", "/kiosk", "/kitchen", "/customer-display", "/clientes", "/menu", "/registros/ventas", "/registros/caja", "/registros/reportes", "/dte", "/settings"],
  manager: ["/", "/pos", "/menu", "/clientes", "/registros/ventas", "/registros/reportes"],
  cashier: ["/", "/pos", "/registros/ventas", "/registros/reportes"],
  kitchen: ["/kitchen"],
  accountant: ["/"],
};

export const allowedNavItemsByRole: Record<AppRole, Array<{ label: string; path: string }>> = {
  admin: [
    { label: "POS", path: "/" },
    { label: "Kiosk", path: "/kiosk" },
    { label: "Cocina", path: "/kitchen" },
    { label: "Pedidos Clientes", path: "/customer-display" },
    { label: "Menú & Descuentos", path: "/menu" },
    { label: "Registros", path: "/registros/ventas" },
    { label: "DTE", path: "/dte" },
    { label: "Clientes", path: "/clientes" },
    { label: "Configuración", path: "/settings" },
  ],
  manager: [
    { label: "POS", path: "/" },
    { label: "Menú & Descuentos", path: "/menu" },
    { label: "Registros", path: "/registros/ventas" },
    { label: "Clientes", path: "/clientes" },
  ],
  cashier: [
    { label: "POS", path: "/" },
    { label: "Registros", path: "/registros/ventas" },
  ],
  kitchen: [{ label: "Cocina", path: "/kitchen" }],
  accountant: [{ label: "POS", path: "/" }],
};

export const canAccessPath = (role: AppRole, path: string, isSuperuser = false) => {
  if (isSuperuser) return true;
  if (path.startsWith("/registros")) {
    if (path === "/registros/caja") return role === "admin";
    return allowedRoutesByRole[role].includes(path);
  }
  return allowedRoutesByRole[role].some((allowed) => path === allowed || path.startsWith(`${allowed}/`));
};
