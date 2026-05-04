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
  const [employeeId, setEmployeeId] = useState<string>("");
  const [date, setDate] = useState(formatLocalDate(new Date())); const [clockInTime, setClockInTime] = useState(''); const [breakStartTime, setBreakStartTime] = useState(''); const [breakEndTime, setBreakEndTime] = useState(''); const [clockOutTime, setClockOutTime] = useState('');
  const [saving, setSaving] = useState(false);
  const filtered = useMemo(() => employees.filter((e) => !e.name?.toLowerCase().startsWith('empleado eliminado') && e.role !== 'admin' && e.status !== 'inactive' && !e.isDeleted), [employees]);
  const lockedEmployee = useMemo(() => filtered.find((e) => String(e.id) === String(initialEmployeeId)), [filtered, initialEmployeeId]);

  useEffect(() => {
    if (!open) return;
    if (import.meta.env.DEV) console.debug("manual_time_card.open", { source: lockEmployeeSelection ? "settings" : "reports", initialEmployeeId, lockEmployeeSelection });
    if (initialEmployeeId) {
      setEmployeeId(String(initialEmployeeId));
      return;
    }
    if (!lockEmployeeSelection) {
      setEmployeeId("");
    }
  }, [open, initialEmployeeId, lockEmployeeSelection]);
  const nextDay = !!clockInTime && !!clockOutTime && clockOutTime < clockInTime;
  const submit = async () => {
    const error = validateTimeCardPayload({ employeeId: employeeId ? Number(employeeId) : null, date, clockInTime, breakStartTime, breakEndTime, clockOutTime });
    if (error) return toast.error(error);
    if (import.meta.env.DEV) console.debug("manual_time_card.submit", { employeeId, hasBreak: Boolean(breakStartTime && breakEndTime) });
    setSaving(true);
    try {
      await createEmployeeHoursCycle({ employeeId: Number(employeeId), date, clockInTime, breakStartTime: breakStartTime || null, breakEndTime: breakEndTime || null, clockOutTime, clockOutNextDay: nextDay, reason: 'Registro manual' });
      toast.success('Tarjeta de horas creada correctamente.'); onSaved(); onClose();
    } finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className='max-w-2xl'><DialogHeader><DialogTitle>Nueva Tarjeta de Horas</DialogTitle></DialogHeader>
    <p className='text-xs text-muted-foreground'>Crea un registro manual para un empleado que olvidó marcar entrada, break o salida.</p>
    <div className='grid gap-3 md:grid-cols-2'>
      <div><Label>Empleado</Label><Select value={employeeId} onValueChange={setEmployeeId} disabled={lockEmployeeSelection && Boolean(initialEmployeeId)}><SelectTrigger><SelectValue placeholder={lockEmployeeSelection ? "Cargando empleado..." : "Selecciona empleado"} /></SelectTrigger><SelectContent>{filtered.map((e)=><SelectItem key={e.id} value={String(e.id)}>{e.name} — {formatRole(e.role)}</SelectItem>)}</SelectContent></Select>{lockEmployeeSelection && initialEmployeeId && !lockedEmployee ? <p className='text-xs text-amber-500 mt-1'>Empleado no disponible.</p> : null}</div>
      <div><Label>Fecha</Label><Input type='date' value={date} max={formatLocalDate(new Date())} onChange={(e)=>setDate(e.target.value)} /></div>
      <div><Label>Hora de entrada</Label><Input type='time' value={clockInTime} onChange={(e)=>setClockInTime(e.target.value)} /></div>
      <div><Label>Hora de salida</Label><Input type='time' value={clockOutTime} onChange={(e)=>setClockOutTime(e.target.value)} />{nextDay ? <p className='text-xs text-emerald-500 mt-1'>Salida al día siguiente</p> : null}</div>
      <div><Label>Salida break</Label><Input type='time' value={breakStartTime} onChange={(e)=>setBreakStartTime(e.target.value)} /></div>
      <div><Label>Regreso break</Label><Input type='time' value={breakEndTime} onChange={(e)=>setBreakEndTime(e.target.value)} /></div>
    </div>
    <div className='flex justify-between'><Button variant='outline' onClick={onClose}>Cancelar</Button><Button onClick={() => void submit()} disabled={saving}>Aceptar</Button></div>
  </DialogContent></Dialog>;
}
