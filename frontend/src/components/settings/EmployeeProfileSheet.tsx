import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Employee } from "@/types/employee";

interface EmployeeProfileSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: Employee | null;
}

export const EmployeeProfileSheet = ({
  open,
  onOpenChange,
  employee,
}: EmployeeProfileSheetProps) => {
  if (!employee) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Perfil del empleado</SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Información básica */}
          <div className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">Nombre</p>
              <p className="font-medium">{employee.name}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Puesto</p>
              <p className="font-medium">{employee.role}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Sucursal</p>
              <p className="font-medium">{employee.branch}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Email</p>
              <p className="font-medium">{employee.email}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Teléfono</p>
              <p className="font-medium">{employee.phone}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Estado</p>
              <Badge variant={employee.status === "active" ? "default" : "secondary"}>
                {employee.status === "active" ? "Activo" : "Inactivo"}
              </Badge>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="font-semibold">Acceso al sistema</h3>
            <div>
              <p className="text-sm text-muted-foreground">Usuario</p>
              <p className="font-medium">
                {employee.hasUser ? employee.userUsername || employee.userEmail || "Sí" : "No"}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Rol del sistema</p>
              <p className="font-medium">{employee.hasUser ? employee.userRole || "—" : "—"}</p>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};
