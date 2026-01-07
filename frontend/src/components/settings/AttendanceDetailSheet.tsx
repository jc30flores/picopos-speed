import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Calendar, Clock, AlertCircle, Plus } from "lucide-react";
import { AttendanceRecord, DailyAttendance } from "@/types/employee";
import { toast } from "sonner";

interface AttendanceDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  record: AttendanceRecord | null;
  month: string;
  dailyRecords: DailyAttendance[];
  onSaveEntry: (payload: { date: string; entryTime: string; exitTime: string; notes?: string }) => Promise<void>;
}

export const AttendanceDetailSheet = ({
  open,
  onOpenChange,
  record,
  month,
  dailyRecords,
  onSaveEntry,
}: AttendanceDetailSheetProps) => {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    date: "",
    entryTime: "",
    exitTime: "",
    notes: "",
  });

  if (!record) return null;

  const handleSaveManualEntry = async () => {
    if (!formData.date || !formData.entryTime || !formData.exitTime) {
      toast.error("Por favor completa todos los campos obligatorios");
      return;
    }
    try {
      await onSaveEntry({
        date: formData.date,
        entryTime: formData.entryTime,
        exitTime: formData.exitTime,
        notes: formData.notes,
      });
      toast.success("Jornada registrada correctamente");
      setShowForm(false);
      setFormData({ date: "", entryTime: "", exitTime: "", notes: "" });
    } catch (error) {
      console.error("Failed to save attendance entry", error);
      toast.error("No se pudo registrar la jornada");
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            Detalle de asistencia - {record.employeeName}
          </SheetTitle>
          <p className="text-sm text-muted-foreground">
            {new Date(month + "-01").toLocaleDateString("es-ES", {
              month: "long",
              year: "numeric",
            })}
          </p>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Resumen */}
          <div className="grid grid-cols-3 gap-3">
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-col items-center text-center">
                  <Calendar className="h-5 w-5 text-primary mb-2" />
                  <p className="text-xs text-muted-foreground">Días trabajados</p>
                  <p className="text-2xl font-bold">{record.daysWorked}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex flex-col items-center text-center">
                  <Clock className="h-5 w-5 text-primary mb-2" />
                  <p className="text-xs text-muted-foreground">Horas totales</p>
                  <p className="text-2xl font-bold">{record.hoursWorked}h</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex flex-col items-center text-center">
                  <AlertCircle className="h-5 w-5 text-destructive mb-2" />
                  <p className="text-xs text-muted-foreground">Llegadas tarde</p>
                  <p className="text-2xl font-bold">{record.lateArrivals}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Botón para registrar jornada manual */}
          {!showForm && (
            <Button variant="outline" className="w-full" onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Registrar jornada manualmente
            </Button>
          )}

          {/* Formulario de registro manual */}
          {showForm && (
            <Card>
              <CardContent className="p-4 space-y-4">
                <h4 className="font-semibold">Nueva jornada manual</h4>
                <div className="grid gap-3">
                  <div>
                    <Label htmlFor="date">Fecha *</Label>
                    <Input
                      id="date"
                      type="date"
                      value={formData.date}
                      onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label htmlFor="entry">Hora de entrada *</Label>
                      <Input
                        id="entry"
                        type="time"
                        value={formData.entryTime}
                        onChange={(e) => setFormData({ ...formData, entryTime: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="exit">Hora de salida *</Label>
                      <Input
                        id="exit"
                        type="time"
                        value={formData.exitTime}
                        onChange={(e) => setFormData({ ...formData, exitTime: e.target.value })}
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="notes">Comentario</Label>
                    <Textarea
                      id="notes"
                      value={formData.notes}
                      onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                      rows={2}
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleSaveManualEntry} className="flex-1">
                    Guardar
                  </Button>
                  <Button variant="outline" onClick={() => setShowForm(false)} className="flex-1">
                    Cancelar
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Timeline de asistencia diaria */}
          <div>
            <h4 className="font-semibold mb-3">Registro diario</h4>
            <div className="space-y-2">
              {dailyRecords.length === 0 ? (
                <Card>
                  <CardContent className="p-4 text-sm text-muted-foreground text-center">
                    No hay registros de asistencia para este periodo.
                  </CardContent>
                </Card>
              ) : (
                dailyRecords.map((day) => (
                  <Card key={day.date}>
                    <CardContent className="p-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex-1">
                          <p className="font-medium text-sm">
                            {new Date(day.date).toLocaleDateString("es-ES", {
                              weekday: "long",
                              day: "numeric",
                              month: "short",
                            })}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {day.entryTime} - {day.exitTime} ({day.hoursWorked.toFixed(2)}h)
                          </p>
                          {day.notes && (
                            <p className="text-xs text-destructive mt-1">{day.notes}</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};
