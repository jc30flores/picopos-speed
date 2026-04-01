import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Moon, Sun } from "lucide-react";
import galloLogo from "@/assets/gallo-logo.jpg";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useState, useEffect } from "react";
import { useAuth } from "@/context/useAuth";
import { branchOptions, type BranchOption } from "@/lib/api";
import { allowedNavItemsByRole } from "@/lib/roleAccess";

export const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    branchOptions().then((list) => {
      const savedId = localStorage.getItem("selected_branch_id");
      const selected =
        list.find((b) => String(b.id) === savedId) ||
        list.find((b) => b.is_default || b.is_primary || b.is_default_branch) ||
        list.find((b) => b.code === "PRINCIPAL") ||
        list[0];
      if (selected) {
        localStorage.setItem("selected_branch_id", String(selected.id));
      }
    }).catch(() => undefined);

    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.classList.toggle("dark", savedTheme === "dark");
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    document.documentElement.classList.toggle("dark", newTheme === "dark");
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate("/login");
    }
  };

  const isNavItemActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    if (path.startsWith("/registros")) return location.pathname.startsWith("/registros");
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };
  const navItems = user ? allowedNavItemsByRole[user.role] : [];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-card border-b border-border shadow-sm">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo - Hidden on small screens */}
          <Link to="/" className="hidden lg:flex items-center gap-2 group">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform overflow-hidden">
              <img src={galloLogo} alt="Pico de Gallo" className="w-full h-full object-cover" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-lg leading-tight text-foreground">Pico de Gallo</span>
              <span className="text-xs text-muted-foreground leading-tight">POS</span>
            </div>
          </Link>

          {/* Center Navigation - Always visible, scrollable on small screens */}
          <div className="flex-1 lg:flex-initial overflow-x-auto">
            <div className="flex items-center gap-1 min-w-max lg:min-w-0">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  aria-current={isNavItemActive(item.path) ? "page" : undefined}
                  className={cn(
                    "px-3 lg:px-4 py-2 rounded-lg text-xs lg:text-sm font-medium transition-all duration-200 whitespace-nowrap",
                    isNavItemActive(item.path)
                      ? "bg-primary/90 text-primary-foreground ring-1 ring-primary/60 shadow-[0_0_12px_rgba(34,197,94,0.35)]"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-2 lg:gap-3">
            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="rounded-lg shrink-0"
            >
              {theme === "light" ? (
                <Moon className="h-4 w-4 lg:h-5 lg:w-5" />
              ) : (
                <Sun className="h-4 w-4 lg:h-5 lg:w-5" />
              )}
            </Button>

            <TooltipProvider delayDuration={150}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleLogout}
                    className="rounded-lg shrink-0 text-foreground hover:bg-muted"
                    aria-label="Cerrar sesión"
                  >
                    <LogOut className="h-4 w-4 lg:h-5 lg:w-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Cerrar sesión</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>
    </nav>
  );
};
