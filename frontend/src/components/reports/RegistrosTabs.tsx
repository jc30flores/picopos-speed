import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";
import { useEffect, useState } from "react";
import { getDteSettings } from "@/lib/api";

export const RegistrosTabs = () => {
  const location = useLocation();
  const { user } = useAuth();
  const [dteEnabled, setDteEnabled] = useState(false);
  const isSuperadmin = Boolean(user?.permissions?.isSuperadmin || user?.role === "superadmin");
  const isAdminLike = user?.role === "admin" || user?.role === "superadmin";
  const canViewCash = isAdminLike;
  const canViewReports = isAdminLike;
  useEffect(() => {
    if (!isSuperadmin) {
      setDteEnabled(false);
      return;
    }
    getDteSettings().then((settings) => setDteEnabled(settings.haciendaEnabled)).catch(() => setDteEnabled(false));
  }, [isSuperadmin]);
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      {canViewReports ? (
        <Button asChild variant={location.pathname === "/registros/reportes" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/reportes">Resumen</Link>
        </Button>
      ) : null}
      <Button asChild variant={location.pathname === "/registros/ventas" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
        <Link to="/registros/ventas">Transacciones</Link>
      </Button>
      {canViewCash ? (
        <Button asChild variant={location.pathname === "/registros/caja" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/caja">Caja</Link>
        </Button>
      ) : null}
      {isSuperadmin && canViewReports && dteEnabled ? (
        <Button asChild variant={location.pathname === "/registros/dte" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/dte">DTE</Link>
        </Button>
      ) : null}
      {canViewReports ? (
        <Button asChild variant={location.pathname === "/registros/empleados" ? "default" : "outline"} className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
          <Link to="/registros/empleados">Empleados</Link>
        </Button>
      ) : null}
    </div>
  );
};
