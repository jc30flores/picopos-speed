import type { AttendanceState } from "@/lib/api";

export type AttendanceBlockReason = "MISSING_CLOCK_IN" | "CLOCKED_OUT" | "ERROR" | "NONE";

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
  const canAccessDashboard = hasClockInToday && !hasClockOutToday;

  if (options?.hasError) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "ERROR",
    };
  }

  if (!hasClockInToday) {
    return {
      hasClockInToday,
      hasClockOutToday,
      canAccessDashboard: false,
      blockReason: "MISSING_CLOCK_IN",
    };
  }

  if (hasClockOutToday) {
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
