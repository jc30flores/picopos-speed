import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { Moon, Sun } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const MainMenu = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const cards = useMemo(
    () => [
      { label: "POS", path: "/pos" },
      { label: "KIOSK", path: "/kiosk" },
      { label: "COCINA", path: "/kitchen" },
      { label: "PEDIDOS CLIENTES", path: "/customer-display" },
      { label: "MENÚ & DESCUENTOS", path: "/menu" },
      { label: "REGISTROS", path: "/registros/ventas" },
      { label: "DTE", path: "/dte" },
      { label: "CLIENTES", path: "/clientes" },
      { label: "CONFIGURACIÓN", path: "/settings" },
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
      <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 pb-4">
        <Button className="h-14 px-6 text-base" variant="outline" onClick={toggleTheme}>
          {theme === "light" ? <Moon className="mr-2 h-5 w-5" /> : <Sun className="mr-2 h-5 w-5" />}
          Tema
        </Button>
        <Button
          className="h-14 px-6 text-base"
          variant="destructive"
          onClick={async () => {
            await logout();
            navigate("/login");
          }}
        >
          Cerrar sesión
        </Button>
      </div>
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Button key={card.path} className="h-24 text-lg font-semibold" onClick={() => navigate(card.path)}>
            {card.label}
          </Button>
        ))}
      </div>
    </div>
  );
};

export default MainMenu;
