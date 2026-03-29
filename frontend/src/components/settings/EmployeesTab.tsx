import { useEffect, useMemo, useState } from "react";
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
import { createEmployee, getEmployees, updateEmployee } from "@/lib/api";
import { toast } from "sonner";

const ROLE_OPTIONS = [
  { value: "all", label: "Todos" },
  { value: "cashier", label: "Cajero" },
  { value: "kitchen", label: "Cocinero" },
  { value: "manager", label: "Gerente" },
  { value: "admin", label: "Administrador" },
];

export const EmployeesTab = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [selectedRole, setSelectedRole] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [isLoading, setIsLoading] = useState(false);

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

  const branchOptions = useMemo(() => {
    const options = employees.map((employee) => employee.branch).filter(Boolean);
    const unique = Array.from(new Set(options));
    return unique.length ? unique : ["Sucursal Centro", "Sucursal Norte"];
  }, [employees]);

  const filteredEmployees = employees.filter((emp) => {
    const matchesBranch = selectedBranch === "all" || emp.branch === selectedBranch;
    return matchesBranch;
  });

  const handleOpenDialog = (employee?: Employee) => {
    setEditingEmployee(employee || null);
    setIsDialogOpen(true);
  };

  const handleOpenProfile = (employee: Employee) => {
    setSelectedEmployee(employee);
    setIsProfileOpen(true);
  };

  const handleSaveEmployee = async (employeeData: EmployeeFormData) => {
    const userIdentifier = employeeData.userIdentifier ?? "";
    const userPassword = employeeData.userPassword ?? "";
    const userRole = employeeData.userRole ?? "";
    const createUser = employeeData.createUser ?? false;
    const userPayload = createUser
      ? {
          username: userIdentifier,
          email: userIdentifier.includes("@") ? userIdentifier : "",
          password: userPassword,
          role: userRole,
        }
      : undefined;
    try {
      if (editingEmployee) {
        await updateEmployee(editingEmployee.id, {
          ...employeeData,
          createUser,
          user: userPayload
            ? {
                ...userPayload,
                password: userPassword || undefined,
              }
            : undefined,
        });
      } else {
        await createEmployee({
          name: employeeData.name ?? "",
          email: employeeData.email ?? "",
          role: employeeData.role ?? "",
          phone: employeeData.phone ?? "",
          branch: employeeData.branch ?? "",
          status: employeeData.status ?? "active",
          createUser,
          user: userPayload,
        });
      }
      await loadEmployees();
    } catch (error) {
      console.error("Failed to save employee", error);
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el empleado");
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
          <Select value={selectedBranch} onValueChange={setSelectedBranch}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {branchOptions.map((branch) => (
                <SelectItem key={branch} value={branch}>
                  {branch}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => handleOpenDialog()} className="w-full sm:w-auto">
          <Plus className="h-4 w-4" />
          Agregar Empleado
        </Button>
      </div>

      <EmployeesTable
        employees={filteredEmployees}
        isLoading={isLoading}
        onEdit={handleOpenDialog}
        onToggleStatus={handleDeleteEmployee}
        onResetPassword={handleResetPassword}
        onViewProfile={handleOpenProfile}
      />

      <EmployeeFormDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        employee={editingEmployee}
        onSave={handleSaveEmployee}
        branches={branchOptions}
      />

      <EmployeeProfileSheet
        open={isProfileOpen}
        onOpenChange={setIsProfileOpen}
        employee={selectedEmployee}
      />
    </div>
  );
};
