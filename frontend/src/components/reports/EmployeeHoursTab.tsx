import { useEffect, useMemo, useState } from "react";
import { ManualTimeCardModal } from "@/components/employees/ManualTimeCardModal";
import { formatDurationMinutes as formatDuration, formatRole, fmtTime, formatLocalDate, parseLocalDate } from "@/components/employees/timeCardUtils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createEmployeeHoursCycle, getEmployeeHoursDetail, getEmployeeHoursSummary, updateEmployeeHoursCycle, type EmployeeHoursDetailResponse, type EmployeeHoursSummaryRow } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";

const minDateStr = (a: string, b: string) => (a <= b ? a : b);
const monthRange = () => { const now = new Date(); return { from: formatLocalDate(new Date(now.getFullYear(), now.getMonth(), 1)), to: formatLocalDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) }; };
const secondsToDurationParts = (seconds: number | null | undefined) => { const total = Math.max(0, Math.floor(Number(seconds || 0))); return { hours: Math.floor(total / 3600), minutes: Math.floor((total % 3600) / 60), seconds: total % 60 }; };
const durationPartsToSeconds = (hours: number, minutes: number, seconds: number) => Math.max(0, (Number(hours || 0) * 3600) + (Math.min(59, Math.max(0, Number(minutes || 0))) * 60) + Math.min(59, Math.max(0, Number(seconds || 0))));

type DurationParts = { hours: number; minutes: number; seconds: number };
type EditState = { id: number | null; employeeId: number; date: string; entry: string; exit: string; nextDay: boolean; shift: DurationParts; break: DurationParts; reason: string; isEmpty: boolean };

export const EmployeeHoursTab = () => {
  const { user } = useAuth(); const isAdmin = user?.role === "admin";
  const initial = monthRange();
  const [dateFrom, setDateFrom] = useState(initial.from); const [dateTo, setDateTo] = useState(initial.to);
  const [rows, setRows] = useState<EmployeeHoursSummaryRow[]>([]); const [selected, setSelected] = useState<EmployeeHoursDetailResponse | null>(null);
  const [loading, setLoading] = useState(false); const [open, setOpen] = useState(false); const [editOpen, setEditOpen] = useState(false); const [edit, setEdit] = useState<EditState | null>(null); const [manualOpen, setManualOpen] = useState(false);
  const [totals, setTotals] = useState({ employeeCount: 0, totalShiftMinutes: 0, totalBreakMinutes: 0, totalNetMinutes: 0 });

  const load = async () => { setLoading(true); try { const payload = await getEmployeeHoursSummary({ dateFrom, dateTo, groupBy: "custom" }); setRows(payload.employees.filter((r) => !r.name?.toLowerCase().startsWith("empleado eliminado"))); setTotals(payload.totals); } finally { setLoading(false); } };
  const detail = async (employeeId: number) => { const payload = await getEmployeeHoursDetail(employeeId, { dateFrom, dateTo }); setSelected(payload); setOpen(true); };
  useEffect(() => { if (dateFrom <= dateTo) { void load(); if (open && selected) void detail(selected.employee.id); } }, [dateFrom, dateTo]);

  const dayRows = useMemo(() => {
    if (!selected) return [] as any[];
    const todayLocal = formatLocalDate(new Date());
    const effectiveTo = minDateStr(dateTo, todayLocal);
    if (dateFrom > effectiveTo) return [];
    const byDay = new Map(selected.days.map((d) => [d.date, d.cycles]));
    const list: any[] = [];
    for (let day = parseLocalDate(dateFrom); formatLocalDate(day) <= effectiveTo; day = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1)) {
      const d = formatLocalDate(day); const cycles = byDay.get(d) || [];
      if (cycles.length === 0) list.push({ date: d, isEmpty: true, id: null, employeeId: selected.employee.id, shiftMinutes: null, breakMinutes: null, netMinutes: null });
      else cycles.forEach((c: any) => list.push({ ...c, date: d, isEmpty: false, employeeId: selected.employee.id }));
    }
    return list;
  }, [selected, dateFrom, dateTo]);

  const openEdit = (c: any) => {
    if (!isAdmin) return;
    const shiftSeconds = Math.round(Number(c.shiftMinutes || 0) * 60); const breakSeconds = Math.round(Number(c.breakSeconds ?? Number(c.breakMinutes || 0) * 60));
    setEdit({ id: c.id ?? null, employeeId: c.employeeId, date: c.date, entry: c.clockInAt ? new Date(c.clockInAt).toTimeString().slice(0, 5) : "", exit: c.clockOutAt ? new Date(c.clockOutAt).toTimeString().slice(0, 5) : "", nextDay: false, shift: secondsToDurationParts(shiftSeconds), break: secondsToDurationParts(breakSeconds), reason: c.isEmpty ? "Registro manual" : "Corrección manual", isEmpty: !!c.isEmpty });
    setEditOpen(true);
  };

  const saveEdit = async () => {
    if (!edit?.date || !edit.entry) return toast.error("La hora de entrada es obligatoria.");
    const shiftSeconds = durationPartsToSeconds(edit.shift.hours, edit.shift.minutes, edit.shift.seconds);
    const breakSeconds = durationPartsToSeconds(edit.break.hours, edit.break.minutes, edit.break.seconds);
    if (breakSeconds > shiftSeconds) return toast.error("El descanso no puede ser mayor que las horas trabajadas.");
    const payload = { date: edit.date, clockInTime: edit.entry, clockOutTime: edit.exit || null, clockOutNextDay: edit.nextDay, shiftSeconds, breakSeconds, reason: edit.reason };
    if (edit.id) await updateEmployeeHoursCycle(edit.id, payload); else await createEmployeeHoursCycle({ employeeId: edit.employeeId, ...payload });
    toast.success(edit.id ? "Tarjeta de horas actualizada." : "Tarjeta de horas creada."); setEditOpen(false); if (selected) await detail(selected.employee.id); await load();
  };

  return <div className="space-y-4">
    <Card><CardHeader><CardTitle>Empleados</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-5"><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /><Button variant="outline" onClick={() => { const r = monthRange(); setDateFrom(r.from); setDateTo(r.to); }}>Mes actual</Button><Button onClick={() => setManualOpen(true)} className="md:col-span-2">+ Tarjeta de Horas</Button></CardContent></Card>
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4"><Card><CardContent className="p-4"><p>Total empleados</p><p>{totals.employeeCount}</p></CardContent></Card><Card><CardContent className="p-4"><p>Horas turno</p><p className="text-emerald-700">{formatDuration(totals.totalShiftMinutes)}</p></CardContent></Card><Card><CardContent className="p-4"><p>Total breaks</p><p className="text-amber-700">{formatDuration(totals.totalBreakMinutes)}</p></CardContent></Card><Card><CardContent className="p-4"><p>Horas netas</p><p className="text-sky-700">{formatDuration(totals.totalNetMinutes)}</p></CardContent></Card></div>
    <Card><CardContent className="pt-6"><Table><TableHeader><TableRow><TableHead className="text-center">Empleado</TableHead><TableHead className="text-center">Rol</TableHead><TableHead className="text-center">Días</TableHead><TableHead className="text-center">Entradas</TableHead><TableHead className="text-center">Salidas</TableHead><TableHead className="text-center">Horas turno</TableHead><TableHead className="text-center">Breaks</TableHead><TableHead className="text-center">Horas netas</TableHead></TableRow></TableHeader><TableBody>{loading ? <TableRow><TableCell colSpan={8} className="text-center">Cargando...</TableCell></TableRow> : rows.map((r) => <TableRow key={r.employeeId} className="cursor-pointer" onClick={() => void detail(r.employeeId)}><TableCell className="text-center">{r.name}</TableCell><TableCell className="text-center">{formatRole(r.role)}</TableCell><TableCell className="text-center tabular-nums">{r.daysWorked}</TableCell><TableCell className="text-center tabular-nums">{r.entriesCount}</TableCell><TableCell className="text-center tabular-nums">{r.exitsCount}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.shiftMinutes)}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.breakMinutes)}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.netMinutes)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Tarjeta de Horas — {selected?.employee.name}</DialogTitle></DialogHeader>{isAdmin ? <p className="text-xs text-muted-foreground">Toca una fila para editar o crear un registro.</p> : null}<div className="max-h-[420px] overflow-auto rounded-xl border"><table className="w-full"><thead><tr><th className="text-center">FECHA</th><th className="text-center">ENTRADA</th><th className="text-center">SALIDA</th><th className="text-center">TOTAL DE HORAS TRABAJADAS</th><th className="text-center">TOTAL DE DESCANSO</th><th className="text-center">TOTAL FINAL</th></tr></thead><tbody>{dayRows.length === 0 ? <tr><td colSpan={6} className="p-3 text-center text-muted-foreground">Sin registros</td></tr> : dayRows.map((c, i) => <tr key={i} className={`${isAdmin ? "cursor-pointer hover:bg-muted/40" : ""}`} onClick={() => openEdit(c)}><td className="text-center tabular-nums">{c.date}</td><td className="text-center tabular-nums">{c.isEmpty ? "—" : fmtTime(c.clockInAt)}</td><td className="text-center tabular-nums">{c.isEmpty ? "—" : (c.clockInAt && !c.clockOutAt ? "En curso" : `${fmtTime(c.clockOutAt)}${c.clockOutNextDay ? " (+1)" : ""}`)}</td><td className="text-center tabular-nums text-emerald-700">{c.isEmpty ? "—" : formatDuration(c.shiftMinutes)}</td><td className="text-center tabular-nums text-amber-700">{c.isEmpty ? "—" : formatDuration(c.breakMinutes)}</td><td className="text-center tabular-nums text-sky-700">{c.isEmpty ? "—" : formatDuration(c.netMinutes)}</td></tr>)}</tbody></table></div></DialogContent></Dialog>
    <Dialog open={editOpen} onOpenChange={setEditOpen}><DialogContent><DialogHeader><DialogTitle>{edit?.id ? "Editar registro de horas" : "Crear registro de horas"}</DialogTitle></DialogHeader>{edit ? <div className="space-y-3"><Label>Fecha</Label><Input type="date" value={edit.date} onChange={(e) => setEdit({ ...edit, date: e.target.value })} /><Label>Entrada</Label><Input type="time" value={edit.entry} onChange={(e) => setEdit({ ...edit, entry: e.target.value })} /><Label>Salida</Label><Input type="time" value={edit.exit} onChange={(e) => setEdit({ ...edit, exit: e.target.value })} /><label><input type="checkbox" checked={edit.nextDay} onChange={(e) => setEdit({ ...edit, nextDay: e.target.checked })} />Salida al día siguiente</label><Label>Total de horas trabajadas</Label><div className="grid grid-cols-3 gap-2"><Input type="number" min={0} value={edit.shift.hours} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, hours: Number(e.target.value || 0) } })} /><Input type="number" min={0} max={59} value={edit.shift.minutes} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, minutes: Number(e.target.value || 0) } })} /><Input type="number" min={0} max={59} value={edit.shift.seconds} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, seconds: Number(e.target.value || 0) } })} /></div><Label>Total de descanso</Label><div className="grid grid-cols-3 gap-2"><Input type="number" min={0} value={edit.break.hours} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, hours: Number(e.target.value || 0) } })} /><Input type="number" min={0} max={59} value={edit.break.minutes} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, minutes: Number(e.target.value || 0) } })} /><Input type="number" min={0} max={59} value={edit.break.seconds} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, seconds: Number(e.target.value || 0) } })} /></div><Label>Motivo</Label><Input value={edit.reason} onChange={(e) => setEdit({ ...edit, reason: e.target.value })} /><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setEditOpen(false)}>Cancelar</Button><Button onClick={() => void saveEdit()}>Guardar cambios</Button></div></div> : null}</DialogContent></Dialog>
  <ManualTimeCardModal open={manualOpen} onClose={() => setManualOpen(false)} employees={rows.map((r) => ({ id: r.employeeId, name: r.name, role: r.role }))} onSaved={() => { void load(); if (selected) void detail(selected.employee.id); }} /></div>;
};
