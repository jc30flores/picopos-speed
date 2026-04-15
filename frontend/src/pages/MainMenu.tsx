import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { BarChart3, ChefHat, ClipboardList, FileText, LogOut, Settings, ShoppingCart, Store, Tags, Users, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppModuleKey, appModules, filterModulesForUser } from "@/lib/roleAccess";
import { ClockSV } from "@/components/ClockSV";
import { AttendancePanel } from "@/components/attendance/AttendancePanel";
import { getMyAttendanceToday } from "@/lib/api";
import { toast } from "sonner";

const iconByModule: Record<AppModuleKey, typeof ShoppingCart> = {
  pos: ShoppingCart,
  pending: ClipboardList,
  kiosk: Store,
  kitchen: ChefHat,
  orders_customers: ClipboardList,
  menu_discounts: Tags,
  registers: BarChart3,
  dte: FileText,
  clients: Users,
  settings: Settings,
};

const MainMenu = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));

  const cards = useMemo(
    () => filterModulesForUser(user, appModules).map((module) => ({ ...module, icon: iconByModule[module.key] })),
    [user]
  );
  const isWorker = user?.role === "worker";
  const isAttendanceBypassUser = Boolean(user?.isSuperuser || user?.role === "admin");
  const [hasActiveAttendance, setHasActiveAttendance] = useState<boolean>(true);

  useEffect(() => {
    if (!user || isAttendanceBypassUser) {
      setHasActiveAttendance(true);
      return;
    }
    let cancelled = false;
    const loadAttendanceState = async () => {
      try {
        const today = await getMyAttendanceToday();
        const active = Boolean(today.clockIn) && !today.clockOut;
        if (cancelled) return;
        setHasActiveAttendance(active);
        console.info("attendance.home.state", {
          userId: user.id,
          role: user.role,
          pathname: "/",
          clockIn: today.clockIn,
          clockOut: today.clockOut,
          hasActiveAttendance: active,
        });
      } catch (error) {
        if (cancelled) return;
        setHasActiveAttendance(false);
        console.info("attendance.home.state_error", {
          userId: user.id,
          role: user.role,
          pathname: "/",
          error: error instanceof Error ? error.message : String(error),
        });
      }
    };
    void loadAttendanceState();
    return () => {
      cancelled = true;
    };
  }, [isAttendanceBypassUser, user]);

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
            {cards.map((card) => (
              <Button
                key={card.path}
                className="h-24 justify-start gap-3 rounded-2xl bg-secondary text-secondary-foreground px-6 text-lg font-semibold shadow-sm enabled:hover:bg-secondary/90"
                onClick={() => {
                  const blockedByAttendance = !isAttendanceBypassUser && !hasActiveAttendance;
                  console.info("attendance.home.module_click", {
                    userId: user?.id ?? null,
                    role: user?.role ?? null,
                    path: card.path,
                    blockedByAttendance,
                  });
                  if (blockedByAttendance) {
                    toast.error("Debes marcar Entrada antes de continuar.");
                    return;
                  }
                  navigate(card.path);
                }}
              >
                <card.icon className="h-6 w-6" />
                {card.label}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default MainMenu;
