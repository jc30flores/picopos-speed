import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMyAttendanceToday, type AttendanceState } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { AttendanceAccessContext } from "./attendanceAccessContext";
import { getAttendanceAccessState } from "@/lib/attendanceAccess";

const ATTENDANCE_DEBUG = String(import.meta.env.VITE_ATTENDANCE_DEBUG ?? "").toLowerCase() === "true";

const attendanceLog = (event: string, payload: Record<string, unknown>) => {
  if (!ATTENDANCE_DEBUG) return;
  console.info(`attendance.access.${event}`, payload);
};

export const AttendanceAccessProvider = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  const [attendance, setAttendance] = useState<AttendanceState | null>(null);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceResolved, setAttendanceResolved] = useState(false);
  const [attendanceError, setAttendanceError] = useState<string | null>(null);
  const refreshSeqRef = useRef(0);
  const refreshInFlightRef = useRef(false);
  const lastUserIdRef = useRef<number | null>(null);
  const loadedForUserIdRef = useRef<number | null>(null);

  const bypassAttendance = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "kitchen");

  const refreshAttendance = useCallback(
    async (reason = "manual") => {
      const seq = ++refreshSeqRef.current;
      if (!user || bypassAttendance) {
        refreshInFlightRef.current = false;
        setAttendance(null);
        setAttendanceError(null);
        setAttendanceLoading(false);
        setAttendanceResolved(true);
        attendanceLog("ATTENDANCE_REFRESH_SKIP", { reason: "no_user_or_bypass", triggerReason: reason, userId: user?.id ?? null, bypassAttendance });
        return;
      }
      if (refreshInFlightRef.current) {
        attendanceLog("ATTENDANCE_REFRESH_SKIP", { reason: "in_flight", triggerReason: reason, userId: user.id });
        return;
      }
      refreshInFlightRef.current = true;

      setAttendanceLoading(true);
      setAttendanceResolved(false);
      attendanceLog("ATTENDANCE_REFRESH_START", { reason, userId: user.id });
      try {
        const next = await getMyAttendanceToday();
        if (seq !== refreshSeqRef.current) return;
        setAttendance(next);
        setAttendanceError(null);
        setAttendanceResolved(true);
        loadedForUserIdRef.current = user.id;
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
        refreshInFlightRef.current = false;
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
      refreshInFlightRef.current = false;
      loadedForUserIdRef.current = null;
      setAttendance(null);
      setAttendanceError(null);
      setAttendanceLoading(false);
      setAttendanceResolved(Boolean(!user || bypassAttendance));
      attendanceLog("user_changed_reset", { userId: currentUserId, bypassAttendance });
    }
    if (!user?.id || bypassAttendance) {
      void refreshAttendance("user_change_skip");
      return;
    }
    if (loadedForUserIdRef.current === user.id) {
      attendanceLog("ATTENDANCE_REFRESH_SKIP", { reason: "already_loaded_for_user", userId: user.id });
      return;
    }
    void refreshAttendance("user_changed");
  }, [bypassAttendance, refreshAttendance, user?.id]);

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
