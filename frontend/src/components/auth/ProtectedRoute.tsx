import { useEffect, useRef } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { useAttendanceAccess } from "@/context/useAttendanceAccess";
import { toast } from "sonner";
import { getLandingRouteForRole, isRouteAllowed } from "@/lib/roleAccess";

interface ProtectedRouteProps {
  allowedRoles?: Array<"superadmin" | "admin" | "manager" | "cashier" | "kitchen" | "kiosk" | "worker" | "accountant">;
  deniedRedirectTo?: string;
  deniedMessage?: string;
  children: React.ReactElement;
}

export const ProtectedRoute = ({ allowedRoles, deniedRedirectTo, deniedMessage = "Sin permisos", children }: ProtectedRouteProps) => {
  const { user, loading } = useAuth();
  const { attendance, accessState, attendanceLoading, attendanceResolved, attendanceError } = useAttendanceAccess();
  const location = useLocation();
  const warnedRef = useRef<string | null>(null);

  const shouldCheckAttendance = Boolean(user) && location.pathname !== "/" && location.pathname !== "/login";
  const canEvaluateAttendanceGuard = !shouldCheckAttendance || (attendanceResolved && !attendanceLoading);
  const isProductSuperadmin = Boolean(user?.permissions?.isSuperadmin || user?.role === "superadmin");

  const blockedByAllowedRoles = Boolean(user && allowedRoles && !isProductSuperadmin && !allowedRoles.includes(user.role));
  const blockedByPath = Boolean(user && !isRouteAllowed(user.role, location.pathname, isProductSuperadmin));
  const blockedByAttendance = Boolean(shouldCheckAttendance && canEvaluateAttendanceGuard && !accessState.canAccessDashboard);
  const isBlocked = blockedByAllowedRoles || blockedByPath || blockedByAttendance;

  useEffect(() => {
    if (!user || !isBlocked) return;
    const key = `${user.role}:${location.pathname}:${accessState.blockReason}`;
    if (warnedRef.current === key) return;
    warnedRef.current = key;

    if (blockedByAttendance) {
      if (attendanceError) {
        toast.error(`No se pudo validar asistencia: ${attendanceError}`);
      } else if (accessState.blockReason === "ON_BREAK") {
        toast.error("No puedes acceder mientras estás en break. Marca regreso de break para continuar.");
      } else if (accessState.blockReason === "CLOCKED_OUT") {
        toast.error("Tu jornada ya fue cerrada. Debes marcar Entrada en un nuevo turno.");
      } else {
        toast.error("Debes marcar Entrada antes de continuar.");
      }
      return;
    }

    toast.error(deniedMessage);
  }, [accessState.blockReason, attendanceError, blockedByAttendance, deniedMessage, isBlocked, location.pathname, user]);

  if (loading || (shouldCheckAttendance && !canEvaluateAttendanceGuard)) {
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
    console.info("attendance.route_guard.blocked", {
      userId: user.id,
      role: user.role,
      path: location.pathname,
      blockedByAllowedRoles,
      blockedByPath,
      blockedByAttendance,
      canEvaluateAttendanceGuard,
      hasClockInToday: accessState.hasClockInToday,
      hasClockOutToday: accessState.hasClockOutToday,
      hasActiveSession: attendance?.hasActiveSession ?? false,
      canAccessDashboard: accessState.canAccessDashboard,
      attendanceError,
    });
    return <Navigate to={deniedRedirectTo || getLandingRouteForRole(user.role, isProductSuperadmin)} replace />;
  }

  return children;
};
