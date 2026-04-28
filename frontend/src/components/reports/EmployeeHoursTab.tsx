import { useEffect, useMemo, useState } from "react";
import { Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getEmployeeHoursDetail, getEmployeeHoursSummary, type EmployeeHoursDetailResponse, type EmployeeHoursSummaryRow } from "@/lib/api";

const toISODate = (date: Date) => date.toISOString().slice(0, 10);
const monthRange = () => {
  const now = new Date();
  return { from: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)), to: toISODate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) };
};
const fmt = (m: number) => `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;

export const EmployeeHoursTab = () => {
  const initial = monthRange();
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [rows, setRows] = useState<EmployeeHoursSummaryRow[]>([]);
  const [totals, setTotals] = useState({ employeeCount: 0, totalShiftMinutes: 0, totalBreakMinutes: 0, totalNetMinutes: 0 });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<EmployeeHoursDetailResponse | null>(null);
  const [open, setOpen] = useState(false);

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

  useEffect(() => { void load(); }, []);

  const detail = async (employeeId: number) => {
    const payload = await getEmployeeHoursDetail(employeeId, { dateFrom, dateTo });
    setSelected(payload);
    setOpen(true);
  };

  const summaryCards = useMemo(() => ([
    { label: "Total empleados", value: String(totals.employeeCount) },
    { label: "Horas turno", value: fmt(totals.totalShiftMinutes) },
    { label: "Total breaks", value: fmt(totals.totalBreakMinutes) },
    { label: "Horas netas", value: fmt(totals.totalNetMinutes) },
  ]), [totals]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Empleados</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <Button variant="outline" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button>
          <Button onClick={() => void load()}>Aplicar</Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {summaryCards.map((item) => <Card key={item.label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{item.label}</p><p className="text-xl font-bold">{item.value}</p></CardContent></Card>)}
      </div>

      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader><TableRow><TableHead>Empleado</TableHead><TableHead>Rol</TableHead><TableHead>Días</TableHead><TableHead>Entradas</TableHead><TableHead>Salidas</TableHead><TableHead>Horas turno</TableHead><TableHead>Breaks</TableHead><TableHead>Horas netas</TableHead><TableHead>Estado</TableHead><TableHead>Acción</TableHead></TableRow></TableHeader>
            <TableBody>
              {loading ? <TableRow><TableCell colSpan={10} className="text-center">Cargando...</TableCell></TableRow> : null}
              {!loading && rows.map((r) => (
                <TableRow key={r.employeeId}>
                  <TableCell>{r.name}</TableCell><TableCell>{r.role}</TableCell><TableCell>{r.daysWorked}</TableCell><TableCell>{r.entriesCount}</TableCell><TableCell>{r.exitsCount}</TableCell><TableCell>{fmt(r.shiftMinutes)}</TableCell><TableCell>{fmt(r.breakMinutes)}</TableCell><TableCell>{fmt(r.netMinutes)}</TableCell><TableCell>{r.status === "inactive" ? "Inactivo" : r.currentState}</TableCell>
                  <TableCell><Button size="sm" variant="outline" onClick={() => void detail(r.employeeId)} title="Ver detalle" aria-label="Ver detalle"><Eye className="h-4 w-4" /></Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader><DialogTitle>Detalle de horas — {selected?.employee.name}</DialogTitle></DialogHeader>
          <div className="max-h-[70vh] overflow-auto space-y-3">
            {selected?.days.map((day) => (
              <Card key={day.date}><CardHeader><CardTitle className="text-base">{day.date} · Turno {fmt(day.dailyTotals.shiftMinutes)} · Break {fmt(day.dailyTotals.breakMinutes)} · Neto {fmt(day.dailyTotals.netMinutes)}</CardTitle></CardHeader><CardContent className="space-y-2">{day.cycles.map((c, i) => <div key={i} className="rounded border p-2 text-sm">Entrada: {c.clockInAt || "-"} · Break salida: {c.breakStartAt || "-"} · Break regreso: {c.breakEndAt || "-"} · Salida: {c.clockOutAt || "-"} · Estado: {c.status}</div>)}</CardContent></Card>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
