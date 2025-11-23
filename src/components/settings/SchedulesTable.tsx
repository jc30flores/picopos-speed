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
import { Pencil, Trash2 } from "lucide-react";
import { Schedule } from "@/types/employee";
import { toast } from "sonner";

interface SchedulesTableProps {
  schedules: Schedule[];
  onEdit: (schedule: Schedule) => void;
  onDelete: (id: string) => void;
}

export const SchedulesTable = ({ schedules, onEdit, onDelete }: SchedulesTableProps) => {
  const handleDelete = (id: string, name: string) => {
    if (confirm(`¿Estás seguro de eliminar el horario de ${name}?`)) {
      onDelete(id);
      toast.success("Horario eliminado correctamente");
    }
  };

  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Empleado</TableHead>
            <TableHead className="hidden sm:table-cell">Tipo</TableHead>
            <TableHead className="hidden md:table-cell">Días</TableHead>
            <TableHead>Horario</TableHead>
            <TableHead className="hidden lg:table-cell">Horas extra</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {schedules.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                No hay horarios configurados
              </TableCell>
            </TableRow>
          ) : (
            schedules.map((schedule) => (
              <TableRow key={schedule.id}>
                <TableCell className="font-medium">{schedule.employeeName}</TableCell>
                <TableCell className="hidden sm:table-cell">
                  <Badge variant="outline">{schedule.scheduleType}</Badge>
                </TableCell>
                <TableCell className="hidden md:table-cell">{schedule.days}</TableCell>
                <TableCell>
                  {schedule.entryTime} - {schedule.exitTime}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  {schedule.allowsOvertime ? "Sí" : "No"}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onEdit(schedule)}
                      title="Editar"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(schedule.id, schedule.employeeName)}
                      title="Eliminar"
                    >
                      <Trash2 className="h-4 w-4" />
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
