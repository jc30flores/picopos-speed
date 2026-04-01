import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/useAuth";

export const RegistrosTabs = () => {
  const location = useLocation();
  const { user } = useAuth();
  const canViewCash = user?.role === "admin";
  return (
    <div className="mb-4 flex gap-2">
      <Button asChild variant={location.pathname === "/registros/ventas" ? "default" : "outline"}>
        <Link to="/registros/ventas">Ventas</Link>
      </Button>
      {canViewCash ? (
        <Button asChild variant={location.pathname === "/registros/caja" ? "default" : "outline"}>
          <Link to="/registros/caja">Caja</Link>
        </Button>
      ) : null}
    </div>
  );
};
