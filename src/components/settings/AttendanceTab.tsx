import { useState } from "react";
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
import { AttendanceRecord } from "@/types/employee";

const mockAttendanceData: AttendanceRecord[] = [
  {
    employeeId: "1",
    employeeName: "Juan Pérez",
    role: "Cajero",
    daysWorked: 22,
    hoursWorked: 176,
    lastEntry: "Hoy 08:03",
    lastExit: "17:12",
    lateArrivals: 2,
  },
  {
    employeeId: "2",
    employeeName: "María García",
    role: "Gerente",
    daysWorked: 20,
    hoursWorked: 160,
    lastEntry: "Hoy 07:58",
    lastExit: "16:45",
    lateArrivals: 0,
  },
  {
    employeeId: "3",
    employeeName: "Carlos López",
    role: "Cocinero",
    daysWorked: 24,
    hoursWorked: 192,
    lastEntry: "Hoy 08:15",
    lastExit: "18:20",
    lateArrivals: 1,
  },
];

export const AttendanceTab = () => {
  const [selectedMonth, setSelectedMonth] = useState("2025-11");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [selectedEmployee, setSelectedEmployee] = useState("all");
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null);

  const handleViewDetail = (record: AttendanceRecord) => {
    setSelectedRecord(record);
    setIsDetailOpen(true);
  };

  const totalHours = mockAttendanceData.reduce((sum, r) => sum + r.hoursWorked, 0);
  const avgDays = (
    mockAttendanceData.reduce((sum, r) => sum + r.daysWorked, 0) /
    mockAttendanceData.length
  ).toFixed(1);
  const totalLate = mockAttendanceData.reduce((sum, r) => sum + r.lateArrivals, 0);
  const activeEmployees = mockAttendanceData.length;

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
            <SelectItem value="centro">Sucursal Centro</SelectItem>
            <SelectItem value="norte">Sucursal Norte</SelectItem>
          </SelectContent>
        </Select>

        <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los empleados</SelectItem>
            <SelectItem value="1">Juan Pérez</SelectItem>
            <SelectItem value="2">María García</SelectItem>
            <SelectItem value="3">Carlos López</SelectItem>
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
                <p className="text-2xl font-bold">{totalHours}h</p>
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
                <p className="text-2xl font-bold">{avgDays}</p>
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
                <p className="text-2xl font-bold">{totalLate}</p>
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
                <p className="text-2xl font-bold">{activeEmployees}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabla de asistencia */}
      <AttendanceTable data={mockAttendanceData} onViewDetail={handleViewDetail} />

      {/* Panel de detalle */}
      <AttendanceDetailSheet
        open={isDetailOpen}
        onOpenChange={setIsDetailOpen}
        record={selectedRecord}
        month={selectedMonth}
      />
    </div>
  );
};
