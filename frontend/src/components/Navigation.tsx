import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Moon, Sun, ChevronDown } from "lucide-react";
import galloLogo from "@/assets/gallo-logo.jpg";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useState, useEffect } from "react";
import { useAuth } from "@/context/useAuth";
import { branchOptions, type BranchOption } from "@/lib/api";

const navItems = [
  { label: "POS", path: "/" },
  { label: "Kiosk", path: "/kiosk" },
  { label: "Cocina", path: "/kitchen" },
  { label: "Pedidos Clientes", path: "/customer-display" },
  { label: "Menú & Descuentos", path: "/menu" },
  { label: "Reportes & Historial", path: "/reports-history" },
  { label: "DTE", path: "/dte" },
  { label: "Configuración", path: "/settings" },
];

export const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("Sucursal Principal");

  useEffect(() => {
    branchOptions().then((list) => {
      setBranches(list);
      const savedId = localStorage.getItem("selected_branch_id");
      const selected = list.find((b) => String(b.id) === savedId) || list[0];
      if (selected) {
        setSelectedBranch(selected.name);
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
                  className={cn(
                    "px-3 lg:px-4 py-2 rounded-lg text-xs lg:text-sm font-medium transition-all duration-200 whitespace-nowrap",
                    location.pathname === item.path
                      ? "bg-primary text-primary-foreground shadow-md"
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

            {/* Branch Selector - Hidden on small screens */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="hidden md:flex gap-2 rounded-lg border border-border">
                  {selectedBranch}
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                {branches.map((branch) => (
                  <DropdownMenuItem key={branch.id} onClick={() => { setSelectedBranch(branch.name); localStorage.setItem("selected_branch_id", String(branch.id)); }}>
                    {branch.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

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
