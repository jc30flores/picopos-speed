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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Employee } from "@/types/employee";
import { toast } from "sonner";
import { PinKeypad } from "@/components/auth/PinKeypad";

const ROLE_OPTIONS = [
  { value: "cashier", label: "Cajero" },
  { value: "kitchen", label: "Cocinero" },
  { value: "manager", label: "Gerente" },
  { value: "admin", label: "Administrador" },
];

const ROLE_KEY_BY_LABEL = ROLE_OPTIONS.reduce((acc, option) => {
  acc[option.label.toLowerCase()] = option.value;
  return acc;
}, {} as Record<string, string>);

const PIN_LENGTH = 6;

const sanitizePin = (value: string) => value.replace(/\D/g, "").slice(0, PIN_LENGTH);
const isValidPin = (value: string) => /^\d{6}$/.test(value);

export interface EmployeeFormData extends Partial<Employee> {
  createUser?: boolean;
  userIdentifier?: string;
  userPassword?: string;
  userPasswordConfirm?: string;
  userRole?: string;
}

interface EmployeeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: Employee | null;
  onSave: (data: EmployeeFormData) => void;
  branches?: string[];
}

export const EmployeeFormDialog = ({
  open,
  onOpenChange,
  employee,
  onSave,
  branches = ["Sucursal Centro", "Sucursal Norte"],
}: EmployeeFormDialogProps) => {
  const [showPinKeypad, setShowPinKeypad] = useState(false);
  const [pinTarget, setPinTarget] = useState<"pin" | "confirm">("pin");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    role: "",
    phone: "",
    branch: "",
    status: "active" as "active" | "inactive",
    createUser: false,
    userIdentifier: "",
    userPassword: "",
    userPasswordConfirm: "",
    userRole: "",
  });

  useEffect(() => {
    if (employee) {
      setFormData({
        name: employee.name,
        email: employee.email,
        role: ROLE_KEY_BY_LABEL[employee.role.toLowerCase()] ?? employee.role,
        phone: employee.phone,
        branch: employee.branch,
        status: employee.status,
        createUser: employee.hasUser ?? false,
        userIdentifier: employee.userUsername ?? employee.userEmail ?? "",
        userPassword: "",
        userPasswordConfirm: "",
        userRole: ROLE_KEY_BY_LABEL[employee.userRole?.toLowerCase() ?? ""] ?? "",
      });
    } else {
      setFormData({
        name: "",
        email: "",
        role: "",
        phone: "",
        branch: "",
        status: "active",
        createUser: false,
        userIdentifier: "",
        userPassword: "",
        userPasswordConfirm: "",
        userRole: "",
      });
    }
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

  const handleSubmit = () => {
    if (!formData.name || !formData.email || !formData.role || !formData.branch) {
      toast.error("Por favor completa todos los campos obligatorios");
      return;
    }
    if (!ROLE_OPTIONS.some((role) => role.value === formData.role)) {
      toast.error("Selecciona un puesto válido");
      return;
    }
    if (formData.createUser) {
      if (!formData.userIdentifier) {
        toast.error("Completa los datos de acceso");
        return;
      }
      if (!ROLE_OPTIONS.some((role) => role.value === formData.userRole)) {
        toast.error("Selecciona un rol del sistema válido");
        return;
      }
      if (!employee?.hasUser) {
        if (!formData.userPassword || !formData.userPasswordConfirm) {
          toast.error("Completa el PIN para crear el usuario");
          return;
        }
      }
      if (formData.userPassword || formData.userPasswordConfirm) {
        if (!isValidPin(formData.userPassword) || !isValidPin(formData.userPasswordConfirm)) {
          toast.error("El PIN debe contener exactamente 6 dígitos");
          return;
        }
        if (formData.userPassword !== formData.userPasswordConfirm) {
          toast.error("Los PIN no coinciden");
          return;
        }
      }
    }

    onSave(formData);
    toast.success(
      employee
        ? "Empleado actualizado correctamente"
        : formData.createUser
          ? "Empleado y usuario creados correctamente"
          : "Empleado creado correctamente"
    );
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-[860px] max-h-[calc(100dvh-2rem)] p-0 overflow-hidden">
        <div className="flex h-full flex-col">
          <div className="border-b border-border px-5 py-4">
            <DialogHeader>
              <DialogTitle>
                {employee ? "Editar Empleado" : "Nuevo Empleado"}
              </DialogTitle>
            </DialogHeader>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
            <div className="grid gap-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold">Datos del empleado</p>
                <p className="text-xs text-muted-foreground">
                  Información básica para administrar al personal.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="grid gap-2 md:col-span-2">
                  <Label htmlFor="name">Nombre *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="phone">Teléfono</Label>
                  <Input
                    id="phone"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="role">Puesto *</Label>
                  <Select
                    value={formData.role}
                    onValueChange={(value) => setFormData({ ...formData, role: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar puesto" />
                    </SelectTrigger>
                    <SelectContent>
                      {ROLE_OPTIONS.map((role) => (
                        <SelectItem key={role.value} value={role.value}>
                          {role.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="branch">Sucursal *</Label>
                  <Select
                    value={formData.branch}
                    onValueChange={(value) => setFormData({ ...formData, branch: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar sucursal" />
                    </SelectTrigger>
                    <SelectContent>
                      {branches.map((branch) => (
                        <SelectItem key={branch} value={branch}>
                          {branch}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="status">Estado</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value: "active" | "inactive") =>
                      setFormData({ ...formData, status: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Activo</SelectItem>
                      <SelectItem value="inactive">Inactivo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2 border-t border-border pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold">Acceso al sistema</p>
                    <p className="text-xs text-muted-foreground">
                      Este usuario podrá iniciar sesión en el sistema.
                    </p>
                  </div>
                  <Switch
                    checked={formData.createUser}
                    onCheckedChange={(checked) =>
                      setFormData({ ...formData, createUser: checked })
                    }
                  />
                </div>

                {formData.createUser && (
                  <div className="grid gap-3 pt-2 md:grid-cols-2">
                    <div className="grid gap-2 md:col-span-2">
                      <Label htmlFor="userIdentifier">Usuario / Email de acceso *</Label>
                      <Input
                        id="userIdentifier"
                        value={formData.userIdentifier}
                        onChange={(e) =>
                          setFormData({ ...formData, userIdentifier: e.target.value })
                        }
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="userPassword">
                        {employee?.hasUser ? "PIN (6 dígitos) (opcional)" : "PIN (6 dígitos) *"}
                      </Label>
                      <Input
                        id="userPassword"
                        type="password"
                        inputMode="numeric"
                        pattern="\\d{6}"
                        maxLength={PIN_LENGTH}
                        value={formData.userPassword}
                        onChange={(e) =>
                          setFormData({ ...formData, userPassword: sanitizePin(e.target.value) })
                        }
                      />
                      {pinError ? <p className="text-xs text-destructive">{pinError}</p> : null}
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="userPasswordConfirm">
                        {employee?.hasUser ? "Confirmar PIN (opcional)" : "Confirmar PIN *"}
                      </Label>
                      <Input
                        id="userPasswordConfirm"
                        type="password"
                        inputMode="numeric"
                        pattern="\\d{6}"
                        maxLength={PIN_LENGTH}
                        value={formData.userPasswordConfirm}
                        onChange={(e) =>
                          setFormData({ ...formData, userPasswordConfirm: sanitizePin(e.target.value) })
                        }
                      />
                      {confirmPinError ? <p className="text-xs text-destructive">{confirmPinError}</p> : null}
                    </div>
                    <div className="md:col-span-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowPinKeypad((prev) => !prev)}
                      >
                        {showPinKeypad ? "Ocultar teclado táctil" : "Abrir teclado táctil"}
                      </Button>
                    </div>
                    {showPinKeypad ? (
                      <div className="grid gap-2 md:col-span-2 rounded-md border p-3">
                        <div className="flex gap-2">
                          <Button type="button" size="sm" variant={pinTarget === "pin" ? "default" : "outline"} onClick={() => setPinTarget("pin")}>PIN</Button>
                          <Button type="button" size="sm" variant={pinTarget === "confirm" ? "default" : "outline"} onClick={() => setPinTarget("confirm")}>Confirmar PIN</Button>
                        </div>
                        <PinKeypad
                          value={pinTarget === "pin" ? formData.userPassword : formData.userPasswordConfirm}
                          onChange={(next) =>
                            setFormData((prev) =>
                              pinTarget === "pin"
                                ? { ...prev, userPassword: sanitizePin(next) }
                                : { ...prev, userPasswordConfirm: sanitizePin(next) }
                            )
                          }
                          maxLength={PIN_LENGTH}
                        />
                      </div>
                    ) : null}
                    <div className="grid gap-2 md:col-span-2">
                      <Label htmlFor="userRole">Rol del sistema *</Label>
                      <Select
                        value={formData.userRole}
                        onValueChange={(value) => setFormData({ ...formData, userRole: value })}
                      >
                        <SelectTrigger>
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
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="sticky bottom-0 border-t border-border bg-background px-5 py-4">
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button onClick={handleSubmit}>Guardar</Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
