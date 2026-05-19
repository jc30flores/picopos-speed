import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { BarChart3, ChefHat, ClipboardList, Boxes, FileText, LogOut, Settings, ShoppingCart, Store, Tags, Users, Moon, Sun, LayoutGrid } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppModuleKey, appModules, filterModulesForUser } from "@/lib/roleAccess";
import { getFeatureFlags, getFeatureSettings, normalizeFeatureFlags } from "@/lib/api";
import { ClockSV } from "@/components/ClockSV";
import { AttendancePanel } from "@/components/attendance/AttendancePanel";
import { useAttendanceAccess } from "@/context/useAttendanceAccess";
import { toast } from "sonner";

const iconByModule: Partial<Record<AppModuleKey, LucideIcon>> = {
  pos: ShoppingCart,
  pending: ClipboardList,
  kiosk: Store,
  kitchen: ChefHat,
  orders_customers: ClipboardList,
  menu_discounts: Tags,
  inventory: Boxes,
  registers: BarChart3,
  dte: FileText,
  clients: Users,
  settings: Settings,
};

const DEFAULT_MENU_ICON: LucideIcon = LayoutGrid;

const MainMenu = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { attendance, accessState, attendanceLoading, attendanceResolved, attendanceError } = useAttendanceAccess();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const [featureVisibility, setFeatureVisibility] = useState({ kiosk: true, kitchen: true, customerDisplay: true, loaded: false });

  useEffect(() => {
    Promise.all([getFeatureSettings(), getFeatureFlags().catch(() => [])])
      .then(([settings, coreFlags]) => {
        const normalizedFromSettings = normalizeFeatureFlags(settings);
        const normalizedFromCore = normalizeFeatureFlags(coreFlags.map((f) => ({ key: f.key, enabled: f.isEnabled })));
        const normalized = { ...normalizedFromCore, ...normalizedFromSettings };
        console.info("FEATURE_FLAGS_RAW_SETTINGS_RESPONSE", settings);
        console.info("FEATURE_FLAGS_RAW_CORE_RESPONSE", coreFlags);
        console.info("FEATURE_FLAGS_NORMALIZED", normalized);
        setFeatureVisibility({ kiosk: normalized.kioskEnabled, kitchen: normalized.kitchenDisplayEnabled, customerDisplay: normalized.customerDisplayEnabled, loaded: true });
      })
      .catch((error) => {
        const status = error instanceof Error && "status" in error ? (error as { status?: number }).status : undefined;
        console.warn("FEATURE_FLAGS_LOAD_FAILED", {
          status: status ?? null,
          non_blocking: true,
          keep_authenticated: true,
        });
      });
  }, []);

  const cards = useMemo(
    () =>
      filterModulesForUser(user, appModules)
        .filter((module) => module.key !== "dte")
        .filter((module) => {
          if (module.key === "kiosk") return featureVisibility.kiosk !== false;
          if (module.key === "kitchen") return featureVisibility.kitchen !== false;
          if (module.key === "orders_customers") return featureVisibility.customerDisplay !== false;
          return true;
        })
        .map((module) => ({ ...module, icon: iconByModule[module.key] ?? DEFAULT_MENU_ICON })),
    [featureVisibility.customerDisplay, featureVisibility.kiosk, featureVisibility.kitchen, user]
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
          <h1 className="text-3xl font-bold text-foreground sm:text-4xl">Pico de Gallo POS</h1>
          <p className="text-sm text-muted-foreground">Bienvenido, {user?.username ?? "Usuario"}</p>
          <div className="mx-auto mt-4 max-w-md">
            <ClockSV className="bg-background/50" timeClassName="text-5xl sm:text-6xl" />
          </div>
        </div>
        <AttendancePanel />
        {!isWorker ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((card) => {
              const CardIcon = card.icon ?? DEFAULT_MENU_ICON;
              return (
              <Button
                key={card.path}
                className="h-24 justify-start gap-3 rounded-2xl bg-secondary text-secondary-foreground px-6 text-lg font-semibold shadow-sm enabled:hover:bg-secondary/90"
                onClick={() => {
                  const canEvaluateAttendanceGuard = attendanceResolved && !attendanceLoading;
                  const blockedByAttendance = canEvaluateAttendanceGuard && !accessState.canAccessDashboard;
                  console.info("attendance.home.module_click", {
                    userId: user?.id ?? null,
                    role: user?.role ?? null,
                    path: card.path,
                    attendanceResolved,
                    attendanceLoading,
                    canEvaluateAttendanceGuard,
                    blockedByAttendance,
                    hasClockInToday: accessState.hasClockInToday,
                    hasClockOutToday: accessState.hasClockOutToday,
                    hasActiveSession: attendance?.hasActiveSession ?? false,
                    canAccessDashboard: accessState.canAccessDashboard,
                    attendanceError,
                  });
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
