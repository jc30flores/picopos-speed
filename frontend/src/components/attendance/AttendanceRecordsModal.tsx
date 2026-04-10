import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AttendanceHistoryRow } from "@/lib/api";
import { AlertTriangle } from "lucide-react";

const fmtHM = (value: string | null) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
};

const toMinutes = (start: string | null, end: string | null) => {
  if (!start || !end) return 0;
  const startDate = new Date(start);
  const endDate = new Date(end);
  const diff = endDate.getTime() - startDate.getTime();
  if (Number.isNaN(diff) || diff <= 0) return 0;
  return Math.floor(diff / 60000);
};

const fmtDuration = (minutes: number) => {
  if (minutes <= 0) return "0h 00m";
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${String(rem).padStart(2, "0")}m`;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rows: AttendanceHistoryRow[];
  loading?: boolean;
  initialStart?: string;
  initialEnd?: string;
  onApplyFilters: (filters: { start?: string; end?: string }) => Promise<void> | void;
};

export const AttendanceRecordsModal = ({
  open,
  onOpenChange,
  rows,
  loading = false,
  initialStart = "",
  initialEnd = "",
  onApplyFilters,
}: Props) => {
  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setStart(initialStart);
    setEnd(initialEnd);
    setError(null);
  }, [open, initialStart, initialEnd]);

  const sorted = useMemo(() => [...rows].sort((a, b) => b.date.localeCompare(a.date)), [rows]);

  const rowsWithTotals = useMemo(
    () =>
      sorted.map((row) => {
        const grossMinutes = toMinutes(row.clockIn, row.clockOut);
        const breakMinutes = toMinutes(row.breakStart, row.breakEnd);
        const workedMinutes = Math.max(grossMinutes - breakMinutes, 0);
        return {
          ...row,
          workedMinutes,
          breakMinutes,
          finalMinutes: workedMinutes,
        };
      }),
    [sorted]
  );

  const applyFilters = () => {
    if (!start && !end) {
      setError(null);
      void onApplyFilters({});
      return;
    }
    if (!start || !end) {
      setError("Debes seleccionar fecha inicio y fecha fin.");
      return;
    }
    if (end < start) {
      setError("La fecha fin no puede ser menor que la fecha inicio.");
      return;
    }
    setError(null);
    void onApplyFilters({ start, end });
  };

  const clearFilters = () => {
    setStart("");
    setEnd("");
    setError(null);
    void onApplyFilters({});
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl border-border/70 bg-background/95">
        <DialogHeader>
          <DialogTitle>Tarjeta de Horas</DialogTitle>
        </DialogHeader>

        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="Fecha inicio" className="h-11" />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="Fecha fin" className="h-11" />
          <div className="flex gap-2">
            <Button className="h-11" onClick={applyFilters}>Aplicar</Button>
            <Button className="h-11" variant="outline" onClick={clearFilters}>Limpiar</Button>
          </div>
        </div>

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        ) : null}

        <div className="max-h-[420px] overflow-auto rounded-xl border border-border/60">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/70 backdrop-blur-sm">
              <tr className="border-b border-border/70 text-xs uppercase tracking-wide text-muted-foreground">
                <th className="p-2 text-left">Fecha</th>
                <th className="p-2 text-left">Entrada</th>
                <th className="p-2 text-left">Break In</th>
                <th className="p-2 text-left">Break Out</th>
                <th className="p-2 text-left">Salida</th>
                <th className="p-2 text-left">Total de horas trabajadas</th>
                <th className="p-2 text-left">Total de descanso</th>
                <th className="p-2 text-left">Total final</th>
              </tr>
            </thead>
            <tbody>
              {loading ? <tr><td className="p-4 text-center" colSpan={8}>Cargando…</td></tr> : null}
              {!loading && rowsWithTotals.length === 0 ? <tr><td className="p-4 text-center text-muted-foreground" colSpan={8}>Sin registros</td></tr> : null}
              {!loading && rowsWithTotals.map((row) => (
                <tr key={row.date} className="border-b border-border/40 transition-colors hover:bg-muted/40">
                  <td className="p-2 font-medium">{row.date}</td>
                  <td className="p-2">{fmtHM(row.clockIn)}</td>
                  <td className="p-2">{fmtHM(row.breakStart)}</td>
                  <td className="p-2">{fmtHM(row.breakEnd)}</td>
                  <td className="p-2">{fmtHM(row.clockOut)}</td>
                  <td className="p-2 text-emerald-700 dark:text-emerald-300">{fmtDuration(row.workedMinutes)}</td>
                  <td className="p-2 text-amber-700 dark:text-amber-300">{fmtDuration(row.breakMinutes)}</td>
                  <td className="p-2 font-semibold text-primary">{fmtDuration(row.finalMinutes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  );
};
