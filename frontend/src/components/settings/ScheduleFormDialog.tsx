import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Schedule } from "@/types/employee";
import { toast } from "sonner";

interface ScheduleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  schedule: Schedule | null;
  onSave: (data: Partial<Schedule>) => void;
}

const DAYS = [
  { id: "L", label: "L" },
  { id: "M", label: "M" },
  { id: "X", label: "X" },
  { id: "J", label: "J" },
  { id: "V", label: "V" },
  { id: "S", label: "S" },
  { id: "D", label: "D" },
];

export const ScheduleFormDialog = ({
  open,
  onOpenChange,
  schedule,
  onSave,
}: ScheduleFormDialogProps) => {
  const [formData, setFormData] = useState({
    employeeName: "",
    scheduleType: "Fijo" as "Fijo" | "Turnos rotativos",
    selectedDays: [] as string[],
    entryTime: "",
    exitTime: "",
    allowsOvertime: false,
  });

  useEffect(() => {
    if (schedule) {
      setFormData({
        employeeName: schedule.employeeName,
        scheduleType: schedule.scheduleType,
        selectedDays: schedule.days.split(", "),
        entryTime: schedule.entryTime,
        exitTime: schedule.exitTime,
        allowsOvertime: schedule.allowsOvertime,
      });
    } else {
      setFormData({
        employeeName: "",
        scheduleType: "Fijo",
        selectedDays: [],
        entryTime: "",
        exitTime: "",
        allowsOvertime: false,
      });
    }
  }, [schedule, open]);

  const toggleDay = (dayId: string) => {
    setFormData((prev) => ({
      ...prev,
      selectedDays: prev.selectedDays.includes(dayId)
        ? prev.selectedDays.filter((d) => d !== dayId)
        : [...prev.selectedDays, dayId],
    }));
  };

  const handleSubmit = () => {
    if (
      !formData.employeeName ||
      formData.selectedDays.length === 0 ||
      !formData.entryTime ||
      !formData.exitTime
    ) {
      toast.error("Por favor completa todos los campos obligatorios");
      return;
    }

    const data: Partial<Schedule> = {
      employeeName: formData.employeeName,
      scheduleType: formData.scheduleType,
      days: formData.selectedDays.join(", "),
      entryTime: formData.entryTime,
      exitTime: formData.exitTime,
      allowsOvertime: formData.allowsOvertime,
    };

    onSave(data);
    toast.success(
      schedule ? "Horario actualizado correctamente" : "Horario creado correctamente"
    );
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {schedule ? "Editar Horario" : "Nuevo Horario"}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="employee">Empleado *</Label>
            <Input
              id="employee"
              value={formData.employeeName}
              onChange={(e) =>
                setFormData({ ...formData, employeeName: e.target.value })
              }
              placeholder="Nombre del empleado"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="type">Tipo de horario</Label>
            <Select
              value={formData.scheduleType}
              onValueChange={(value: "Fijo" | "Turnos rotativos") =>
                setFormData({ ...formData, scheduleType: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Fijo">Fijo</SelectItem>
                <SelectItem value="Turnos rotativos">Turnos rotativos</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label>Días de la semana *</Label>
            <div className="flex gap-2 flex-wrap">
              {DAYS.map((day) => (
                <Button
                  key={day.id}
                  type="button"
                  variant={
                    formData.selectedDays.includes(day.id) ? "default" : "outline"
                  }
                  size="sm"
                  onClick={() => toggleDay(day.id)}
                  className="w-10"
                >
                  {day.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="entry">Hora de entrada *</Label>
              <Input
                id="entry"
                type="time"
                value={formData.entryTime}
                onChange={(e) =>
                  setFormData({ ...formData, entryTime: e.target.value })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="exit">Hora de salida *</Label>
              <Input
                id="exit"
                type="time"
                value={formData.exitTime}
                onChange={(e) =>
                  setFormData({ ...formData, exitTime: e.target.value })
                }
              />
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="overtime"
              checked={formData.allowsOvertime}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, allowsOvertime: checked as boolean })
              }
            />
            <Label htmlFor="overtime" className="cursor-pointer">
              Permite horas extra
            </Label>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit}>Guardar horario</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
