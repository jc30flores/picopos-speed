import { useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AttendanceHistoryRow } from "@/lib/api";

const fmtHM = (value: string | null) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rows: AttendanceHistoryRow[];
  loading?: boolean;
  onApplyFilters: (filters: { start?: string; end?: string }) => Promise<void> | void;
};

export const AttendanceRecordsModal = ({ open, onOpenChange, rows, loading = false, onApplyFilters }: Props) => {
  const [day, setDay] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const sorted = useMemo(() => [...rows].sort((a, b) => b.date.localeCompare(a.date)), [rows]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Registros de asistencia</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3 md:grid-cols-4">
          <Input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          <div className="flex gap-2">
            <Button className="h-11" onClick={() => void onApplyFilters(day ? { start: day, end: day } : { start: start || undefined, end: end || undefined })}>Aplicar</Button>
            <Button className="h-11" variant="outline" onClick={() => { setDay(""); setStart(""); setEnd(""); void onApplyFilters({}); }}>Limpiar</Button>
          </div>
        </div>
        <div className="max-h-[420px] overflow-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background">
              <tr className="border-b">
                <th className="p-2 text-left">Fecha</th><th className="p-2 text-left">Entrada</th><th className="p-2 text-left">Break In</th><th className="p-2 text-left">Break Out</th><th className="p-2 text-left">Salida</th>
              </tr>
            </thead>
            <tbody>
              {loading ? <tr><td className="p-4 text-center" colSpan={5}>Cargando…</td></tr> : null}
              {!loading && sorted.length === 0 ? <tr><td className="p-4 text-center text-muted-foreground" colSpan={5}>Sin registros</td></tr> : null}
              {!loading && sorted.map((row) => (
                <tr key={row.date} className="border-b/50">
                  <td className="p-2">{row.date}</td>
                  <td className="p-2">{fmtHM(row.clockIn)}</td>
                  <td className="p-2">{fmtHM(row.breakStart)}</td>
                  <td className="p-2">{fmtHM(row.breakEnd)}</td>
                  <td className="p-2">{fmtHM(row.clockOut)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  );
};
