import type { AuthUser } from "@/lib/api";

export type AppRole = AuthUser["role"];

export const allowedRoutesByRole: Record<AppRole, string[]> = {
  admin: ["/", "/kiosk", "/kitchen", "/customer-display", "/clientes", "/menu", "/registros/ventas", "/registros/caja", "/dte", "/settings"],
  manager: ["/", "/menu", "/clientes", "/registros/ventas"],
  cashier: ["/", "/registros/ventas"],
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

export const canAccessPath = (role: AppRole, path: string) => {
  if (path.startsWith("/registros")) {
    return allowedRoutesByRole[role].includes("/registros/ventas") && (path === "/registros/ventas" || (role === "admin" && path === "/registros/caja"));
  }
  return allowedRoutesByRole[role].some((allowed) => path === allowed || path.startsWith(`${allowed}/`));
};
