import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { BarChart3, ChefHat, ClipboardList, FileText, LogOut, Settings, ShoppingCart, Store, Tags, Users, Moon, Sun } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppModuleKey, appModules, filterModulesForUser } from "@/lib/roleAccess";
import { ClockSV } from "@/components/ClockSV";
import { AttendancePanel } from "@/components/attendance/AttendancePanel";

const MainMenu = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const iconByModule: Record<AppModuleKey, typeof ShoppingCart> = {
    pos: ShoppingCart,
    kiosk: Store,
    kitchen: ChefHat,
    orders_customers: ClipboardList,
    menu_discounts: Tags,
    registers: BarChart3,
    dte: FileText,
    clients: Users,
    settings: Settings,
  };

  const cards = useMemo(
    () => filterModulesForUser(user, appModules).map((module) => ({ ...module, icon: iconByModule[module.key] })),
    [user]
  );
  const isWorker = user?.role === "worker";

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <div className="min-h-screen bg-background p-4 sm:p-6">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-7xl flex-col justify-center gap-6">
        <div className="flex items-center justify-end gap-2">
          <Button className="h-9 gap-1.5 rounded-full px-3 text-xs sm:text-sm" variant="outline" onClick={toggleTheme}>
            {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            Tema
          </Button>
          <Button
            className="h-9 gap-1.5 rounded-full px-3 text-xs sm:text-sm"
            variant="destructive"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" />
            Salir
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
              <Button key={card.path} className="h-24 justify-start gap-3 rounded-2xl px-6 text-lg font-semibold shadow-sm" onClick={() => navigate(card.path)}>
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
