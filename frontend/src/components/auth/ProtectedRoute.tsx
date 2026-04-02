import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/useAuth";

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

  if (allowedRoles && !user.isSuperuser && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
};
