export const parseLocalDate = (value: string) => { const [y,m,d]=value.split('-').map(Number); return new Date(y,(m||1)-1,d||1); };
export const formatLocalDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
export const formatRole = (role?: string) => role?.toLowerCase()==='worker' ? 'Team Member' : (role||'—');
export const formatDurationMinutes = (m: number | null | undefined) => { const mm=Math.max(0,Math.round(Number(m||0))); return `${Math.floor(mm/60)}h ${String(mm%60).padStart(2,'0')}m`; };
export const fmtTime = (value?: string | null) => value ? new Date(value).toLocaleTimeString('es-SV',{hour:'2-digit',minute:'2-digit',hour12:false}) : '—';

export const validateTimeCardPayload = (payload: { employeeId?: number | null; date: string; clockInTime: string; breakStartTime: string; breakEndTime: string; clockOutTime: string; }) => {
  if (!payload.employeeId) return 'Selecciona un empleado.';
  if (!payload.date) return 'La fecha es obligatoria.';
  if (!payload.clockInTime) return 'La hora de entrada es obligatoria.';
  if (!payload.clockOutTime) return 'La hora de salida es obligatoria.';
  const today = formatLocalDate(new Date());
  if (payload.date > today) return 'No se pueden crear registros en fechas futuras.';
  if ((payload.breakStartTime && !payload.breakEndTime) || (!payload.breakStartTime && payload.breakEndTime)) return 'Debes completar salida y regreso de break.';
  return null;
};
