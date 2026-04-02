import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { ArrowLeft, Home, LogOut, Moon, Sun } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const isHome = location.pathname === "/";

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <nav className="sticky top-0 z-40 border-b bg-background/95 px-4 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {!isHome ? (
            <Button className="h-12 px-4 text-base" variant="outline" onClick={() => navigate("/")}>
              <ArrowLeft className="mr-2 h-5 w-5" />
              Volver
            </Button>
          ) : null}
          {!isHome ? (
            <Button className="h-12 px-4 text-base" variant="outline" onClick={() => navigate("/")}>
              <Home className="mr-2 h-5 w-5" />
              Menú
            </Button>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Button className="h-12 px-4 text-base" variant="outline" onClick={toggleTheme}>
            {theme === "light" ? <Moon className="mr-2 h-5 w-5" /> : <Sun className="mr-2 h-5 w-5" />}
            Tema
          </Button>
          <Button
            className="h-12 px-4 text-base"
            variant="destructive"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut className="mr-2 h-5 w-5" />
            Salir
          </Button>
        </div>
      </div>
    </nav>
  );
};
