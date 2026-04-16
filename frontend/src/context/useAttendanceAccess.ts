import { useContext } from "react";
import { AttendanceAccessContext } from "./attendanceAccessContext";

export const useAttendanceAccess = () => {
  const context = useContext(AttendanceAccessContext);
  if (!context) {
    throw new Error("useAttendanceAccess must be used within AttendanceAccessProvider");
  }
  return context;
};
