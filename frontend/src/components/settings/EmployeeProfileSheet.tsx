import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, AlertCircle } from "lucide-react";
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

          {/* Métricas del mes */}
          <div>
            <h3 className="font-semibold mb-3">Métricas del mes actual</h3>
            <div className="grid grid-cols-1 gap-3">
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Calendar className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Días trabajados</p>
                      <p className="text-xl font-bold">{employee.daysWorked}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Clock className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Horas trabajadas</p>
                      <p className="text-xl font-bold">{employee.hoursWorked}h</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-destructive/10">
                      <AlertCircle className="h-4 w-4 text-destructive" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Llegadas tarde</p>
                      <p className="text-xl font-bold">{employee.lateArrivals}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Button className="w-full" variant="outline">
            Ver asistencia detallada
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
};
