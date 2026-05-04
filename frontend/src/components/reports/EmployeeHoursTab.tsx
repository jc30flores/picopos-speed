import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getEmployeeHoursDetail, getEmployeeHoursSummary, updateEmployeeHoursCycle, type EmployeeHoursDetailResponse, type EmployeeHoursSummaryRow } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";

const toISODate = (date: Date) => date.toISOString().slice(0, 10);
const monthRange = () => {
  const now = new Date();
  return { from: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)), to: toISODate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) };
};
const formatDuration = (m: number | null | undefined) => {
  const minutes = Number(m || 0);
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
};
const formatDate = (value: string | null | undefined) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
};
const formatTime = (value: string | null | undefined) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
};
const formatTimeWithNextDay = (value: string | null | undefined, baseDate: string | null | undefined) => {
  if (!value) return "—";
  const time = formatTime(value);
  if (time === "—") return "—";
  if (!baseDate) return time;
  const b = new Date(baseDate);
  const t = new Date(value);
  if (Number.isNaN(b.getTime()) || Number.isNaN(t.getTime())) return time;
  const plus = t.getDate() !== b.getDate() || t.getMonth() !== b.getMonth() || t.getFullYear() !== b.getFullYear();
  return plus ? `${time} (+1)` : time;
};

export const EmployeeHoursTab = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const initial = monthRange();
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [rows, setRows] = useState<EmployeeHoursSummaryRow[]>([]);
  const [totals, setTotals] = useState({ employeeCount: 0, totalShiftMinutes: 0, totalBreakMinutes: 0, totalNetMinutes: 0 });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<EmployeeHoursDetailResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await getEmployeeHoursSummary({ dateFrom, dateTo, groupBy: "custom" });
      setRows(payload.employees);
      setTotals(payload.totals);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = setTimeout(() => {
      if (!dateFrom || !dateTo) return;
      if (dateFrom > dateTo) { setDateError("La fecha desde no puede ser mayor que la fecha hasta."); return; }
      setDateError(null);
      void load();
      if (open && selected) void detail(selected.employee.id);
    }, 320);
    return () => clearTimeout(id);
  }, [dateFrom, dateTo]);

  const detail = async (employeeId: number) => {
    const payload = await getEmployeeHoursDetail(employeeId, { dateFrom, dateTo });
    setSelected(payload);
    setOpen(true);
  };

  const summaryCards = useMemo(() => ([
    { label: "Total empleados", value: String(totals.employeeCount) },
    { label: "Horas turno", value: formatDuration(totals.totalShiftMinutes) },
    { label: "Total breaks", value: formatDuration(totals.totalBreakMinutes) },
    { label: "Horas netas", value: formatDuration(totals.totalNetMinutes) },
  ]), [totals]);

  const flatCycles = useMemo(() => {
    if (!selected) return [] as Array<{ date: string; baseDate: string; clockInAt: string | null; breakStartAt: string | null; breakEndAt: string | null; clockOutAt: string | null; shiftMinutes: number; breakMinutes: number; netMinutes: number; status: string }>;
    return selected.days.flatMap((day) => day.cycles.map((c) => ({ ...c, date: day.date, baseDate: c.clockInAt || day.date })));
  }, [selected]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Empleados</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <Button variant="outline" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button>
          
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {summaryCards.map((item) => <Card key={item.label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{item.label}</p><p className="text-xl font-bold">{item.value}</p></CardContent></Card>)}
      </div>

      <Card>
        <CardContent className="pt-6">
          <p className="mb-3 text-xs text-muted-foreground">Toca una fila para ver detalle.</p>
          <Table>
            <TableHeader><TableRow><TableHead>Empleado</TableHead><TableHead>Rol</TableHead><TableHead>Días</TableHead><TableHead>Entradas</TableHead><TableHead>Salidas</TableHead><TableHead>Horas turno</TableHead><TableHead>Breaks</TableHead><TableHead>Horas netas</TableHead></TableRow></TableHeader>
            <TableBody>
              {loading ? <TableRow><TableCell colSpan={6} className="text-center">Cargando...</TableCell></TableRow> : null}
              {!loading && rows.map((r) => (
                <TableRow
                  key={r.employeeId}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer transition-colors hover:bg-muted/40 focus-visible:bg-muted/50"
                  onClick={() => void detail(r.employeeId)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      void detail(r.employeeId);
                    }
                  }}
                >
                  <TableCell>{r.name}</TableCell><TableCell>{r.role}</TableCell><TableCell>{r.daysWorked}</TableCell><TableCell>{r.entriesCount}</TableCell><TableCell>{r.exitsCount}</TableCell><TableCell>{formatDuration(r.shiftMinutes)}</TableCell><TableCell>{formatDuration(r.breakMinutes)}</TableCell><TableCell>{formatDuration(r.netMinutes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-6xl border-border/70 bg-background/95">
          <DialogHeader><DialogTitle>Tarjeta de Horas — {selected?.employee.name}</DialogTitle></DialogHeader>

          {dateError ? <p className="text-sm text-red-500">{dateError}</p> : null}<div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} aria-label="Desde" className="h-11" />
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} aria-label="Hasta" className="h-11" />
            <div className="flex gap-2">
              <Button className="h-11" onClick={() => selected && void detail(selected.employee.id)}>Aplicar</Button>
              <Button className="h-11" variant="outline" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total horas turno</p><p className="text-lg font-semibold">{formatDuration(selected?.totals.shiftMinutes)}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total descanso</p><p className="text-lg font-semibold">{formatDuration(selected?.totals.breakMinutes)}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Total final</p><p className="text-lg font-semibold text-primary">{formatDuration(selected?.totals.netMinutes)}</p></CardContent></Card>
          </div>

          <div className="max-h-[420px] overflow-auto rounded-xl border border-border/60">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="sticky top-0 bg-muted/70 backdrop-blur-sm">
                <tr className="border-b border-border/70 text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="p-2 text-left">Fecha</th><th className="p-2 text-left">Entrada</th><th className="p-2 text-left">Salida</th><th className="p-2 text-left">Total de horas trabajadas</th><th className="p-2 text-left">Total de descanso</th><th className="p-2 text-left">Total final</th><th className="p-2 text-left">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {flatCycles.length === 0 ? <tr><td className="p-4 text-center text-muted-foreground" colSpan={7}>Sin registros</td></tr> : null}
                {flatCycles.map((c, i) => (
                  <tr key={`${c.date}-${i}`} className="border-b border-border/40 transition-colors hover:bg-muted/40">
                    <td className="p-2 font-medium">{formatDate(c.date)}</td>
                    <td className="p-2">{formatTime(c.clockInAt)}</td>
                    <td className="p-2">{c.clockInAt && !c.clockOutAt ? "En curso" : formatTimeWithNextDay(c.clockOutAt, c.baseDate)}</td>
                    <td className="p-2 text-emerald-700 dark:text-emerald-300">{formatDuration(c.shiftMinutes)}</td>
                    <td className="p-2 text-amber-700 dark:text-amber-300">{formatDuration(c.breakMinutes)}</td>
                    <td className="p-2 font-semibold text-primary">{formatDuration(c.netMinutes)}</td>
                    <td className="p-2">{isAdmin && c.id ? <Button type="button" size="sm" variant="outline" onClick={async () => { const hIn = prompt("Entrada ISO", c.clockInAt || "") || c.clockInAt || ""; const hOut = prompt("Salida ISO", c.clockOutAt || "") || c.clockOutAt; const br = Number(prompt("Break total segundos", String(c.break_seconds ?? 0)) || "0"); const reason = prompt("Motivo", "Corrección manual") || ""; try { await updateEmployeeHoursCycle(c.id, { clockInAt: hIn, clockOutAt: hOut, breakSecondsOverride: br, reason }); toast.success("Tarjeta de horas actualizada."); if (selected) { await detail(selected.employee.id); await load(); } } catch (e) { toast.error(e instanceof Error ? e.message : "No se pudo actualizar"); } }}>Editar</Button> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
