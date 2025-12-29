import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { SchedulesTable } from "./SchedulesTable";
import { ScheduleFormDialog } from "./ScheduleFormDialog";
import { Schedule, Employee } from "@/types/employee";
import { createSchedule, deleteSchedule, getEmployees, getSchedules } from "@/lib/api";
import { toast } from "sonner";

interface ScheduleGroup extends Schedule {
  scheduleIds: string[];
  dayNumbers: number[];
  employeeId: string;
}

export const SchedulesTab = () => {
  const [schedules, setSchedules] = useState<ScheduleGroup[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<ScheduleGroup | null>(null);

  const loadEmployees = async () => {
    try {
      const data = await getEmployees();
      setEmployees(data);
    } catch (error) {
      console.error("Failed to load employees", error);
      toast.error("No se pudieron cargar los empleados");
    }
  };

  const loadSchedules = async () => {
    try {
      const data = await getSchedules();
      const grouped = groupSchedules(data as Array<Schedule & { employeeId?: string; dayOfWeek?: number }>);
      setSchedules(grouped);
    } catch (error) {
      console.error("Failed to load schedules", error);
      toast.error("No se pudieron cargar los horarios");
    }
  };

  useEffect(() => {
    loadEmployees();
    loadSchedules();
  }, []);

  const handleOpenDialog = (schedule?: ScheduleGroup) => {
    setEditingSchedule(schedule || null);
    setIsDialogOpen(true);
  };

  const handleSaveSchedule = async (scheduleData: Partial<Schedule>) => {
    try {
      const employee = employees.find((emp) => emp.name === scheduleData.employeeName);
      if (!employee) {
        toast.error("Selecciona un empleado válido");
        return;
      }

      const dayNumbers = parseDayNumbers(scheduleData.days || "");
      if (!dayNumbers.length) {
        toast.error("Selecciona al menos un día");
        return;
      }

      if (editingSchedule) {
        await Promise.all(editingSchedule.scheduleIds.map((id) => deleteSchedule(id)));
      }

      await Promise.all(
        dayNumbers.map((day) =>
          createSchedule({
            employeeId: employee.id,
            scheduleType: scheduleData.scheduleType ?? "Fijo",
            dayOfWeek: day,
            entryTime: scheduleData.entryTime ?? "08:00",
            exitTime: scheduleData.exitTime ?? "17:00",
            allowsOvertime: scheduleData.allowsOvertime ?? false,
          })
        )
      );

      await loadSchedules();
    } catch (error) {
      console.error("Failed to save schedule", error);
      toast.error("No se pudo guardar el horario");
    }
  };

  const handleDeleteSchedule = async (id: string) => {
    try {
      const schedule = schedules.find((item) => item.id === id);
      if (!schedule) return;
      await Promise.all(schedule.scheduleIds.map((scheduleId) => deleteSchedule(scheduleId)));
      await loadSchedules();
    } catch (error) {
      console.error("Failed to delete schedule", error);
      toast.error("No se pudo eliminar el horario");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Horarios de trabajo</h2>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="h-4 w-4" />
          Nuevo horario
        </Button>
      </div>

      <SchedulesTable
        schedules={schedules}
        onEdit={handleOpenDialog}
        onDelete={handleDeleteSchedule}
      />

      <ScheduleFormDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        schedule={editingSchedule}
        onSave={handleSaveSchedule}
        employees={employees}
      />
    </div>
  );
};

const groupSchedules = (entries: Array<Schedule & { employeeId?: string; dayOfWeek?: number }>) => {
  const grouped = new Map<string, ScheduleGroup>();

  entries.forEach((entry) => {
    const dayLetter = entry.days;
    const key = `${entry.employeeName}|${entry.scheduleType}|${entry.entryTime}|${entry.exitTime}|${entry.allowsOvertime}`;
    const existing = grouped.get(key);

    if (!existing) {
      grouped.set(key, {
        ...entry,
        scheduleIds: [entry.id],
        dayNumbers: entry.dayOfWeek !== undefined ? [entry.dayOfWeek] : [],
        employeeId: entry.employeeId ?? "",
        days: dayLetter,
      });
    } else {
      existing.scheduleIds.push(entry.id);
      if (entry.dayOfWeek !== undefined) {
        existing.dayNumbers.push(entry.dayOfWeek);
      }
      existing.days = mergeDays(existing.days, dayLetter);
    }
  });

  return Array.from(grouped.values());
};

const mergeDays = (existing: string, next: string) => {
  const days = new Set(existing.split(", ").filter(Boolean));
  next.split(", ").forEach((day) => days.add(day));
  return Array.from(days).join(", ");
};

const parseDayNumbers = (days: string) => {
  const mapping: Record<string, number> = {
    L: 1,
    M: 2,
    X: 3,
    J: 4,
    V: 5,
    S: 6,
    D: 0,
  };
  return days
    .split(",")
    .map((day) => day.trim())
    .filter(Boolean)
    .map((day) => mapping[day])
    .filter((day) => day !== undefined);
};
