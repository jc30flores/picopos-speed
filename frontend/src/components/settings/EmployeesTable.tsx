import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { KeyRound, Pencil, Power, Eye } from "lucide-react";
import { Employee } from "@/types/employee";
import { toast } from "sonner";

interface EmployeesTableProps {
  employees: Employee[];
  isLoading?: boolean;
  onEdit: (employee: Employee) => void;
  onToggleStatus: (employee: Employee) => void;
  onResetPassword: (employee: Employee, password: string) => void;
  onViewProfile: (employee: Employee) => void;
}

export const EmployeesTable = ({
  employees,
  isLoading = false,
  onEdit,
  onToggleStatus,
  onResetPassword,
  onViewProfile,
}: EmployeesTableProps) => {
  const handleToggleStatus = (employee: Employee) => {
    const action = employee.status === "active" ? "desactivar" : "activar";
    if (confirm(`¿Estás seguro de ${action} a ${employee.name}?`)) {
      onToggleStatus(employee);
      toast.success("Estado actualizado");
    }
  };

  const handleResetPassword = (employee: Employee) => {
    const password = prompt(`Nueva contraseña para ${employee.name}`);
    if (!password) return;
    onResetPassword(employee, password);
  };

  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead className="hidden sm:table-cell">Puesto</TableHead>
            <TableHead className="hidden md:table-cell">Usuario</TableHead>
            <TableHead className="hidden lg:table-cell">Rol del sistema</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                Cargando empleados...
              </TableCell>
            </TableRow>
          ) : employees.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                No hay empleados registrados
              </TableCell>
            </TableRow>
          ) : (
            employees.map((employee) => (
              <TableRow key={employee.id}>
                <TableCell className="font-medium">{employee.name}</TableCell>
                <TableCell className="hidden sm:table-cell">{employee.role}</TableCell>
                <TableCell className="hidden md:table-cell">
                  {employee.hasUser ? "Sí" : "No"}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  {employee.hasUser ? employee.userRole || "—" : "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={employee.status === "active" ? "default" : "secondary"}>
                    {employee.status === "active" ? "Activo" : "Inactivo"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onViewProfile(employee)}
                      title="Ver perfil"
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    {employee.hasUser && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleResetPassword(employee)}
                        title="Resetear contraseña"
                      >
                        <KeyRound className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onEdit(employee)}
                      title="Editar"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleToggleStatus(employee)}
                      title={employee.status === "active" ? "Desactivar" : "Activar"}
                    >
                      <Power className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
};
