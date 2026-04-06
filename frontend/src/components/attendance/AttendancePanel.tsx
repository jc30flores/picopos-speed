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

  const loadHistory = async (filters: { start?: string; end?: string } = {}) => {
    setHistoryLoading(true);
    try { setHistory(await getMyAttendanceHistory(filters)); }
    catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo cargar historial"); }
    finally { setHistoryLoading(false); }
  };

  return (
    <Card className="rounded-2xl border border-emerald-500/30 bg-card/80 p-4 sm:p-5">
      <div className="mb-4">
        <p className="text-sm text-muted-foreground">Marcaje del día</p>
        <p className="text-2xl font-bold">Bienvenido, {state?.employee?.name ?? "—"}</p>
      </div>
      <div className="mb-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div><p className="text-muted-foreground">Entrada</p><p className="font-semibold">{fmtHM(state?.clockIn ?? null)}</p></div>
        <div><p className="text-muted-foreground">Break inicio</p><p className="font-semibold">{fmtHM(state?.breakStart ?? null)}</p></div>
        <div><p className="text-muted-foreground">Break fin</p><p className="font-semibold">{fmtHM(state?.breakEnd ?? null)}</p></div>
        <div><p className="text-muted-foreground">Salida</p><p className="font-semibold">{fmtHM(state?.clockOut ?? null)}</p></div>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Button className="h-14 bg-blue-600 text-white enabled:hover:bg-blue-700 disabled:opacity-35" disabled={loading || !state?.canClockIn} onClick={() => void runAction(actions.clockIn)}>Entrada</Button>
        <Button className="h-14 bg-yellow-500 text-black enabled:hover:bg-yellow-400 disabled:opacity-35" disabled={loading || !state?.canBreakStart} onClick={() => void runAction(actions.breakStart)}>Break inicio</Button>
        <Button className="h-14 bg-emerald-600 text-white enabled:hover:bg-emerald-500 disabled:opacity-35" disabled={loading || !state?.canBreakEnd} onClick={() => void runAction(actions.breakEnd)}>Break fin</Button>
        <Button className="h-14 bg-rose-600 text-white enabled:hover:bg-rose-500 disabled:opacity-35" disabled={loading || !state?.canClockOut} onClick={() => void runAction(actions.clockOut)}>Salida</Button>
      </div>
      <div className="mt-3 flex justify-end">
        <Button variant="ghost" className="h-10 px-4" onClick={() => { setRecordsOpen(true); void loadHistory(); }}>Ver registros</Button>
      </div>
      <AttendanceRecordsModal open={recordsOpen} onOpenChange={setRecordsOpen} rows={history} loading={historyLoading} onApplyFilters={loadHistory} />
    </Card>
  );
};
