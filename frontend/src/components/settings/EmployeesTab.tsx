import { useState } from "react";
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

const mockEmployees: Employee[] = [
  {
    id: "1",
    name: "Juan Pérez",
    email: "juan@example.com",
    role: "Cajero",
    phone: "555-0101",
    branch: "Sucursal Centro",
    status: "active",
    daysWorked: 22,
    hoursWorked: 176,
    lateArrivals: 2,
  },
  {
    id: "2",
    name: "María García",
    email: "maria@example.com",
    role: "Gerente",
    phone: "555-0102",
    branch: "Sucursal Centro",
    status: "active",
    daysWorked: 20,
    hoursWorked: 160,
    lateArrivals: 0,
  },
  {
    id: "3",
    name: "Carlos López",
    email: "carlos@example.com",
    role: "Cocinero",
    phone: "555-0103",
    branch: "Sucursal Norte",
    status: "active",
    daysWorked: 24,
    hoursWorked: 192,
    lateArrivals: 1,
  },
  {
    id: "4",
    name: "Ana Martínez",
    email: "ana@example.com",
    role: "Mesera",
    phone: "555-0104",
    branch: "Sucursal Centro",
    status: "inactive",
    daysWorked: 0,
    hoursWorked: 0,
    lateArrivals: 0,
  },
];

export const EmployeesTab = () => {
  const [employees, setEmployees] = useState<Employee[]>(mockEmployees);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);

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

  const handleSaveEmployee = (employeeData: Partial<Employee>) => {
    if (editingEmployee) {
      setEmployees(
        employees.map((emp) =>
          emp.id === editingEmployee.id ? { ...emp, ...employeeData } : emp
        )
      );
    } else {
      const newEmployee: Employee = {
        id: Date.now().toString(),
        daysWorked: 0,
        hoursWorked: 0,
        lateArrivals: 0,
        status: "active",
        ...employeeData,
      } as Employee;
      setEmployees([...employees, newEmployee]);
    }
  };

  const handleDeleteEmployee = (id: string) => {
    setEmployees(employees.filter((emp) => emp.id !== id));
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
              <SelectItem value="Sucursal Centro">Sucursal Centro</SelectItem>
              <SelectItem value="Sucursal Norte">Sucursal Norte</SelectItem>
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
      />

      <EmployeeProfileSheet
        open={isProfileOpen}
        onOpenChange={setIsProfileOpen}
        employee={selectedEmployee}
      />
    </div>
  );
};
