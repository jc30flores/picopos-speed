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
const monthRange = () => {
  const now = new Date();
  return { from: formatLocalDate(new Date(now.getFullYear(), now.getMonth(), 1)), to: formatLocalDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) };
};

const numberPlaceholder = (value: number | null | undefined) => {
  const parsed = Number(value || 0);
  return parsed === 0 ? "" : String(parsed);
};

const secondsToDurationParts = (seconds: number | null | undefined) => {
  const total = Math.max(0, Math.floor(Number(seconds || 0)));
  return {
    hours: numberPlaceholder(Math.floor(total / 3600)),
    minutes: numberPlaceholder(Math.floor((total % 3600) / 60)),
    seconds: numberPlaceholder(total % 60),
  };
};

const partToNumber = (value: string) => (value.trim() === "" ? 0 : Number(value));
const durationPartsToSeconds = (parts: DurationParts) => Math.max(0, (partToNumber(parts.hours) * 3600) + (Math.min(59, Math.max(0, partToNumber(parts.minutes))) * 60) + Math.min(59, Math.max(0, partToNumber(parts.seconds))));

const isValidPart = (value: string, max?: number) => {
  if (value.trim() === "") return true;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && (max == null || parsed <= max);
};

const localDateFromIso = (value?: string | null, fallback?: string) => value ? formatLocalDate(new Date(value)) : (fallback ?? formatLocalDate(new Date()));
const localTimeFromIso = (value?: string | null) => value ? new Date(value).toTimeString().slice(0, 5) : "";

type DurationParts = { hours: string; minutes: string; seconds: string };
type EditState = {
  id: number | null;
  employeeId: number;
  entryDate: string;
  exitDate: string;
  exitDateEdited: boolean;
  entry: string;
  exit: string;
  shift: DurationParts;
  break: DurationParts;
  reason: string;
  isEmpty: boolean;
};

export const EmployeeHoursTab = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const initial = monthRange();
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [rows, setRows] = useState<EmployeeHoursSummaryRow[]>([]);
  const [selected, setSelected] = useState<EmployeeHoursDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [edit, setEdit] = useState<EditState | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [totals, setTotals] = useState({ employeeCount: 0, totalShiftMinutes: 0, totalBreakMinutes: 0, totalNetMinutes: 0 });

  const load = async () => {
    setLoading(true);
    try {
      const payload = await getEmployeeHoursSummary({ dateFrom, dateTo, groupBy: "custom" });
      setRows(payload.employees.filter((r) => !r.name?.toLowerCase().startsWith("empleado eliminado")));
      setTotals(payload.totals);
    } finally {
      setLoading(false);
    }
  };

  const detail = async (employeeId: number) => {
    const payload = await getEmployeeHoursDetail(employeeId, { dateFrom, dateTo });
    setSelected(payload);
    setOpen(true);
  };

  useEffect(() => {
    if (dateFrom <= dateTo) {
      void load();
      if (open && selected) void detail(selected.employee.id);
    }
  }, [dateFrom, dateTo]);

  const dayRows = useMemo(() => {
    if (!selected) return [] as any[];
    const todayLocal = formatLocalDate(new Date());
    const effectiveTo = minDateStr(dateTo, todayLocal);
    if (dateFrom > effectiveTo) return [];
    const byDay = new Map(selected.days.map((d) => [d.date, d.cycles]));
    const list: any[] = [];
    for (let day = parseLocalDate(dateFrom); formatLocalDate(day) <= effectiveTo; day = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1)) {
      const d = formatLocalDate(day);
      const cycles = byDay.get(d) || [];
      if (cycles.length === 0) list.push({ date: d, isEmpty: true, id: null, employeeId: selected.employee.id, shiftMinutes: null, breakMinutes: null, netMinutes: null });
      else cycles.forEach((c: any) => list.push({ ...c, date: d, isEmpty: false, employeeId: selected.employee.id }));
    }
    return list;
  }, [selected, dateFrom, dateTo]);

  const openEdit = (c: any) => {
    if (!isAdmin) return;
    const shiftSeconds = Math.round(Number(c.shiftMinutes || 0) * 60);
    const breakSeconds = Math.round(Number(c.breakSeconds ?? Number(c.breakMinutes || 0) * 60));
    const entryDate = localDateFromIso(c.clockInAt, c.date);
    const exitDate = c.clockOutAt ? localDateFromIso(c.clockOutAt, c.date) : c.date;
    setEdit({
      id: c.id ?? null,
      employeeId: c.employeeId,
      entryDate,
      exitDate,
      exitDateEdited: Boolean(c.clockOutAt && exitDate !== entryDate),
      entry: localTimeFromIso(c.clockInAt),
      exit: localTimeFromIso(c.clockOutAt),
      shift: secondsToDurationParts(shiftSeconds),
      break: secondsToDurationParts(breakSeconds),
      reason: c.isEmpty ? "Registro manual" : "Corrección manual",
      isEmpty: !!c.isEmpty,
    });
    setEditOpen(true);
  };

  const setEntryDate = (value: string) => {
    setEdit((prev) => prev ? { ...prev, entryDate: value, exitDate: prev.exitDateEdited ? prev.exitDate : value } : prev);
  };

  const setExitDate = (value: string) => {
    setEdit((prev) => prev ? { ...prev, exitDate: value, exitDateEdited: true } : prev);
  };

  const saveEdit = async () => {
    if (!edit?.entryDate || !edit.exitDate) return toast.error("La fecha de entrada y la fecha de salida son obligatorias.");
    if (!edit.entry) return toast.error("La hora de entrada es obligatoria.");
    if (edit.exitDate < edit.entryDate) return toast.error("La fecha de salida no puede ser anterior a la fecha de entrada.");
    if (!isValidPart(edit.shift.hours) || !isValidPart(edit.shift.minutes, 59) || !isValidPart(edit.shift.seconds, 59) || !isValidPart(edit.break.hours) || !isValidPart(edit.break.minutes, 59) || !isValidPart(edit.break.seconds, 59)) {
      return toast.error("Horas, minutos y segundos deben ser valores positivos; minutos y segundos deben estar entre 0 y 59.");
    }
    const shiftSeconds = durationPartsToSeconds(edit.shift);
    const breakSeconds = durationPartsToSeconds(edit.break);
    if (breakSeconds > shiftSeconds) return toast.error("El descanso no puede ser mayor que las horas trabajadas.");
    if (edit.exit) {
      const entryDateTime = new Date(`${edit.entryDate}T${edit.entry}:00`);
      const exitDateTime = new Date(`${edit.exitDate}T${edit.exit}:00`);
      if (exitDateTime <= entryDateTime) return toast.error("La salida debe ser posterior a la entrada. Si salió al día siguiente, cambia la fecha de salida.");
    }
    const payload = {
      date: edit.entryDate,
      clockInTime: edit.entry,
      clockOutTime: edit.exit || null,
      clockOutNextDay: Boolean(edit.exit && edit.exitDate > edit.entryDate),
      shiftSeconds,
      breakSeconds,
      reason: edit.reason,
    };
    if (edit.id) await updateEmployeeHoursCycle(edit.id, payload);
    else await createEmployeeHoursCycle({ employeeId: edit.employeeId, ...payload });
    toast.success(edit.id ? "Tarjeta de horas actualizada." : "Tarjeta de horas creada.");
    setEditOpen(false);
    if (selected) await detail(selected.employee.id);
    await load();
  };

  return <div className="space-y-4">
    <Card>
      <CardHeader><CardTitle>Reporte de horas por empleado</CardTitle></CardHeader>
      <CardContent className="flex flex-wrap items-end gap-3">
        <div><Label>Desde</Label><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></div>
        <div><Label>Hasta</Label><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></div>
        <Button onClick={() => void load()}>Aplicar</Button>
        {isAdmin ? <Button variant="outline" onClick={() => setManualOpen(true)}>Crear registro de horas</Button> : null}
      </CardContent>
    </Card>

    <div className="grid gap-3 md:grid-cols-4">
      <Card><CardContent className="p-4"><p>Empleados</p><p className="text-2xl font-bold">{totals.employeeCount}</p></CardContent></Card>
      <Card><CardContent className="p-4"><p>Horas turno</p><p className="text-emerald-700">{formatDuration(totals.totalShiftMinutes)}</p></CardContent></Card>
      <Card><CardContent className="p-4"><p>Total descanso</p><p className="text-amber-700">{formatDuration(totals.totalBreakMinutes)}</p></CardContent></Card>
      <Card><CardContent className="p-4"><p>Horas netas</p><p className="text-sky-700">{formatDuration(totals.totalNetMinutes)}</p></CardContent></Card>
    </div>

    <Card><CardContent className="pt-6"><Table><TableHeader><TableRow><TableHead className="text-center">Empleado</TableHead><TableHead className="text-center">Rol</TableHead><TableHead className="text-center">Días</TableHead><TableHead className="text-center">Entradas</TableHead><TableHead className="text-center">Salidas</TableHead><TableHead className="text-center">Horas turno</TableHead><TableHead className="text-center">Descansos</TableHead><TableHead className="text-center">Horas netas</TableHead></TableRow></TableHeader><TableBody>{loading ? <TableRow><TableCell colSpan={8} className="text-center">Cargando...</TableCell></TableRow> : rows.map((r) => <TableRow key={r.employeeId} className="cursor-pointer" onClick={() => void detail(r.employeeId)}><TableCell className="text-center">{r.name}</TableCell><TableCell className="text-center">{formatRole(r.role)}</TableCell><TableCell className="text-center tabular-nums">{r.daysWorked}</TableCell><TableCell className="text-center tabular-nums">{r.entriesCount}</TableCell><TableCell className="text-center tabular-nums">{r.exitsCount}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.shiftMinutes)}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.breakMinutes)}</TableCell><TableCell className="text-center tabular-nums">{formatDuration(r.netMinutes)}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>

    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-6xl">
        <DialogHeader><DialogTitle>Tarjeta de horas — {selected?.employee.name}</DialogTitle></DialogHeader>
        {isAdmin ? <p className="text-xs text-muted-foreground">Toca una fila para editar o crear un registro.</p> : null}
        <div className="max-h-[420px] overflow-auto rounded-xl border">
          <table className="w-full">
            <thead><tr><th className="text-center">FECHA</th><th className="text-center">ENTRADA</th><th className="text-center">SALIDA</th><th className="text-center">TOTAL DE HORAS TRABAJADAS</th><th className="text-center">TOTAL DE DESCANSO</th><th className="text-center">TOTAL FINAL</th></tr></thead>
            <tbody>{dayRows.length === 0 ? <tr><td colSpan={6} className="p-3 text-center text-muted-foreground">Sin registros</td></tr> : dayRows.map((c, i) => <tr key={i} className={`${isAdmin ? "cursor-pointer hover:bg-muted/40" : ""}`} onClick={() => openEdit(c)}><td className="text-center tabular-nums">{c.date}</td><td className="text-center tabular-nums">{c.isEmpty ? "—" : fmtTime(c.clockInAt)}</td><td className="text-center tabular-nums">{c.isEmpty ? "—" : (c.clockInAt && !c.clockOutAt ? "En curso" : fmtTime(c.clockOutAt))}</td><td className="text-center tabular-nums text-emerald-700">{c.isEmpty ? "—" : formatDuration(c.shiftMinutes)}</td><td className="text-center tabular-nums text-amber-700">{c.isEmpty ? "—" : formatDuration(c.breakMinutes)}</td><td className="text-center tabular-nums text-sky-700">{c.isEmpty ? "—" : formatDuration(c.netMinutes)}</td></tr>)}</tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog open={editOpen} onOpenChange={setEditOpen}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-hidden p-0">
        <DialogHeader className="border-b px-6 py-4"><DialogTitle>{edit?.id ? "Editar registro de horas" : "Crear registro de horas"}</DialogTitle></DialogHeader>
        {edit ? <div className="max-h-[70vh] space-y-5 overflow-y-auto px-6 py-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5"><Label>Fecha de entrada</Label><Input type="date" value={edit.entryDate} onChange={(e) => setEntryDate(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Fecha de salida</Label><Input type="date" value={edit.exitDate} min={edit.entryDate} onChange={(e) => setExitDate(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Hora de entrada</Label><Input type="time" value={edit.entry} onChange={(e) => setEdit({ ...edit, entry: e.target.value })} /></div>
            <div className="space-y-1.5"><Label>Hora de salida</Label><Input type="time" value={edit.exit} onChange={(e) => setEdit({ ...edit, exit: e.target.value })} /></div>
          </div>
          <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
            <Label>Total de horas trabajadas</Label>
            <div className="grid grid-cols-3 gap-2">
              <Input aria-label="Horas trabajadas" type="number" min={0} placeholder="0" value={edit.shift.hours} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, hours: e.target.value } })} />
              <Input aria-label="Minutos trabajados" type="number" min={0} max={59} placeholder="0" value={edit.shift.minutes} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, minutes: e.target.value } })} />
              <Input aria-label="Segundos trabajados" type="number" min={0} max={59} placeholder="0" value={edit.shift.seconds} onChange={(e) => setEdit({ ...edit, shift: { ...edit.shift, seconds: e.target.value } })} />
            </div>
          </div>
          <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
            <Label>Total de descanso</Label>
            <div className="grid grid-cols-3 gap-2">
              <Input aria-label="Horas de descanso" type="number" min={0} placeholder="0" value={edit.break.hours} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, hours: e.target.value } })} />
              <Input aria-label="Minutos de descanso" type="number" min={0} max={59} placeholder="0" value={edit.break.minutes} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, minutes: e.target.value } })} />
              <Input aria-label="Segundos de descanso" type="number" min={0} max={59} placeholder="0" value={edit.break.seconds} onChange={(e) => setEdit({ ...edit, break: { ...edit.break, seconds: e.target.value } })} />
            </div>
          </div>
          <div className="space-y-1.5"><Label>Motivo</Label><Input value={edit.reason} onChange={(e) => setEdit({ ...edit, reason: e.target.value })} /></div>
        </div> : null}
        <div className="flex justify-end gap-2 border-t px-6 py-4"><Button variant="outline" onClick={() => setEditOpen(false)}>Cancelar</Button><Button onClick={() => void saveEdit()}>Guardar cambios</Button></div>
      </DialogContent>
    </Dialog>

    <ManualTimeCardModal open={manualOpen} onClose={() => setManualOpen(false)} employees={rows.map((r) => ({ id: r.employeeId, name: r.name, role: r.role }))} onSaved={() => { void load(); if (selected) void detail(selected.employee.id); }} />
  </div>;
};
