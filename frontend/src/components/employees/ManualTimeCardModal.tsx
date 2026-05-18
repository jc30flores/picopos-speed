import { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { createEmployeeHoursCycle } from '@/lib/api';
import { toast } from 'sonner';
import { formatLocalDate, formatRole, validateTimeCardPayload } from './timeCardUtils';

type EmployeeOpt = { id: number; name: string; role?: string; status?: string; isDeleted?: boolean };
export function ManualTimeCardModal({ open, onClose, employees, onSaved, initialEmployeeId, lockEmployeeSelection=false }: { open: boolean; onClose: () => void; employees: EmployeeOpt[]; onSaved: () => void; initialEmployeeId?: number | null; lockEmployeeSelection?: boolean; }) {
  const today = formatLocalDate(new Date());
  const [employeeId, setEmployeeId] = useState<string>("");
  const [entryDate, setEntryDateState] = useState(today);
  const [exitDate, setExitDate] = useState(today);
  const [exitDateEdited, setExitDateEdited] = useState(false);
  const [clockInTime, setClockInTime] = useState('');
  const [breakStartTime, setBreakStartTime] = useState('');
  const [breakEndTime, setBreakEndTime] = useState('');
  const [clockOutTime, setClockOutTime] = useState('');
  const [saving, setSaving] = useState(false);
  const filtered = useMemo(() => employees.filter((e) => !e.name?.toLowerCase().startsWith('empleado eliminado') && e.role !== 'admin' && e.status !== 'inactive' && !e.isDeleted), [employees]);
  const lockedEmployee = useMemo(() => filtered.find((e) => String(e.id) === String(initialEmployeeId)), [filtered, initialEmployeeId]);

  useEffect(() => {
    if (!open) return;
    if (import.meta.env.DEV) console.debug("manual_time_card.open", { source: lockEmployeeSelection ? "settings" : "reports", initialEmployeeId, lockEmployeeSelection });
    setEntryDateState(today);
    setExitDate(today);
    setExitDateEdited(false);
    if (initialEmployeeId) {
      setEmployeeId(String(initialEmployeeId));
      return;
    }
    if (!lockEmployeeSelection) {
      setEmployeeId("");
    }
  }, [open, initialEmployeeId, lockEmployeeSelection, today]);

  const setEntryDate = (value: string) => {
    setEntryDateState(value);
    if (!exitDateEdited) setExitDate(value);
  };

  const nextDay = Boolean(clockOutTime && exitDate > entryDate);
  const submit = async () => {
    const error = validateTimeCardPayload({ employeeId: employeeId ? Number(employeeId) : null, date: entryDate, clockInTime, breakStartTime, breakEndTime, clockOutTime });
    if (error) return toast.error(error);
    if (!exitDate) return toast.error('La fecha de salida es obligatoria.');
    if (exitDate < entryDate) return toast.error('La fecha de salida no puede ser anterior a la fecha de entrada.');
    const entryDateTime = new Date(`${entryDate}T${clockInTime}:00`);
    const exitDateTime = new Date(`${exitDate}T${clockOutTime}:00`);
    if (exitDateTime <= entryDateTime) return toast.error('La salida debe ser posterior a la entrada. Si salió al día siguiente, cambia la fecha de salida.');
    if (import.meta.env.DEV) console.debug("manual_time_card.submit", { employeeId, hasBreak: Boolean(breakStartTime && breakEndTime) });
    setSaving(true);
    try {
      await createEmployeeHoursCycle({ employeeId: Number(employeeId), date: entryDate, clockInTime, breakStartTime: breakStartTime || null, breakEndTime: breakEndTime || null, clockOutTime, clockOutNextDay: nextDay, reason: 'Registro manual' });
      toast.success('Tarjeta de horas creada correctamente.'); onSaved(); onClose();
    } finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className='max-h-[90vh] max-w-2xl overflow-hidden p-0'><DialogHeader className='border-b px-6 py-4'><DialogTitle>Nueva tarjeta de horas</DialogTitle></DialogHeader>
    <div className='max-h-[72vh] space-y-4 overflow-y-auto px-6 py-5'>
      <p className='text-xs text-muted-foreground'>Crea un registro manual para un empleado que olvidó marcar entrada, descanso o salida.</p>
      <div className='grid gap-3 md:grid-cols-2'>
        <div className='space-y-1.5'><Label>Empleado</Label><Select value={employeeId} onValueChange={setEmployeeId} disabled={lockEmployeeSelection && Boolean(initialEmployeeId)}><SelectTrigger><SelectValue placeholder={lockEmployeeSelection ? "Cargando empleado..." : "Selecciona empleado"} /></SelectTrigger><SelectContent>{filtered.map((e)=><SelectItem key={e.id} value={String(e.id)}>{e.name} — {formatRole(e.role)}</SelectItem>)}</SelectContent></Select>{lockEmployeeSelection && initialEmployeeId && !lockedEmployee ? <p className='text-xs text-amber-500 mt-1'>Empleado no disponible.</p> : null}</div>
        <div className='space-y-1.5'><Label>Fecha de entrada</Label><Input type='date' value={entryDate} max={today} onChange={(e)=>setEntryDate(e.target.value)} /></div>
        <div className='space-y-1.5'><Label>Fecha de salida</Label><Input type='date' value={exitDate} min={entryDate} onChange={(e)=>{ setExitDate(e.target.value); setExitDateEdited(true); }} /></div>
        <div className='space-y-1.5'><Label>Hora de entrada</Label><Input type='time' value={clockInTime} onChange={(e)=>setClockInTime(e.target.value)} /></div>
        <div className='space-y-1.5'><Label>Hora de salida</Label><Input type='time' value={clockOutTime} onChange={(e)=>setClockOutTime(e.target.value)} /></div>
        <div className='space-y-1.5'><Label>Salida a descanso</Label><Input type='time' value={breakStartTime} onChange={(e)=>setBreakStartTime(e.target.value)} /></div>
        <div className='space-y-1.5'><Label>Regreso de descanso</Label><Input type='time' value={breakEndTime} onChange={(e)=>setBreakEndTime(e.target.value)} /></div>
      </div>
    </div>
    <div className='flex justify-end gap-2 border-t px-6 py-4'><Button variant='outline' onClick={onClose}>Cancelar</Button><Button onClick={() => void submit()} disabled={saving}>Guardar cambios</Button></div>
  </DialogContent></Dialog>;
}
