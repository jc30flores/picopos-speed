import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";
import { getMyAttendanceToday } from "@/lib/api";
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
  const [attendanceCheckLoading, setAttendanceCheckLoading] = useState(false);
  const [hasActiveAttendance, setHasActiveAttendance] = useState(true);

  const isAttendanceBypassUser = Boolean(user?.isSuperuser || user?.role === "admin");
  const shouldCheckAttendance =
    Boolean(user) &&
    !isAttendanceBypassUser &&
    location.pathname !== "/" &&
    location.pathname !== "/login";

  const blockedByAllowedRoles = Boolean(user && allowedRoles && !user.isSuperuser && !allowedRoles.includes(user.role));
  const blockedByPath = Boolean(user && !isRouteAllowed(user.role, location.pathname, user.isSuperuser));
  const blockedByAttendance = Boolean(shouldCheckAttendance && !attendanceCheckLoading && !hasActiveAttendance);
  const isBlocked = blockedByAllowedRoles || blockedByPath || blockedByAttendance;

  useEffect(() => {
    if (!user || !shouldCheckAttendance) {
      setHasActiveAttendance(true);
      setAttendanceCheckLoading(false);
      return;
    }
    let cancelled = false;
    const checkAttendance = async () => {
      setAttendanceCheckLoading(true);
      try {
        const today = await getMyAttendanceToday();
        const active = Boolean(today.clockIn) && !today.clockOut;
        if (cancelled) return;
        setHasActiveAttendance(active);
        console.info("attendance.route_guard.check", {
          userId: user.id,
          role: user.role,
          path: location.pathname,
          clockIn: today.clockIn,
          clockOut: today.clockOut,
          hasActiveAttendance: active,
        });
      } catch (error) {
        if (cancelled) return;
        setHasActiveAttendance(false);
        console.info("attendance.route_guard.error", {
          userId: user.id,
          role: user.role,
          path: location.pathname,
          error: error instanceof Error ? error.message : String(error),
        });
      } finally {
        if (!cancelled) setAttendanceCheckLoading(false);
      }
    };
    void checkAttendance();
    return () => {
      cancelled = true;
    };
  }, [location.pathname, shouldCheckAttendance, user]);

  useEffect(() => {
    if (!user || !isBlocked) return;
    const key = `${user.role}:${location.pathname}`;
    if (warnedRef.current === key) return;
    warnedRef.current = key;
    toast.error(blockedByAttendance ? "Debes marcar Entrada antes de continuar." : deniedMessage);
  }, [blockedByAttendance, deniedMessage, isBlocked, location.pathname, user]);

  if (loading || attendanceCheckLoading) {
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
    });
    return <Navigate to={deniedRedirectTo || getLandingRouteForRole(user.role, user.isSuperuser)} replace />;
  }

  return children;
};
