import { useEffect, useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Clock, Calendar, AlertCircle, Users } from "lucide-react";
import { AttendanceTable } from "./AttendanceTable";
import { AttendanceDetailSheet } from "./AttendanceDetailSheet";
import { AttendanceRecord, DailyAttendance, Employee } from "@/types/employee";
import { createAttendance, getAttendance, getEmployeeStats, getEmployees } from "@/lib/api";
import { getLocalDateSV } from "@/lib/datetime";
import { toast } from "sonner";

export const AttendanceTab = () => {
  const [selectedMonth, setSelectedMonth] = useState("2025-11");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [selectedEmployee, setSelectedEmployee] = useState("all");
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [attendanceRows, setAttendanceRows] = useState<AttendanceRecord[]>([]);
  const [dailyRecords, setDailyRecords] = useState<DailyAttendance[]>([]);
  const [stats, setStats] = useState({
    totalHours: 0,
    avgDays: "0.0",
    totalLate: 0,
    activeEmployees: 0,
  });

  const handleViewDetail = (record: AttendanceRecord) => {
    setSelectedRecord(record);
    setIsDetailOpen(true);
  };

  const monthRange = useMemo(() => {
    const [year, month] = selectedMonth.split("-").map(Number);
    const start = new Date(year, month - 1, 1);
    const end = new Date(year, month, 0);
    return {
      start: getLocalDateSV(start),
      end: getLocalDateSV(end),
    };
  }, [selectedMonth]);

  const loadEmployees = async () => {
    try {
      const data = await getEmployees();
      setEmployees(data);
    } catch (error) {
      console.error("Failed to load employees", error);
      toast.error("No se pudieron cargar los empleados");
    }
  };

  const loadAttendance = async () => {
    try {
      const data = await getAttendance({
        dateFrom: monthRange.start,
        dateTo: monthRange.end,
        employeeId: selectedEmployee !== "all" ? selectedEmployee : undefined,
      });
      const aggregated = aggregateAttendance(data, employees);
      setAttendanceRows(aggregated);
      const totalHours = aggregated.reduce((sum, row) => sum + row.hoursWorked, 0);
      const avgDays =
        aggregated.length > 0
          ? (aggregated.reduce((sum, row) => sum + row.daysWorked, 0) / aggregated.length).toFixed(1)
          : "0.0";
      const totalLate = aggregated.reduce((sum, row) => sum + row.lateArrivals, 0);
      setStats((prev) => ({
        ...prev,
        totalHours,
        avgDays,
        totalLate,
      }));
    } catch (error) {
      console.error("Failed to load attendance", error);
      toast.error("No se pudo cargar la asistencia");
    }
  };

  const loadStats = async () => {
    try {
      const data = await getEmployeeStats();
      setStats((prev) => ({
        ...prev,
        activeEmployees: data.activeEmployees,
      }));
    } catch (error) {
      console.error("Failed to load employee stats", error);
    }
  };

  useEffect(() => {
    loadEmployees();
    loadStats();
  }, []);

  useEffect(() => {
    if (employees.length) {
      loadAttendance();
    }
  }, [employees, monthRange.start, monthRange.end, selectedEmployee]);

  useEffect(() => {
    if (selectedRecord) {
      getAttendance({
        dateFrom: monthRange.start,
        dateTo: monthRange.end,
        employeeId: selectedRecord.employeeId,
      })
        .then((data) => {
          setDailyRecords(
            data.map((record) => ({
              date: record.date,
              entryTime: record.checkIn ? record.checkIn.slice(11, 16) : "--:--",
              exitTime: record.checkOut ? record.checkOut.slice(11, 16) : "--:--",
              hoursWorked: computeHoursWorked(record.checkIn, record.checkOut),
              notes: record.notes,
            }))
          );
        })
        .catch((error) => {
          console.error("Failed to load daily attendance", error);
          setDailyRecords([]);
        });
    }
  }, [selectedRecord, monthRange.start, monthRange.end]);

  const filteredAttendance = attendanceRows.filter((row) => {
    if (selectedBranch === "all") return true;
    const employee = employees.find((emp) => emp.id === row.employeeId);
    return employee?.branch === selectedBranch;
  });

  const handleSaveManualEntry = async (payload: {
    date: string;
    entryTime: string;
    exitTime: string;
    notes?: string;
  }) => {
    if (!selectedRecord) return;
    await createAttendance({
      employeeId: selectedRecord.employeeId,
      date: payload.date,
      entryTime: payload.entryTime,
      exitTime: payload.exitTime,
      notes: payload.notes,
    });
    await loadAttendance();
    const data = await getAttendance({
      dateFrom: monthRange.start,
      dateTo: monthRange.end,
      employeeId: selectedRecord.employeeId,
    });
    setDailyRecords(
      data.map((record) => ({
        date: record.date,
        entryTime: record.checkIn ? record.checkIn.slice(11, 16) : "--:--",
        exitTime: record.checkOut ? record.checkOut.slice(11, 16) : "--:--",
        hoursWorked: computeHoursWorked(record.checkIn, record.checkOut),
        notes: record.notes,
      }))
    );
  };

  return (
    <div className="space-y-6">
      {/* Filtros */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Select value={selectedMonth} onValueChange={setSelectedMonth}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="2025-11">Noviembre 2025</SelectItem>
            <SelectItem value="2025-10">Octubre 2025</SelectItem>
            <SelectItem value="2025-09">Septiembre 2025</SelectItem>
          </SelectContent>
        </Select>

        <Select value={selectedBranch} onValueChange={setSelectedBranch}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas</SelectItem>
            {Array.from(new Set(employees.map((employee) => employee.branch).filter(Boolean))).map(
              (branch) => (
                <SelectItem key={branch} value={branch}>
                  {branch}
                </SelectItem>
              )
            )}
          </SelectContent>
        </Select>

        <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los empleados</SelectItem>
            {employees.map((employee) => (
              <SelectItem key={employee.id} value={employee.id}>
                {employee.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Clock className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Horas totales</p>
                <p className="text-2xl font-bold">{stats.totalHours}h</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Calendar className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Días promedio</p>
                <p className="text-2xl font-bold">{stats.avgDays}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-destructive/10">
                <AlertCircle className="h-5 w-5 text-destructive" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Llegadas tarde</p>
                <p className="text-2xl font-bold">{stats.totalLate}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Users className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Empleados activos</p>
                <p className="text-2xl font-bold">{stats.activeEmployees}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabla de asistencia */}
      <AttendanceTable data={filteredAttendance} onViewDetail={handleViewDetail} />

      {/* Panel de detalle */}
      <AttendanceDetailSheet
        open={isDetailOpen}
        onOpenChange={setIsDetailOpen}
        record={selectedRecord}
        month={selectedMonth}
        dailyRecords={dailyRecords}
        onSaveEntry={handleSaveManualEntry}
      />
    </div>
  );
};

const aggregateAttendance = (
  records: Awaited<ReturnType<typeof getAttendance>>,
  employees: Employee[]
): AttendanceRecord[] => {
  const grouped = new Map<string, AttendanceRecord>();
  const latestDates = new Map<string, number>();
  records.forEach((record) => {
    const existing = grouped.get(record.employeeId);
    const hoursWorked = computeHoursWorked(record.checkIn, record.checkOut);
    const lastEntry = formatEntryLabel(record.date, record.checkIn);
    const lastExit = formatEntryLabel(record.date, record.checkOut);
    const recordDate = new Date(record.date).getTime();

    if (!existing) {
      grouped.set(record.employeeId, {
        employeeId: record.employeeId,
        employeeName: record.employeeName,
        role: record.role,
        daysWorked: 1,
        hoursWorked,
        lastEntry,
        lastExit,
        lateArrivals: record.minutesLate > 0 ? 1 : 0,
      });
      latestDates.set(record.employeeId, recordDate);
    } else {
      existing.daysWorked += 1;
      existing.hoursWorked += hoursWorked;
      existing.lateArrivals += record.minutesLate > 0 ? 1 : 0;
      if (!Number.isNaN(recordDate)) {
        const latestDate = latestDates.get(record.employeeId) ?? 0;
        if (recordDate >= latestDate) {
          existing.lastEntry = lastEntry;
          existing.lastExit = lastExit;
          latestDates.set(record.employeeId, recordDate);
        }
      }
    }
  });

  return Array.from(grouped.values())
    .filter((row) => {
      const employee = employees.find((emp) => emp.id === row.employeeId);
      if (!employee) return true;
      return employee.status === "active";
    })
    .sort((a, b) => a.employeeName.localeCompare(b.employeeName));
};

const computeHoursWorked = (checkIn?: string | null, checkOut?: string | null) => {
  if (!checkIn || !checkOut) return 0;
  const start = new Date(checkIn);
  const end = new Date(checkOut);
  const diffMs = end.getTime() - start.getTime();
  if (Number.isNaN(diffMs) || diffMs <= 0) return 0;
  return Math.round((diffMs / 36e5) * 100) / 100;
};

const formatEntryLabel = (date: string, timestamp?: string | null) => {
  if (!timestamp) return "--:--";
  const time = timestamp.slice(11, 16);
  const entryDate = new Date(date);
  const today = new Date();
  const isToday =
    entryDate.getFullYear() === today.getFullYear() &&
    entryDate.getMonth() === today.getMonth() &&
    entryDate.getDate() === today.getDate();
  if (isToday) {
    return `Hoy ${time}`;
  }
  return `${entryDate.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
  })} ${time}`;
};
