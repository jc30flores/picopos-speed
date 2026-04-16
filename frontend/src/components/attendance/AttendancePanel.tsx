import { useMemo, useState } from "react";
import {
  AttendanceHistoryRow,
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
  const [actionLoading, setActionLoading] = useState<"clockIn" | "clockOut" | null>(null);

  const actions = useMemo(() => ({
    clockIn: async () => {
      const next = await attendanceClockIn();
      applyAttendanceState(next, "clock_in");
    },
    clockOut: async () => {
      const next = await attendanceClockOut();
      applyAttendanceState(next, "clock_out");
    },
  }), [applyAttendanceState]);

  const runAction = async (key: "clockIn" | "clockOut", fn: () => Promise<void>) => {
    if (actionLoading) return;
    setActionLoading(key);
    try {
      await fn();
      toast.success("Marcaje guardado");
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
        <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => { setRecordsOpen(true); void loadHistory(); }}>Ver registros</Button>
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:text-sm">
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Entrada</p><p className="font-semibold">{fmtHM(attendance?.clockIn ?? null)}</p></div>
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Salida</p><p className="font-semibold">{fmtHM(attendance?.clockOut ?? null)}</p></div>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Ciclos hoy: {attendance?.totalEntriesToday ?? 0} entradas / {attendance?.totalExitsToday ?? 0} salidas
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Button
          className="h-12 bg-blue-600 text-white enabled:hover:bg-blue-700 disabled:opacity-35 disabled:saturate-50"
          disabled={attendanceLoading || actionLoading !== null || !attendance?.canClockIn}
          onClick={() => void runAction("clockIn", actions.clockIn)}
        >
          Entrada
        </Button>
        <Button
          className="h-12 bg-rose-600 text-white enabled:hover:bg-rose-500 disabled:opacity-35 disabled:saturate-50"
          disabled={attendanceLoading || actionLoading !== null || !attendance?.canClockOut}
          onClick={() => void runAction("clockOut", actions.clockOut)}
        >
          Salida
        </Button>
      </div>
      <AttendanceRecordsModal open={recordsOpen} onOpenChange={setRecordsOpen} rows={history} loading={historyLoading} onApplyFilters={loadHistory} />
    </Card>
  );
};
