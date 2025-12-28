import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Eye } from "lucide-react";
import { AttendanceRecord } from "@/types/employee";

interface AttendanceTableProps {
  data: AttendanceRecord[];
  onViewDetail: (record: AttendanceRecord) => void;
}

export const AttendanceTable = ({ data, onViewDetail }: AttendanceTableProps) => {
  return (
    <>
      {/* Vista de tabla para desktop */}
      <div className="hidden md:block rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Empleado</TableHead>
              <TableHead>Puesto</TableHead>
              <TableHead>Días trabajados</TableHead>
              <TableHead>Horas trabajadas</TableHead>
              <TableHead>Última entrada / salida</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((record) => (
              <TableRow key={record.employeeId}>
                <TableCell className="font-medium">{record.employeeName}</TableCell>
                <TableCell>{record.role}</TableCell>
                <TableCell>{record.daysWorked}</TableCell>
                <TableCell>{record.hoursWorked}h</TableCell>
                <TableCell>
                  {record.lastEntry} / {record.lastExit}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onViewDetail(record)}
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Detalle
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Vista de tarjetas para móvil */}
      <div className="md:hidden space-y-3">
        {data.map((record) => (
          <Card key={record.employeeId}>
            <CardContent className="p-4">
              <div className="space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium">{record.employeeName}</p>
                    <p className="text-sm text-muted-foreground">{record.role}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">Días trabajados</p>
                    <p className="font-medium">{record.daysWorked}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Horas totales</p>
                    <p className="font-medium">{record.hoursWorked}h</p>
                  </div>
                </div>
                <div className="text-sm">
                  <p className="text-muted-foreground">Última entrada / salida</p>
                  <p className="font-medium">
                    {record.lastEntry} / {record.lastExit}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full mt-2"
                  onClick={() => onViewDetail(record)}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  Ver detalle
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
};
