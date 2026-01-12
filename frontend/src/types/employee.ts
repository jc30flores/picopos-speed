export interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  phone: string;
  branch: string;
  status: "active" | "inactive";
  hasUser: boolean;
  userId?: string | null;
  userUsername?: string;
  userEmail?: string;
  userRole?: string;
  daysWorked: number;
  hoursWorked: number;
  lateArrivals: number;
}

export interface AttendanceRecord {
  employeeId: string;
  employeeName: string;
  role: string;
  daysWorked: number;
  hoursWorked: number;
  lastEntry: string;
  lastExit: string;
  lateArrivals: number;
}

export interface DailyAttendance {
  date: string;
  entryTime: string;
  exitTime: string;
  hoursWorked: number;
  notes?: string;
}

export interface Schedule {
  id: string;
  employeeName: string;
  scheduleType: "Fijo" | "Turnos rotativos";
  days: string;
  entryTime: string;
  exitTime: string;
  allowsOvertime: boolean;
}
