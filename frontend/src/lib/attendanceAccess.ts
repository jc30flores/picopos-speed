import type { AttendanceState } from "@/lib/api";

export type AttendanceBlockReason = "MISSING_CLOCK_IN" | "CLOCKED_OUT" | "ON_BREAK" | "ERROR" | "NONE";

export type AttendanceAccessState = {
  hasClockInToday: boolean;
  hasClockOutToday: boolean;
  canAccessDashboard: boolean;
  blockReason: AttendanceBlockReason;
};

export const getAttendanceAccessState = (
  attendance: AttendanceState | null,
  options?: { bypassAttendance?: boolean; hasError?: boolean },
): AttendanceAccessState => {
  if (options?.bypassAttendance) {
    return {
      hasClockInToday: true,
      hasClockOutToday: false,
      canAccessDashboard: true,
      blockReason: "NONE",
    };
  }

  const hasClockInToday = Boolean(attendance?.clockIn);
  const hasClockOutToday = Boolean(attendance?.clockOut);
  const hasActiveSession = Boolean(attendance?.hasActiveSession);
  const isOnBreak = attendance?.state === "ON_BREAK";
  const canAccessDashboard = Boolean(attendance?.accessAllowed) && !isOnBreak;

  if (options?.hasError) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "ERROR",
    };
  }

  if (isOnBreak) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "ON_BREAK",
    };
  }

  if (!hasActiveSession && !hasClockInToday) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "MISSING_CLOCK_IN",
    };
  }

  if (!hasActiveSession && hasClockOutToday) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "CLOCKED_OUT",
    };
  }

  return {
    hasClockInToday,
    hasClockOutToday,
    canAccessDashboard: true,
    blockReason: "NONE",
  };
};
