import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import AccessDenied from "@/pages/AccessDenied";

interface ProtectedRouteProps {
  allowedRoles?: Array<"admin" | "manager" | "cashier" | "kitchen" | "accountant">;
  children: React.ReactElement;
}

export const ProtectedRoute = ({ allowedRoles, children }: ProtectedRouteProps) => {
  const { user, loading } = useAuth();

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

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <AccessDenied />;
  }

  return children;
};
