import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { BarChart3, ChefHat, ClipboardList, FileText, LogOut, Settings, ShoppingCart, Store, Tags, Users, Moon, Sun } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const MainMenu = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const cards = useMemo(
    () => [
      { label: "POS", path: "/pos", icon: ShoppingCart },
      { label: "KIOSK", path: "/kiosk", icon: Store },
      { label: "COCINA", path: "/kitchen", icon: ChefHat },
      { label: "PEDIDOS CLIENTES", path: "/customer-display", icon: ClipboardList },
      { label: "MENÚ & DESCUENTOS", path: "/menu", icon: Tags },
      { label: "REGISTROS", path: "/registros/ventas", icon: BarChart3 },
      { label: "DTE", path: "/dte", icon: FileText },
      { label: "CLIENTES", path: "/clientes", icon: Users },
      { label: "CONFIGURACIÓN", path: "/settings", icon: Settings },
    ],
    []
  );

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <div className="min-h-screen bg-background p-4 sm:p-6">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-7xl flex-col justify-center gap-6">
        <div className="space-y-1 text-center">
          <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">Centro de Control</p>
          <h1 className="text-3xl font-bold text-foreground sm:text-4xl">Pico de Gallo POS</h1>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <Button key={card.path} className="h-24 justify-start gap-3 rounded-2xl px-6 text-lg font-semibold shadow-sm" onClick={() => navigate(card.path)}>
              <card.icon className="h-6 w-6" />
              {card.label}
            </Button>
          ))}
          <Button className="h-24 justify-start gap-3 rounded-2xl px-6 text-lg font-semibold shadow-sm" variant="outline" onClick={toggleTheme}>
            {theme === "light" ? <Moon className="h-6 w-6" /> : <Sun className="h-6 w-6" />}
            Tema
          </Button>
          <Button
            className="h-24 justify-start gap-3 rounded-2xl px-6 text-lg font-semibold shadow-sm"
            variant="destructive"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-6 w-6" />
            Cerrar sesión
          </Button>
        </div>
      </div>
    </div>
  );
};

export default MainMenu;
