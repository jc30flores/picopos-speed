import { useEffect, useMemo, useState } from "react";
import {
  AttendanceHistoryRow,
  AttendanceState,
  attendanceBreakEnd,
  attendanceBreakStart,
  attendanceClockIn,
  attendanceClockOut,
  getMyAttendanceHistory,
  getMyAttendanceToday,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { AttendanceRecordsModal } from "@/components/attendance/AttendanceRecordsModal";

const fmtHM = (value: string | null) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
};

export const AttendancePanel = () => {
  const [state, setState] = useState<AttendanceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [recordsOpen, setRecordsOpen] = useState(false);
  const [history, setHistory] = useState<AttendanceHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const refreshToday = async () => {
    setLoading(true);
    try {
      setState(await getMyAttendanceToday());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo cargar marcaje");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refreshToday(); }, []);

  const actions = useMemo(() => ({
    clockIn: async () => setState(await attendanceClockIn()),
    breakStart: async () => setState(await attendanceBreakStart()),
    breakEnd: async () => setState(await attendanceBreakEnd()),
    clockOut: async () => setState(await attendanceClockOut()),
  }), []);

  const runAction = async (fn: () => Promise<void>) => {
    try { await fn(); toast.success("Marcaje guardado"); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Acción inválida"); }
  };

  const hasClockIn = Boolean(state?.clockIn);
  const hasClockOut = Boolean(state?.clockOut);
  const hasBreakStart = Boolean(state?.breakStart);
  const hasBreakEnd = Boolean(state?.breakEnd);
  const breakActive = hasBreakStart && !hasBreakEnd;
  const breakDone = hasBreakStart && hasBreakEnd;
  const breakLabel = breakActive ? "Volver" : breakDone ? "Break ✓" : "Break";
  const breakDisabled = loading || !hasClockIn || hasClockOut || breakDone;
  const breakClass = breakDone
    ? "border border-border bg-background text-muted-foreground"
    : breakActive
      ? "bg-emerald-600 text-white enabled:hover:bg-emerald-500"
      : "bg-yellow-500 text-black enabled:hover:bg-yellow-400";

  const breakText = hasBreakStart
    ? `${fmtHM(state?.breakStart ?? null)}${hasBreakEnd ? `–${fmtHM(state?.breakEnd ?? null)}` : "–"}`
    : "—";

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
          <p className="text-xl font-semibold leading-tight">Bienvenido, {state?.employee?.name ?? "—"}</p>
        </div>
        <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => { setRecordsOpen(true); void loadHistory(); }}>Ver registros</Button>
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2 text-xs sm:text-sm">
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Entrada</p><p className="font-semibold">{fmtHM(state?.clockIn ?? null)}</p></div>
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Break</p><p className="font-semibold">{breakText}</p></div>
        <div className="rounded-md border bg-background/50 px-2 py-1.5"><p className="text-muted-foreground">Salida</p><p className="font-semibold">{fmtHM(state?.clockOut ?? null)}</p></div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Button className="h-12 bg-blue-600 text-white enabled:hover:bg-blue-700 disabled:opacity-35 disabled:saturate-50" disabled={loading || !state?.canClockIn} onClick={() => void runAction(actions.clockIn)}>Entrada</Button>
        <Button
          className={`h-12 disabled:opacity-35 disabled:saturate-50 ${breakClass}`}
          disabled={breakDisabled}
          onClick={() => void runAction(breakActive ? actions.breakEnd : actions.breakStart)}
        >
          {breakLabel}
        </Button>
        <Button className="h-12 bg-rose-600 text-white enabled:hover:bg-rose-500 disabled:opacity-35 disabled:saturate-50" disabled={loading || !state?.canClockOut} onClick={() => void runAction(actions.clockOut)}>Salida</Button>
      </div>
      <AttendanceRecordsModal open={recordsOpen} onOpenChange={setRecordsOpen} rows={history} loading={historyLoading} onApplyFilters={loadHistory} />
    </Card>
  );
};
