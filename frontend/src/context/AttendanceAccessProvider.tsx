import { useCallback, useEffect, useMemo, useState } from "react";
import { getMyAttendanceToday, type AttendanceState } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { AttendanceAccessContext } from "./attendanceAccessContext";
import { getAttendanceAccessState } from "@/lib/attendanceAccess";

const attendanceLog = (event: string, payload: Record<string, unknown>) => {
  console.info(`attendance.access.${event}`, payload);
};

export const AttendanceAccessProvider = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  const [attendance, setAttendance] = useState<AttendanceState | null>(null);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceError, setAttendanceError] = useState<string | null>(null);

  const bypassAttendance = Boolean(user?.isSuperuser || user?.role === "admin");

  const refreshAttendance = useCallback(
    async (reason = "manual") => {
      if (!user || bypassAttendance) {
        setAttendance(null);
        setAttendanceError(null);
        setAttendanceLoading(false);
        attendanceLog("refresh_skipped", { reason, userId: user?.id ?? null, bypassAttendance });
        return;
      }

      setAttendanceLoading(true);
      try {
        const next = await getMyAttendanceToday();
        setAttendance(next);
        setAttendanceError(null);
        attendanceLog("today_response", {
          reason,
          userId: user.id,
          clockIn: next.clockIn,
          clockOut: next.clockOut,
          hasActiveSession: next.hasActiveSession,
          payload: next,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "No se pudo validar asistencia";
        setAttendanceError(message);
        setAttendance(null);
        attendanceLog("refresh_error", {
          reason,
          userId: user.id,
          error: message,
        });
      } finally {
        setAttendanceLoading(false);
      }
    },
    [bypassAttendance, user],
  );

  const applyAttendanceState = useCallback(
    (next: AttendanceState, reason: string) => {
      setAttendance(next);
      setAttendanceError(null);
      attendanceLog("state_transition", {
        reason,
        userId: user?.id ?? null,
        clockIn: next.clockIn,
        clockOut: next.clockOut,
        hasActiveSession: next.hasActiveSession,
        payload: next,
      });
    },
    [user?.id],
  );

  useEffect(() => {
    void refreshAttendance("user_change");
  }, [refreshAttendance]);

  const accessState = useMemo(() => {
    const next = getAttendanceAccessState(attendance, {
      bypassAttendance,
      hasError: Boolean(attendanceError),
    });
    attendanceLog("access_evaluated", {
      userId: user?.id ?? null,
      hasClockInToday: next.hasClockInToday,
      hasClockOutToday: next.hasClockOutToday,
      hasActiveSession: attendance?.hasActiveSession ?? false,
      canAccessDashboard: next.canAccessDashboard,
      blockReason: next.blockReason,
    });
    return next;
  }, [attendance, attendanceError, bypassAttendance, user?.id]);

  const value = useMemo(
    () => ({
      attendance,
      attendanceLoading,
      attendanceError,
      accessState,
      refreshAttendance,
      applyAttendanceState,
    }),
    [attendance, attendanceLoading, attendanceError, accessState, refreshAttendance, applyAttendanceState],
  );

  return <AttendanceAccessContext.Provider value={value}>{children}</AttendanceAccessContext.Provider>;
};
