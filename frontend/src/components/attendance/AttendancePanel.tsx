import { useMemo, useState } from "react";
import {
  AttendanceHistoryRow,
  attendanceBreakEnd,
  attendanceBreakStart,
  attendanceClockIn,
  attendanceClockOut,
  getMyAttendanceHistory,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { AttendanceRecordsModal } from "@/components/attendance/AttendanceRecordsModal";
import { useAttendanceAccess } from "@/context/useAttendanceAccess";

const fmtHM = (value: string | null) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
};

export const AttendancePanel = () => {
  const { attendance, attendanceLoading, applyAttendanceState } = useAttendanceAccess();
  const [recordsOpen, setRecordsOpen] = useState(false);
  const [history, setHistory] = useState<AttendanceHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<"clockIn" | "break" | "clockOut" | null>(null);
  const showPersonalTimeCard = false;

  const actions = useMemo(() => ({
    clockIn: async () => {
      const next = await attendanceClockIn();
      applyAttendanceState(next, "clock_in");
    },
    clockOut: async () => {
      const next = await attendanceClockOut();
      applyAttendanceState(next, "clock_out");
    },
    breakStart: async () => {
      const next = await attendanceBreakStart();
      applyAttendanceState(next, "break_start");
    },
    breakEnd: async () => {
      const next = await attendanceBreakEnd();
      applyAttendanceState(next, "break_end");
    },
  }), [applyAttendanceState]);

  const runAction = async (
    key: "clockIn" | "break" | "clockOut",
    fn: () => Promise<void>,
    successMessage: string,
  ) => {
    if (actionLoading) return;
    setActionLoading(key);
    try {
      await fn();
      toast.success(successMessage);
    }
    catch (error) {
      toast.error(error instanceof Error ? error.message : "Acción inválida");
    } finally {
      setActionLoading(null);
    }
  };

  const loadHistory = async (filters: { start?: string; end?: string } = {}) => {
    setHistoryLoading(true);
    try { setHistory(await getMyAttendanceHistory(filters)); }
    catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo cargar historial"); }
    finally { setHistoryLoading(false); }
  };

  return (
    <Card className="rounded-xl border border-emerald-500/30 bg-card/80 p-3 sm:p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Marcaje del día</p>
          <p className="text-xl font-semibold leading-tight">Bienvenido, {attendance?.employee?.name ?? "—"}</p>
        </div>
        {showPersonalTimeCard ? <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => { setRecordsOpen(true); void loadHistory(); }}>Ver registros</Button> : null}
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:text-sm">
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Entrada</p><p className="font-semibold">{fmtHM(attendance?.clockIn ?? null)}</p></div>
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Salida</p><p className="font-semibold">{fmtHM(attendance?.clockOut ?? null)}</p></div>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Ciclos hoy: {attendance?.totalEntriesToday ?? 0} entradas / {attendance?.totalExitsToday ?? 0} salidas
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs sm:text-sm">
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Total break</p><p className="font-semibold">{attendance?.activeCycle?.breakMinutes != null ? `${Math.floor(attendance.activeCycle.breakMinutes/60)}h ${String(attendance.activeCycle.breakMinutes%60).padStart(2,"0")}m` : "—"}</p></div>
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Break actual</p><p className="font-semibold">{fmtHM(attendance?.activeCycle?.currentBreakStartedAt ?? null)}</p></div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <Button
          className="h-12 bg-blue-600 text-white enabled:hover:bg-blue-700 disabled:opacity-35 disabled:saturate-50"
          disabled={attendanceLoading || actionLoading !== null || !attendance?.canClockIn}
          onClick={() => void runAction("clockIn", actions.clockIn, "Entrada registrada correctamente.")}
        >
          Entrada
        </Button>
        <Button
          className={`h-12 text-white disabled:opacity-35 disabled:saturate-50 ${
            attendance?.state === "ON_BREAK"
              ? "bg-violet-600 enabled:hover:bg-violet-700"
              : attendance?.state === "WORKING"
                ? "bg-amber-500 enabled:hover:bg-amber-600"
                : "bg-zinc-500"
          }`}
          disabled={attendanceLoading || actionLoading !== null || !(attendance?.canBreakStart || attendance?.canBreakEnd)}
          onClick={() =>
            void runAction(
              "break",
              attendance?.canBreakEnd ? actions.breakEnd : actions.breakStart,
              attendance?.canBreakEnd ? "Regreso de break registrado." : "Salida a break registrada.",
            )
          }
        >
          {attendance?.state === "ON_BREAK"
            ? "Regresar de Break"
            : attendance?.state === "WORKING_AFTER_BREAK"
              ? "Break completado"
              : attendance?.state === "WORKING"
                ? "Salir a Break"
                : "Break"}
        </Button>
        <Button
          className="h-12 bg-rose-600 text-white enabled:hover:bg-rose-500 disabled:opacity-35 disabled:saturate-50"
          disabled={attendanceLoading || actionLoading !== null || !attendance?.canClockOut}
          onClick={() => void runAction("clockOut", actions.clockOut, "Salida registrada correctamente.")}
        >
          Salida
        </Button>
      </div>
      <AttendanceRecordsModal open={recordsOpen} onOpenChange={setRecordsOpen} rows={history} loading={historyLoading} onApplyFilters={loadHistory} />
    </Card>
  );
};
