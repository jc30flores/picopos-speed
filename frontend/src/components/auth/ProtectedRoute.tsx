import { useEffect, useRef } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";
import { getLandingRouteForRole, isRouteAllowed } from "@/lib/roleAccess";

interface ProtectedRouteProps {
  allowedRoles?: Array<"admin" | "manager" | "cashier" | "kitchen" | "kiosk" | "worker" | "accountant">;
  deniedRedirectTo?: string;
  deniedMessage?: string;
  children: React.ReactElement;
}

export const ProtectedRoute = ({ allowedRoles, deniedRedirectTo, deniedMessage = "Sin permisos", children }: ProtectedRouteProps) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  const warnedRef = useRef<string | null>(null);

  const blockedByAllowedRoles = Boolean(user && allowedRoles && !user.isSuperuser && !allowedRoles.includes(user.role));
  const blockedByPath = Boolean(user && !isRouteAllowed(user.role, location.pathname, user.isSuperuser));
  const isBlocked = blockedByAllowedRoles || blockedByPath;

  useEffect(() => {
    if (!user || !isBlocked) return;
    const key = `${user.role}:${location.pathname}`;
    if (warnedRef.current === key) return;
    warnedRef.current = key;
    toast.error(deniedMessage);
  }, [isBlocked, location.pathname, user]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Cargando...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (isBlocked) {
    return <Navigate to={deniedRedirectTo || getLandingRouteForRole(user.role, user.isSuperuser)} replace />;
  }

  return children;
};
