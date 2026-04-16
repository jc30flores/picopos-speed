import { createContext } from "react";
import type { AttendanceState } from "@/lib/api";
import type { AttendanceAccessState } from "@/lib/attendanceAccess";

export interface AttendanceAccessContextValue {
  attendance: AttendanceState | null;
  attendanceLoading: boolean;
  attendanceError: string | null;
  accessState: AttendanceAccessState;
  refreshAttendance: (reason?: string) => Promise<void>;
  applyAttendanceState: (next: AttendanceState, reason: string) => void;
}

export const AttendanceAccessContext = createContext<AttendanceAccessContextValue | null>(null);
