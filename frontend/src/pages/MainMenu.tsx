import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { BarChart3, ChefHat, ClipboardList, Boxes, LogOut, Settings, ShoppingCart, Store, Tags, Users, Moon, Sun, LayoutGrid } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppModuleKey, appModules, filterModulesForUser } from "@/lib/roleAccess";
import { getFeatureFlags, getRuntimeFeatureSettings, normalizeFeatureFlags } from "@/lib/api";
import { ClockSV } from "@/components/ClockSV";
import { AttendancePanel } from "@/components/attendance/AttendancePanel";
import { useAttendanceAccess } from "@/context/useAttendanceAccess";
import { toast } from "sonner";
import { APP_DISPLAY_NAME } from "@/lib/branding";

const isProductSuperadmin = (user: ReturnType<typeof useAuth>["user"]) =>
  Boolean(user?.permissions?.isSuperadmin || user?.role === "superadmin");

const iconByModule: Partial<Record<AppModuleKey, LucideIcon>> = {
  pos: ShoppingCart,
  pending: ClipboardList,
  kiosk: Store,
  kitchen: ChefHat,
  orders_customers: ClipboardList,
  menu_discounts: Tags,
  inventory: Boxes,
  registers: BarChart3,
  clients: Users,
  settings: Settings,
};

const DEFAULT_MENU_ICON: LucideIcon = LayoutGrid;

const MainMenu = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { accessState, attendanceLoading, attendanceResolved, attendanceError } = useAttendanceAccess();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const [featureVisibility, setFeatureVisibility] = useState({
    pos: false,
    openOrders: false,
    kiosk: false,
    kitchen: false,
    customerDisplay: false,
    menuDiscounts: false,
    inventory: false,
    reports: false,
    clients: false,
    settings: false,
    tableService: false,
    operationMode: "quick_pos" as "quick_pos" | "table_service" | "both",
    loaded: false,
  });
  const [featureError, setFeatureError] = useState<string | null>(null);

  useEffect(() => {
    setFeatureError(null);
    setFeatureVisibility((previous) => ({ ...previous, loaded: false }));
    Promise.all([getRuntimeFeatureSettings(), getFeatureFlags().catch(() => [])])
      .then(([settings, coreFlags]) => {
        const normalizedFromSettings = normalizeFeatureFlags(settings);
        const normalizedFromCore = normalizeFeatureFlags(coreFlags.map((f) => ({ key: f.key, enabled: f.isEnabled })));
        const normalized = { ...normalizedFromCore, ...normalizedFromSettings };
        const tableService = normalized.operationMode !== "quick_pos" && normalized.tableMapEnabled;
        const isSuperadmin = isProductSuperadmin(user);
        setFeatureVisibility({
          pos: normalized.posEnabled,
          openOrders: false,
          kiosk: normalized.kioskEnabled,
          kitchen: normalized.kitchenDisplayEnabled,
          customerDisplay: normalized.customerDisplayEnabled,
          menuDiscounts: normalized.menuDiscountsEnabled,
          inventory: normalized.inventoryModuleEnabled,
          reports: normalized.reportsEnabled,
          clients: normalized.clientsEnabled,
          settings: normalized.settingsEnabled || isSuperadmin,
          tableService,
          operationMode: normalized.operationMode,
          loaded: true,
        });
      })
      .catch((error) => {
        const status = error instanceof Error && "status" in error ? (error as { status?: number }).status : undefined;
        console.warn("FEATURE_FLAGS_LOAD_FAILED", {
          status: status ?? null,
          non_blocking: true,
          keep_authenticated: true,
        });
        setFeatureError("No se pudieron cargar los módulos disponibles.");
        setFeatureVisibility((previous) => ({ ...previous, loaded: false }));
      });
  }, [user]);

  const cards = useMemo(
    () =>
      filterModulesForUser(user, appModules)
        .filter((module) => {
          if (module.key === "pos") return featureVisibility.pos !== false;
          if (module.key === "pending") return false;
          if (module.key === "kiosk") return featureVisibility.kiosk !== false;
          if (module.key === "kitchen") return featureVisibility.kitchen !== false;
          if (module.key === "orders_customers") return featureVisibility.customerDisplay !== false;
          if (module.key === "menu_discounts") return featureVisibility.menuDiscounts !== false;
          if (module.key === "inventory") return featureVisibility.inventory !== false;
          if (module.key === "registers") return featureVisibility.reports !== false;
          if (module.key === "clients") return featureVisibility.clients !== false;
          if (module.key === "settings") return featureVisibility.settings !== false;
          if (module.key === "dte") return false;
          if (module.key === "tables_editor") return featureVisibility.tableService !== false;
          return true;
        })
        .map((module) => ({ ...module, icon: iconByModule[module.key] ?? DEFAULT_MENU_ICON })),
    [featureVisibility, user]
  );
  const isWorker = user?.role === "worker";

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <div className="min-h-screen bg-background p-3 sm:p-4">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col justify-start gap-4">
        <div className="flex items-center justify-end gap-2">
          <Button
            className="h-11 w-11 rounded-full border-border/70 p-0 hover:bg-accent/70 active:scale-[0.98]"
            variant="outline"
            onClick={toggleTheme}
            aria-label="Cambiar tema"
            title="Tema"
          >
            {theme === "light" ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
          </Button>
          <Button
            className="h-11 w-11 rounded-full p-0 active:scale-[0.98]"
            variant="outline"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut className="h-5 w-5" />
          </Button>
        </div>
        <div className="space-y-1 text-center">
          <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">Centro de Control</p>
          <h1 className="text-3xl font-bold text-foreground sm:text-4xl">{APP_DISPLAY_NAME}</h1>
          <p className="text-sm text-muted-foreground">Bienvenido, {user?.username ?? "Usuario"}</p>
          <div className="mx-auto mt-4 max-w-md">
            <ClockSV className="bg-background/50" timeClassName="text-5xl sm:text-6xl" />
          </div>
        </div>
        <AttendancePanel />
        {!isWorker ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {!featureVisibility.loaded ? (
              featureError ? (
                <div className="col-span-full rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                  {featureError}
                </div>
              ) : (
                Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="h-24 animate-pulse rounded-2xl border bg-muted/40" aria-label="Cargando módulos" />
                ))
              )
            ) : cards.map((card) => {
              const CardIcon = card.icon ?? DEFAULT_MENU_ICON;
              return (
              <Button
                key={card.path}
                className="h-24 justify-start gap-3 rounded-2xl bg-secondary text-secondary-foreground px-6 text-lg font-semibold shadow-sm enabled:hover:bg-secondary/90"
                onClick={() => {
                  const canEvaluateAttendanceGuard = attendanceResolved && !attendanceLoading;
                  const blockedByAttendance = canEvaluateAttendanceGuard && !accessState.canAccessDashboard;
                  if (blockedByAttendance) {
                    if (attendanceError) {
                      toast.error(`No se pudo validar asistencia: ${attendanceError}`);
                    } else if (accessState.blockReason === "ON_BREAK") {
                      toast.error("No puedes acceder mientras estás en break. Marca regreso de break para continuar.");
                    } else if (accessState.blockReason === "CLOCKED_OUT") {
                      toast.error("Tu jornada ya fue cerrada. Debes marcar Entrada en un nuevo turno.");
                    } else {
                      toast.error("Debes marcar Entrada antes de continuar.");
                    }
                    return;
                  }
                  navigate(card.path);
                }}
              >
                <CardIcon className="h-6 w-6" />
                {card.label}
              </Button>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default MainMenu;
