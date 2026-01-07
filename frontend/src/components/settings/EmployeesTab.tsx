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
import { EmployeeFormDialog } from "./EmployeeFormDialog";
import { EmployeeProfileSheet } from "./EmployeeProfileSheet";
import { Employee } from "@/types/employee";
import { createEmployee, getEmployees, updateEmployee } from "@/lib/api";
import { toast } from "sonner";

export const EmployeesTab = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);

  const loadEmployees = async () => {
    try {
      const data = await getEmployees();
      setEmployees(data);
    } catch (error) {
      console.error("Failed to load employees", error);
      toast.error("No se pudieron cargar los empleados");
    }
  };

  useEffect(() => {
    loadEmployees();
  }, []);

  const branchOptions = useMemo(() => {
    const options = employees.map((employee) => employee.branch).filter(Boolean);
    const unique = Array.from(new Set(options));
    return unique.length ? unique : ["Sucursal Centro", "Sucursal Norte"];
  }, [employees]);

  const filteredEmployees = employees.filter((emp) => {
    const matchesSearch =
      emp.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesBranch = selectedBranch === "all" || emp.branch === selectedBranch;
    return matchesSearch && matchesBranch;
  });

  const handleOpenDialog = (employee?: Employee) => {
    setEditingEmployee(employee || null);
    setIsDialogOpen(true);
  };

  const handleOpenProfile = (employee: Employee) => {
    setSelectedEmployee(employee);
    setIsProfileOpen(true);
  };

  const handleSaveEmployee = async (employeeData: Partial<Employee>) => {
    try {
      if (editingEmployee) {
        await updateEmployee(editingEmployee.id, employeeData);
      } else {
        await createEmployee({
          name: employeeData.name ?? "",
          email: employeeData.email ?? "",
          role: employeeData.role ?? "",
          phone: employeeData.phone ?? "",
          branch: employeeData.branch ?? "",
          status: employeeData.status ?? "active",
        });
      }
      await loadEmployees();
    } catch (error) {
      console.error("Failed to save employee", error);
      toast.error("No se pudo guardar el empleado");
    }
  };

  const handleDeleteEmployee = async (id: string) => {
    try {
      await updateEmployee(id, { status: "inactive" });
      await loadEmployees();
    } catch (error) {
      console.error("Failed to deactivate employee", error);
      toast.error("No se pudo desactivar el empleado");
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
        onEdit={handleOpenDialog}
        onDelete={handleDeleteEmployee}
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
