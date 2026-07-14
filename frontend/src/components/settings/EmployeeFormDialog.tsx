import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Employee } from "@/types/employee";
import { toast } from "sonner";
import { PinKeypad } from "@/components/auth/PinKeypad";

const ROLE_OPTIONS = [
  { value: "cashier", label: "Cajero" },
  { value: "waiter", label: "Mesero" },
  { value: "kitchen", label: "Cocina" },
  { value: "manager", label: "Gerente" },
  { value: "admin", label: "Administrador" },
  { value: "kiosk", label: "Kiosk" },
  { value: "worker", label: "Worker" },
];

const ROLE_KEY_BY_LABEL = ROLE_OPTIONS.reduce((acc, option) => {
  acc[option.label.toLowerCase()] = option.value;
  return acc;
}, {} as Record<string, string>);

const PIN_LENGTH = 6;
const sanitizePin = (value: string) => value.replace(/\D/g, "").slice(0, PIN_LENGTH);
const isValidPin = (value: string) => /^\d{6}$/.test(value);

export interface EmployeeFormData extends Partial<Employee> {
  username?: string;
  userPassword?: string;
  userPasswordConfirm?: string;
}

interface EmployeeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: Employee | null;
  onSave: (data: EmployeeFormData) => Promise<void>;
}

export const EmployeeFormDialog = ({
  open,
  onOpenChange,
  employee,
  onSave,
}: EmployeeFormDialogProps) => {
  const [showPinKeypad, setShowPinKeypad] = useState(false);
  const [pinTarget, setPinTarget] = useState<"pin" | "confirm">("pin");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formData, setFormData] = useState({
    name: "",
    username: "",
    role: "",
    status: "active" as "active" | "inactive",
    userPassword: "",
    userPasswordConfirm: "",
  });

  useEffect(() => {
    if (employee) {
      setFormData({
        name: employee.name,
        username: employee.userUsername ?? "",
        role: ROLE_KEY_BY_LABEL[employee.role.toLowerCase()] ?? employee.role,
        status: employee.status,
        userPassword: "",
        userPasswordConfirm: "",
      });
    } else {
      setFormData({
        name: "",
        username: "",
        role: "",
        status: "active",
        userPassword: "",
        userPasswordConfirm: "",
      });
    }
    setFieldErrors({});
    setShowPinKeypad(false);
    setPinTarget("pin");
  }, [employee, open]);

  const pinError =
    formData.userPassword.length > 0 && !isValidPin(formData.userPassword)
      ? "El PIN debe tener exactamente 6 dígitos numéricos"
      : "";

  const confirmPinError =
    formData.userPasswordConfirm.length > 0 && !isValidPin(formData.userPasswordConfirm)
      ? "Confirmación inválida: deben ser 6 dígitos"
      : "";

  const parseApiError = (message: string): Record<string, unknown> | null => {
    try {
      const parsed = JSON.parse(message);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  };

  const handleSubmit = async () => {
    setFieldErrors({});
    if (!formData.name || !formData.username || !formData.role) {
      toast.error("Por favor completa todos los campos obligatorios");
      return;
    }
    if (!ROLE_OPTIONS.some((role) => role.value === formData.role)) {
      toast.error("Selecciona un rol válido");
      return;
    }
    if (!formData.userPassword || !formData.userPasswordConfirm) {
      toast.error("Completa el PIN y su confirmación");
      return;
    }
    if (!isValidPin(formData.userPassword) || !isValidPin(formData.userPasswordConfirm)) {
      toast.error("El PIN debe contener exactamente 6 dígitos");
      return;
    }
    if (formData.userPassword !== formData.userPasswordConfirm) {
      toast.error("Los PIN no coinciden");
      return;
    }

    try {
      setSubmitting(true);
      await onSave(formData);
      toast.success(employee ? "Usuario actualizado correctamente" : "Usuario creado correctamente");
      onOpenChange(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar el usuario";
      const parsed = parseApiError(message);
      if (parsed) {
        const nextErrors: Record<string, string> = {};
        const userError = parsed.user as Record<string, string | string[]> | undefined;
        if (parsed.full_name) nextErrors.name = String(Array.isArray(parsed.full_name) ? parsed.full_name[0] : parsed.full_name);
        if (parsed.role) nextErrors.role = String(Array.isArray(parsed.role) ? parsed.role[0] : parsed.role);
        if (userError?.username) nextErrors.username = String(Array.isArray(userError.username) ? userError.username[0] : userError.username);
        if (userError?.password) nextErrors.userPassword = String(Array.isArray(userError.password) ? userError.password[0] : userError.password);
        setFieldErrors(nextErrors);
      }
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[96vw] max-w-[640px] max-h-[90vh] p-0 overflow-hidden">
        <div className="flex h-full flex-col">
          <div className="sticky top-0 z-10 border-b border-border bg-background px-5 py-4">
            <DialogHeader>
              <DialogTitle>{employee ? "Editar Usuario" : "Nuevo Empleado / Usuario"}</DialogTitle>
            </DialogHeader>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Nombre *</Label>
                <Input id="name" className="h-11 text-base" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} />
                {fieldErrors.name ? <p className="text-xs text-destructive">{fieldErrors.name}</p> : null}
              </div>

              <div className="grid gap-2">
                <Label htmlFor="username">Usuario *</Label>
                <Input id="username" className="h-11 text-base" value={formData.username} onChange={(e) => setFormData({ ...formData, username: e.target.value })} />
                {fieldErrors.username ? <p className="text-xs text-destructive">{fieldErrors.username}</p> : null}
              </div>

              <div className="grid gap-2">
                <Label htmlFor="role">Rol *</Label>
                <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })}>
                  <SelectTrigger className="h-11 text-base">
                    <SelectValue placeholder="Seleccionar rol" />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_OPTIONS.map((role) => (
                      <SelectItem key={role.value} value={role.value}>
                        {role.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {fieldErrors.role ? <p className="text-xs text-destructive">{fieldErrors.role}</p> : null}
              </div>

              <div className="grid gap-2">
                <Label htmlFor="status">Estado</Label>
                <Select value={formData.status} onValueChange={(value: "active" | "inactive") => setFormData({ ...formData, status: value })}>
                  <SelectTrigger className="h-11 text-base">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Activo</SelectItem>
                    <SelectItem value="inactive">Inactivo</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3 rounded-lg border border-border p-4">
                <p className="text-sm font-medium">Seguridad de acceso (PIN numérico de 6 dígitos)</p>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="userPassword">PIN / Código *</Label>
                    <Input
                      id="userPassword"
                      type="password"
                      inputMode="numeric"
                      className="h-11 text-base"
                      maxLength={PIN_LENGTH}
                      value={formData.userPassword}
                      onFocus={() => setPinTarget("pin")}
                      onChange={(e) => setFormData({ ...formData, userPassword: sanitizePin(e.target.value) })}
                    />
                    {pinError ? <p className="text-xs text-destructive">{pinError}</p> : null}
                    {!pinError && fieldErrors.userPassword ? <p className="text-xs text-destructive">{fieldErrors.userPassword}</p> : null}
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="userPasswordConfirm">Confirmar PIN *</Label>
                    <Input
                      id="userPasswordConfirm"
                      type="password"
                      inputMode="numeric"
                      className="h-11 text-base"
                      maxLength={PIN_LENGTH}
                      value={formData.userPasswordConfirm}
                      onFocus={() => setPinTarget("confirm")}
                      onChange={(e) => setFormData({ ...formData, userPasswordConfirm: sanitizePin(e.target.value) })}
                    />
                    {confirmPinError ? <p className="text-xs text-destructive">{confirmPinError}</p> : null}
                    {!confirmPinError &&
                    formData.userPasswordConfirm.length === PIN_LENGTH &&
                    formData.userPassword &&
                    formData.userPasswordConfirm !== formData.userPassword ? (
                      <p className="text-xs text-destructive">Los PIN no coinciden</p>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 rounded-md bg-muted/40 p-3">
                  <p className="text-xs text-muted-foreground">Entrada táctil para PIN</p>
                  <Button type="button" size="sm" variant="outline" onClick={() => setShowPinKeypad((prev) => !prev)}>
                    {showPinKeypad ? "Ocultar teclado" : "Abrir teclado táctil"}
                  </Button>
                </div>

                {showPinKeypad ? (
                  <div className="space-y-3 rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" size="sm" variant={pinTarget === "pin" ? "default" : "outline"} onClick={() => setPinTarget("pin")}>PIN</Button>
                      <Button type="button" size="sm" variant={pinTarget === "confirm" ? "default" : "outline"} onClick={() => setPinTarget("confirm")}>Confirmar PIN</Button>
                    </div>
                    <PinKeypad
                      value={pinTarget === "pin" ? formData.userPassword : formData.userPasswordConfirm}
                      onChange={(next) => {
                        setFormData((prev) =>
                          pinTarget === "pin"
                            ? { ...prev, userPassword: sanitizePin(next) }
                            : { ...prev, userPasswordConfirm: sanitizePin(next) }
                        );
                      }}
                      maxLength={PIN_LENGTH}
                      compact
                    />
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="sticky bottom-0 z-10 border-t border-border bg-background px-5 py-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button disabled={submitting} onClick={handleSubmit}>
              {employee ? "Guardar cambios" : "Crear usuario"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
