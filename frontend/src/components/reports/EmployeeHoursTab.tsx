import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getEmployeeHoursDetail, getEmployeeHoursSummary, updateEmployeeHoursCycle, type EmployeeHoursDetailResponse, type EmployeeHoursSummaryRow } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";

const toISODate = (date: Date) => date.toISOString().slice(0, 10);
const monthRange = () => { const now = new Date(); return { from: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)), to: toISODate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) }; };
const formatDuration = (m: number | null | undefined) => { const s = Math.max(0, Math.round(Number(m || 0) * 60)); if (s > 0 && s < 60) return `${s}s`; const mm = Math.floor(s / 60); return `${Math.floor(mm / 60)}h ${String(mm % 60).padStart(2, "0")}m`; };
const hhmm = (v: string | null | undefined) => { if (!v) return ""; const d = new Date(v); if (Number.isNaN(d.getTime())) return ""; return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const formatDate = (value: string | null | undefined) => value ? new Intl.DateTimeFormat("es-SV", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value)) : "—";
const fmtTime = (value: string | null | undefined) => value ? new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value)) : "—";

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
  const [editOpen, setEditOpen] = useState(false);
  const [edit, setEdit] = useState<any>(null);

  const load = async () => { setLoading(true); try { const payload = await getEmployeeHoursSummary({ dateFrom, dateTo, groupBy: "custom" }); setRows(payload.employees); setTotals(payload.totals); } finally { setLoading(false); } };
  const detail = async (employeeId: number) => { const payload = await getEmployeeHoursDetail(employeeId, { dateFrom, dateTo }); setSelected(payload); setOpen(true); };

  useEffect(() => { const id = setTimeout(() => { if (!dateFrom || !dateTo) return; if (dateFrom > dateTo) { setDateError("La fecha desde no puede ser mayor que la fecha hasta."); return; } setDateError(null); void load(); if (open && selected) void detail(selected.employee.id); }, 300); return () => clearTimeout(id); }, [dateFrom, dateTo]);

  const flatCycles = useMemo(() => !selected ? [] as any[] : selected.days.flatMap((day) => day.cycles.map((c: any) => ({ ...c, date: day.date }))), [selected]);
  const openEdit = (c: any) => {
    if (!isAdmin || !c.id) return;
    const shiftSeconds = Math.max(0, Math.round(Number(c.shiftMinutes || 0) * 60));
    const breakSeconds = Math.max(0, Math.round(Number(c.breakSeconds ?? c.breakMinutes * 60 ?? 0)));
    setEdit({ id: c.id, date: c.date, entry: hhmm(c.clockInAt), exit: hhmm(c.clockOutAt), nextDay: false, shiftSeconds, breakSeconds, reason: "Corrección manual" });
    setEditOpen(true);
  };
  const saveEdit = async () => {
    if (!edit?.date || !edit?.entry) return toast.error("Fecha y entrada son obligatorias.");
    if (edit.shiftSeconds < 0 || edit.breakSeconds < 0) return toast.error("Duraciones no pueden ser negativas.");
    if (edit.breakSeconds > edit.shiftSeconds) return toast.error("Descanso no puede ser mayor al turno.");
    const [eh, em] = edit.entry.split(":").map(Number);
    const entry = new Date(`${edit.date}T00:00:00`); entry.setHours(eh, em, 0, 0);
    let exit = new Date(entry.getTime() + edit.shiftSeconds * 1000);
    if (edit.exit) { const [xh, xm] = edit.exit.split(":").map(Number); exit = new Date(`${edit.date}T00:00:00`); exit.setHours(xh, xm, 0, 0); if (edit.nextDay || exit < entry) exit.setDate(exit.getDate() + 1); }
    await updateEmployeeHoursCycle(edit.id, { clockInAt: entry.toISOString(), clockOutAt: exit.toISOString(), breakSecondsOverride: edit.breakSeconds, reason: edit.reason });
    toast.success("Tarjeta de horas actualizada.");
    setEditOpen(false);
    if (selected) await detail(selected.employee.id);
    await load();
  };

  const summaryCards = [
    { label: "Total empleados", value: String(totals.employeeCount) },
    { label: "Horas turno", value: formatDuration(totals.totalShiftMinutes) },
    { label: "Total breaks", value: formatDuration(totals.totalBreakMinutes) },
    { label: "Horas netas", value: formatDuration(totals.totalNetMinutes) },
  ];

  return <div className="space-y-4">
    <Card><CardHeader><CardTitle>Empleados</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-5"><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /><Button variant="outline" type="button" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button></CardContent></Card>
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">{summaryCards.map((item) => <Card key={item.label}><CardContent className="p-4"><p className="text-xs text-muted-foreground">{item.label}</p><p className="text-xl font-bold">{item.value}</p></CardContent></Card>)}</div>
    <Card><CardContent className="pt-6"><p className="mb-3 text-xs text-muted-foreground">Toca una fila para ver detalle.</p><Table><TableHeader><TableRow><TableHead>Empleado</TableHead><TableHead>Rol</TableHead><TableHead>Días</TableHead><TableHead>Entradas</TableHead><TableHead>Salidas</TableHead><TableHead>Horas turno</TableHead><TableHead>Breaks</TableHead><TableHead>Horas netas</TableHead></TableRow></TableHeader><TableBody>{loading ? <TableRow><TableCell colSpan={8} className="text-center">Cargando...</TableCell></TableRow> : null}{!loading && rows.map((r) => <TableRow key={r.employeeId} role="button" tabIndex={0} className="cursor-pointer hover:bg-muted/40" onClick={() => void detail(r.employeeId)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); void detail(r.employeeId); } }}><TableCell>{r.name}</TableCell><TableCell>{r.role}</TableCell><TableCell>{r.daysWorked}</TableCell><TableCell>{r.entriesCount}</TableCell><TableCell>{r.exitsCount}</TableCell><TableCell>{formatDuration(r.shiftMinutes)}</TableCell><TableCell>{formatDuration(r.breakMinutes)}</TableCell><TableCell>{formatDuration(r.netMinutes)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Tarjeta de Horas — {selected?.employee.name}</DialogTitle></DialogHeader>{dateError ? <p className="text-sm text-red-500">{dateError}</p> : null}<div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /><Button type="button" variant="outline" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button></div>{isAdmin ? <p className="text-xs text-muted-foreground">Toca una fila para editar el registro.</p> : null}
      <div className="max-h-[420px] overflow-auto rounded-xl border"><table className="w-full min-w-[900px] text-sm"><thead><tr className="text-xs uppercase text-muted-foreground border-b"><th className="p-2 text-left">Fecha</th><th className="p-2 text-left">Entrada</th><th className="p-2 text-left">Salida</th><th className="p-2 text-left">Total de horas trabajadas</th><th className="p-2 text-left">Total de descanso</th><th className="p-2 text-left">Total final</th></tr></thead><tbody>{flatCycles.map((c, i) => <tr key={`${c.date}-${i}`} role={isAdmin ? "button" : undefined} tabIndex={isAdmin ? 0 : -1} className={`border-b ${isAdmin ? "cursor-pointer hover:bg-muted/40" : ""}`} onClick={() => openEdit(c)} onKeyDown={(e) => { if (isAdmin && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openEdit(c); } }}><td className="p-2">{formatDate(c.date)}</td><td className="p-2">{fmtTime(c.clockInAt)}</td><td className="p-2">{c.clockInAt && !c.clockOutAt ? "En curso" : fmtTime(c.clockOutAt)}</td><td className="p-2">{formatDuration(c.shiftMinutes)}</td><td className="p-2">{formatDuration(c.breakMinutes)}</td><td className="p-2">{formatDuration(c.netMinutes)}</td></tr>)}</tbody></table></div>
    </DialogContent></Dialog>

    <Dialog open={editOpen} onOpenChange={setEditOpen}><DialogContent><DialogHeader><DialogTitle>Editar registro de horas</DialogTitle></DialogHeader>{edit ? <div className="space-y-3"><div><Label>Fecha</Label><Input type="date" value={edit.date} onChange={(e) => setEdit({ ...edit, date: e.target.value })} /></div><div><Label>Entrada</Label><Input type="time" value={edit.entry} onChange={(e) => setEdit({ ...edit, entry: e.target.value })} /></div><div><Label>Salida</Label><Input type="time" value={edit.exit} onChange={(e) => setEdit({ ...edit, exit: e.target.value })} /></div><label className="flex gap-2"><input type="checkbox" checked={edit.nextDay} onChange={(e) => setEdit({ ...edit, nextDay: e.target.checked })} />Salida al día siguiente</label><div><Label>Total horas trabajadas (s)</Label><Input type="number" min={0} value={edit.shiftSeconds} onChange={(e) => setEdit({ ...edit, shiftSeconds: Number(e.target.value || 0) })} /></div><div><Label>Total descanso (s)</Label><Input type="number" min={0} value={edit.breakSeconds} onChange={(e) => setEdit({ ...edit, breakSeconds: Number(e.target.value || 0) })} /></div><div><Label>Motivo</Label><Input value={edit.reason} onChange={(e) => setEdit({ ...edit, reason: e.target.value })} /></div><div className="flex justify-end gap-2"><Button variant="outline" type="button" onClick={() => setEditOpen(false)}>Cancelar</Button><Button type="button" onClick={() => void saveEdit()}>Guardar cambios</Button></div></div> : null}</DialogContent></Dialog>
  </div>;
};
