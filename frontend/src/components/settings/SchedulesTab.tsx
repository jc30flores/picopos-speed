import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { SchedulesTable } from "./SchedulesTable";
import { ScheduleFormDialog } from "./ScheduleFormDialog";
import { Schedule } from "@/types/employee";

const mockSchedules: Schedule[] = [
  {
    id: "1",
    employeeName: "Juan Pérez",
    scheduleType: "Fijo",
    days: "L–V",
    entryTime: "08:00",
    exitTime: "17:00",
    allowsOvertime: true,
  },
  {
    id: "2",
    employeeName: "María García",
    scheduleType: "Fijo",
    days: "L–V",
    entryTime: "07:00",
    exitTime: "16:00",
    allowsOvertime: false,
  },
  {
    id: "3",
    employeeName: "Carlos López",
    scheduleType: "Turnos rotativos",
    days: "L, M, X, J, V, S",
    entryTime: "08:00",
    exitTime: "18:00",
    allowsOvertime: true,
  },
];

export const SchedulesTab = () => {
  const [schedules, setSchedules] = useState<Schedule[]>(mockSchedules);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);

  const handleOpenDialog = (schedule?: Schedule) => {
    setEditingSchedule(schedule || null);
    setIsDialogOpen(true);
  };

  const handleSaveSchedule = (scheduleData: Partial<Schedule>) => {
    if (editingSchedule) {
      setSchedules(
        schedules.map((sch) =>
          sch.id === editingSchedule.id ? { ...sch, ...scheduleData } : sch
        )
      );
    } else {
      const newSchedule: Schedule = {
        id: Date.now().toString(),
        ...scheduleData,
      } as Schedule;
      setSchedules([...schedules, newSchedule]);
    }
  };

  const handleDeleteSchedule = (id: string) => {
    setSchedules(schedules.filter((sch) => sch.id !== id));
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
      />
    </div>
  );
};
