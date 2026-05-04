import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmployeesTable } from "./EmployeesTable";
import { EmployeeFormDialog, EmployeeFormData } from "./EmployeeFormDialog";
import { EmployeeProfileSheet } from "./EmployeeProfileSheet";
import { Employee } from "@/types/employee";
import { createEmployee, deleteEmployee, getEmployeeAttendanceHistory, getEmployees, updateEmployee, type AttendanceHistoryRow } from "@/lib/api";
import { toast } from "sonner";
import { AttendanceRecordsModal } from "@/components/attendance/AttendanceRecordsModal";

const ROLE_OPTIONS = [
  { value: "all", label: "Todos" },
  { value: "cashier", label: "Cajero" },
  { value: "kitchen", label: "Cocina" },
  { value: "manager", label: "Gerente" },
  { value: "admin", label: "Administrador" },
  { value: "kiosk", label: "Kiosk" },
  { value: "worker", label: "Worker" },
];

export const EmployeesTab = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRole, setSelectedRole] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [attendanceOpen, setAttendanceOpen] = useState(false);
  const [attendanceRows, setAttendanceRows] = useState<AttendanceHistoryRow[]>([]);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceEmployee, setAttendanceEmployee] = useState<Employee | null>(null);
  const [attendanceFilters, setAttendanceFilters] = useState<{ start?: string; end?: string }>({});

  const loadEmployees = async () => {
    try {
      setIsLoading(true);
      const data = await getEmployees({
        search: searchQuery,
        role: selectedRole !== "all" ? selectedRole : undefined,
        status: selectedStatus !== "all" ? selectedStatus : undefined,
      });
      setEmployees(data);
    } catch (error) {
      console.error("Failed to load employees", error);
      toast.error(
        error instanceof Error ? error.message : "No se pudieron cargar los empleados"
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEmployees();
  }, [searchQuery, selectedRole, selectedStatus]);

  const handleOpenDialog = (employee?: Employee) => {
    setEditingEmployee(employee || null);
    setIsDialogOpen(true);
  };

  const handleOpenProfile = (employee: Employee) => {
    setSelectedEmployee(employee);
    setIsProfileOpen(true);
  };

  const handleSaveEmployee = async (employeeData: EmployeeFormData) => {
    const username = employeeData.username ?? "";
    const userPassword = employeeData.userPassword ?? "";
    const userPayload = {
      username,
      password: userPassword,
      role: employeeData.role ?? "",
    };
    try {
      if (editingEmployee) {
        await updateEmployee(editingEmployee.id, {
          name: employeeData.name,
          role: employeeData.role,
          status: employeeData.status,
          createUser: true,
          user: { ...userPayload, password: userPassword || undefined },
        });
      } else {
        await createEmployee({
          name: employeeData.name ?? "",
          role: employeeData.role ?? "",
          status: employeeData.status ?? "active",
          createUser: true,
          user: userPayload,
        });
      }
      await loadEmployees();
    } catch (error) {
      console.error("Failed to save employee", error);
      throw error;
    }
  };

  const handleDeleteEmployee = async (employee: Employee) => {
    try {
      await updateEmployee(employee.id, {
        status: employee.status === "active" ? "inactive" : "active",
      });
      await loadEmployees();
    } catch (error) {
      console.error("Failed to deactivate employee", error);
      toast.error("No se pudo actualizar el estado del empleado");
    }
  };


  const handlePermanentDelete = async (employee: Employee) => {
    const ok = confirm(`Eliminar empleado ${employee.name}? Esta acción no se puede deshacer.`);
    if (!ok) return;
    try {
      const result = await deleteEmployee(employee.id);
      toast.success(result.message || "Empleado eliminado correctamente.");
      await loadEmployees();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo eliminar el empleado");
    }
  };

  const handleResetPassword = async (employee: Employee, pin: string) => {
    try {
      await updateEmployee(employee.id, {
        createUser: true,
        user: {
          username: employee.userUsername ?? employee.email,
          email: employee.userEmail ?? employee.email,
          password: pin,
          role: employee.userRole ?? employee.role,
        },
      });
      toast.success("PIN actualizado");
      await loadEmployees();
    } catch (error) {
      console.error("Failed to reset PIN", error);
      toast.error("No se pudo resetear el PIN");
    }
  };

  const loadAttendance = async (filters: { start?: string; end?: string } = {}) => {
    if (!attendanceEmployee) return;
    setAttendanceFilters(filters);
    setAttendanceLoading(true);
    try {
      const rows = await getEmployeeAttendanceHistory(attendanceEmployee.id, filters);
      setAttendanceRows(rows);
    } catch (error) {
      console.error("Failed to load attendance history", error);
      toast.error("No se pudo cargar asistencia");
    } finally {
      setAttendanceLoading(false);
    }
  };

  const handleOpenAttendance = (employee: Employee) => {
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
    const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10);
    const defaultFilters = { start: monthStart, end: monthEnd };

    setAttendanceEmployee(employee);
    setAttendanceFilters(defaultFilters);
    setAttendanceOpen(true);
    void (async () => {
      setAttendanceLoading(true);
      try {
        const rows = await getEmployeeAttendanceHistory(employee.id, defaultFilters);
        setAttendanceRows(rows);
      } catch (error) {
        console.error("Failed to load attendance history", error);
        toast.error("No se pudo cargar asistencia");
      } finally {
        setAttendanceLoading(false);
      }
    })();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar empleado..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select value={selectedRole} onValueChange={setSelectedRole}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLE_OPTIONS.map((role) => (
                <SelectItem key={role.value} value={role.value}>
                  {role.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={selectedStatus} onValueChange={setSelectedStatus}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="active">Activo</SelectItem>
              <SelectItem value="inactive">Inactivo</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => handleOpenDialog()} className="w-full sm:w-auto">
          <Plus className="h-4 w-4" />
          Agregar Empleado
        </Button>
      </div>

      <EmployeesTable
        employees={employees}
        isLoading={isLoading}
        onEdit={handleOpenDialog}
        onToggleStatus={handleDeleteEmployee}
        onResetPassword={handleResetPassword}
        onViewProfile={handleOpenProfile}
        onViewAttendance={handleOpenAttendance}
        onDelete={handlePermanentDelete}
      />

      <EmployeeFormDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        employee={editingEmployee}
        onSave={handleSaveEmployee}
      />

      <EmployeeProfileSheet
        open={isProfileOpen}
        onOpenChange={setIsProfileOpen}
        employee={selectedEmployee}
      />
      <AttendanceRecordsModal
        open={attendanceOpen}
        onOpenChange={setAttendanceOpen}
        rows={attendanceRows}
        loading={attendanceLoading}
        initialStart={attendanceFilters.start}
        initialEnd={attendanceFilters.end}
        onApplyFilters={loadAttendance}
      />
    </div>
  );
};
