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
import { KeyRound, Pencil, Power, Eye, Clock3, Trash2 } from "lucide-react";
import { Employee } from "@/types/employee";
import { toast } from "sonner";

interface EmployeesTableProps {
  employees: Employee[];
  isLoading?: boolean;
  onEdit: (employee: Employee) => void;
  onToggleStatus: (employee: Employee) => void;
  onResetPassword: (employee: Employee, pin: string) => void;
  onViewProfile: (employee: Employee) => void;
  onViewAttendance: (employee: Employee) => void;
  onDelete: (employee: Employee) => void;
}

export const EmployeesTable = ({
  employees,
  isLoading = false,
  onEdit,
  onToggleStatus,
  onResetPassword,
  onViewProfile,
  onViewAttendance,
  onDelete,
}: EmployeesTableProps) => {
  const formatRole = (role: string) => role?.toLowerCase() === "worker" ? "Team Member" : role;
  const handleToggleStatus = (employee: Employee) => {
    const action = employee.status === "active" ? "desactivar" : "activar";
    if (confirm(`¿Estás seguro de ${action} a ${employee.name}?`)) {
      onToggleStatus(employee);
      toast.success("Estado actualizado");
    }
  };

  const handleResetPassword = (employee: Employee) => {
    const pin = (prompt(`Nuevo PIN de 6 dígitos para ${employee.name}`) || "").trim();
    if (!pin) return;
    if (!/^\d{6}$/.test(pin)) {
      toast.error("El PIN debe ser numérico y de 6 dígitos");
      return;
    }
    onResetPassword(employee, pin);
  };

  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead className="hidden sm:table-cell">Puesto</TableHead>
                        <TableHead>Estado</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                Cargando empleados...
              </TableCell>
            </TableRow>
          ) : employees.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                No hay empleados registrados
              </TableCell>
            </TableRow>
          ) : (
            employees.map((employee) => (
              <TableRow key={employee.id}>
                <TableCell className="font-medium">{employee.name}</TableCell>
                <TableCell className="hidden sm:table-cell">{formatRole(employee.role)}</TableCell>
                <TableCell className="hidden md:table-cell">
                  
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  
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
                      onClick={() => onViewAttendance(employee)}
                      title="Ver asistencia"
                      className="h-10 w-10"
                    >
                      <Clock3 className="h-4 w-4" />
                    </Button>
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
                        title="Resetear PIN"
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
                    <Button variant="ghost" size="icon" onClick={() => handleToggleStatus(employee)} title={employee.status === "active" ? "Desactivar" : "Activar"}><Power className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" className="text-red-500" onClick={() => onDelete(employee)} title="Eliminar empleado"><Trash2 className="h-4 w-4" /></Button>
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
