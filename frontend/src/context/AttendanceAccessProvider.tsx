import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  const [attendanceResolved, setAttendanceResolved] = useState(false);
  const [attendanceError, setAttendanceError] = useState<string | null>(null);
  const refreshSeqRef = useRef(0);
  const lastUserIdRef = useRef<number | null>(null);

  const bypassAttendance = Boolean(user?.isSuperuser || user?.role === "admin");

  const refreshAttendance = useCallback(
    async (reason = "manual") => {
      const seq = ++refreshSeqRef.current;
      if (!user || bypassAttendance) {
        setAttendance(null);
        setAttendanceError(null);
        setAttendanceLoading(false);
        setAttendanceResolved(true);
        attendanceLog("refresh_skipped", { reason, userId: user?.id ?? null, bypassAttendance });
        return;
      }

      setAttendanceLoading(true);
      setAttendanceResolved(false);
      try {
        const next = await getMyAttendanceToday();
        if (seq !== refreshSeqRef.current) return;
        setAttendance(next);
        setAttendanceError(null);
        setAttendanceResolved(true);
        attendanceLog("today_response", {
          reason,
          userId: user.id,
          clockIn: next.clockIn,
          clockOut: next.clockOut,
          hasActiveSession: next.hasActiveSession,
          totalEntriesToday: next.totalEntriesToday,
          totalExitsToday: next.totalExitsToday,
          payload: next,
        });
      } catch (error) {
        if (seq !== refreshSeqRef.current) return;
        const message = error instanceof Error ? error.message : "No se pudo validar asistencia";
        setAttendanceError(message);
        setAttendance(null);
        setAttendanceResolved(true);
        attendanceLog("refresh_error", {
          reason,
          userId: user.id,
          error: message,
        });
      } finally {
        if (seq !== refreshSeqRef.current) return;
        setAttendanceLoading(false);
      }
    },
    [bypassAttendance, user],
  );

  const applyAttendanceState = useCallback(
    (next: AttendanceState, reason: string) => {
      setAttendance(next);
      setAttendanceError(null);
      setAttendanceResolved(true);
      attendanceLog("state_transition", {
        reason,
        userId: user?.id ?? null,
        clockIn: next.clockIn,
        clockOut: next.clockOut,
        hasActiveSession: next.hasActiveSession,
        totalEntriesToday: next.totalEntriesToday,
        totalExitsToday: next.totalExitsToday,
        payload: next,
      });
    },
    [user?.id],
  );

  useEffect(() => {
    const currentUserId = user?.id ?? null;
    if (lastUserIdRef.current !== currentUserId) {
      lastUserIdRef.current = currentUserId;
      refreshSeqRef.current += 1;
      setAttendance(null);
      setAttendanceError(null);
      setAttendanceLoading(false);
      setAttendanceResolved(Boolean(!user || bypassAttendance));
      attendanceLog("user_changed_reset", { userId: currentUserId, bypassAttendance });
    }
    void refreshAttendance("user_change");
  }, [bypassAttendance, refreshAttendance, user]);

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
      attendanceResolved,
      attendanceError,
      accessState,
      refreshAttendance,
      applyAttendanceState,
    }),
    [attendance, attendanceLoading, attendanceResolved, attendanceError, accessState, refreshAttendance, applyAttendanceState],
  );

  return <AttendanceAccessContext.Provider value={value}>{children}</AttendanceAccessContext.Provider>;
};
