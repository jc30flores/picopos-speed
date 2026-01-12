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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Employee } from "@/types/employee";
import { toast } from "sonner";

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

interface EmployeeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: Employee | null;
  onSave: (data: Partial<Employee>) => void;
  branches?: string[];
}

export const EmployeeFormDialog = ({
  open,
  onOpenChange,
  employee,
  onSave,
  branches = ["Sucursal Centro", "Sucursal Norte"],
}: EmployeeFormDialogProps) => {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    role: "",
    phone: "",
    branch: "",
    status: "active" as "active" | "inactive",
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
      });
    } else {
      setFormData({
        name: "",
        email: "",
        role: "",
        phone: "",
        branch: "",
        status: "active",
      });
    }
  }, [employee, open]);

  const handleSubmit = () => {
    if (!formData.name || !formData.email || !formData.role || !formData.branch) {
      toast.error("Por favor completa todos los campos obligatorios");
      return;
    }
    if (!ROLE_OPTIONS.some((role) => role.value === formData.role)) {
      toast.error("Selecciona un puesto válido");
      return;
    }

    onSave(formData);
    toast.success(
      employee ? "Empleado actualizado correctamente" : "Empleado agregado correctamente"
    );
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {employee ? "Editar Empleado" : "Nuevo Empleado"}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
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
            <Label htmlFor="phone">Teléfono</Label>
            <Input
              id="phone"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="branch">Sucursal *</Label>
            <Select value={formData.branch} onValueChange={(value) => setFormData({ ...formData, branch: value })}>
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
            <Select value={formData.status} onValueChange={(value: "active" | "inactive") => setFormData({ ...formData, status: value })}>
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
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit}>Guardar</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
