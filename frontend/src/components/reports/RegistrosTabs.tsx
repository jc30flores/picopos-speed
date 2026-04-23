import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";

export const RegistrosTabs = () => {
  const location = useLocation();
  const { user } = useAuth();
  const canViewCash = user?.role === "admin";
  const canViewReports = user?.role === "admin";
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      {canViewReports ? (
        <Button asChild variant={location.pathname === "/registros/reportes" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/reportes">Resumen</Link>
        </Button>
      ) : null}
      <Button asChild variant={location.pathname === "/registros/ventas" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
        <Link to="/registros/ventas">Ventas</Link>
      </Button>
      {canViewCash ? (
        <Button asChild variant={location.pathname === "/registros/caja" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/caja">Caja</Link>
        </Button>
      ) : null}
    </div>
  );
};
