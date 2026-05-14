import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  createPaymentMethod,
  deletePaymentMethod,
  getPaymentMethods,
  listOrderTypes,
  PaymentMethodOption,
  ServiceType,
  updatePaymentMethod,
} from "@/lib/api";
import { getReadableTextColor, isValidHexColor } from "@/lib/color";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const COLOR_PALETTE = ["#16A34A", "#2563EB", "#F97316", "#DC2626", "#7C3AED", "#0891B2", "#CA8A04", "#DB2777", "#0F766E", "#334155"];

const FISCAL_LABELS: Record<NonNullable<PaymentMethodOption["fiscalPaymentType"]>, string> = {
  CASH: "Efectivo",
  CARD: "Tarjeta",
  TRANSFER: "Transferencia",
};

const emptyForm = {
  name: "",
  code: "",
  sortOrder: "0",
  isActive: true,
  isCash: false,
  fiscalPaymentType: "TRANSFER" as NonNullable<PaymentMethodOption["fiscalPaymentType"]>,
  colorHex: "#16A34A",
  isDefault: false,
  linkedOrderTypeId: "__none",
};

const normalizeCode = (value: string) =>
  value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();

export const PaymentMethodsTab = () => {
  const [items, setItems] = useState<PaymentMethodOption[]>([]);
  const [orderTypes, setOrderTypes] = useState<ServiceType[]>([]);
  const [editing, setEditing] = useState<PaymentMethodOption | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    try {
      const [methods, types] = await Promise.all([getPaymentMethods(), listOrderTypes()]);
      setItems(methods);
      setOrderTypes(types);
    } catch (error) {
      console.error("Failed to load payment methods", error);
      toast.error("No se pudieron cargar los métodos de pago");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const sorted = useMemo(
    () => [...items].filter((item) => item.isActive !== false).sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.name.localeCompare(b.name)),
    [items],
  );

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm, sortOrder: String((items.at(-1)?.sortOrder ?? 0) + 1) });
    setIsOpen(true);
  };

  const openEdit = (item: PaymentMethodOption) => {
    setEditing(item);
    setForm({
      name: item.name,
      code: item.code,
      sortOrder: String(item.sortOrder ?? 0),
      isActive: item.isActive !== false,
      isCash: item.isCash === true,
      fiscalPaymentType: item.fiscalPaymentType || (item.isCash ? "CASH" : "TRANSFER"),
      colorHex: item.colorHex || "#16A34A",
      isDefault: item.isDefault === true,
      linkedOrderTypeId: item.linkedOrderTypeId ? String(item.linkedOrderTypeId) : "__none",
    });
    setIsOpen(true);
  };

  const colorUsers = useMemo(() => {
    if (!isValidHexColor(form.colorHex)) return [] as string[];
    const normalized = form.colorHex.toUpperCase();
    const usedByMethods = items
      .filter((item) => item.id !== editing?.id && (item.colorHex || "").toUpperCase() === normalized)
      .map((item) => `Método: ${item.name}`);
    const usedByTypes = orderTypes
      .filter((type) => (type.colorHex || "").toUpperCase() === normalized)
      .map((type) => `Tipo: ${type.label}`);
    return [...usedByMethods, ...usedByTypes];
  }, [editing?.id, form.colorHex, items, orderTypes]);

  const onSave = async () => {
    const name = form.name.trim();
    const code = normalizeCode(form.code || form.name);
    const colorHex = form.colorHex.trim().toUpperCase();
    if (!name || !code) {
      toast.error("Nombre y código son requeridos");
      return;
    }
    if (colorHex && !isValidHexColor(colorHex)) {
      toast.error("Usa un color HEX válido (#RRGGBB)");
      return;
    }
    if (form.isDefault && !form.isActive) {
      toast.error("El método default debe estar activo");
      return;
    }

    setIsSaving(true);
    try {
      const payload: Partial<PaymentMethodOption> & { name: string; code?: string } = {
        name,
        sortOrder: Number(form.sortOrder || 0),
        isActive: form.isActive,
        isCash: form.fiscalPaymentType === "CASH",
        fiscalPaymentType: form.fiscalPaymentType,
        colorHex: colorHex || null,
        isDefault: form.isDefault,
        linkedOrderTypeId: form.linkedOrderTypeId === "__none" ? null : Number(form.linkedOrderTypeId),
      };
      if (!editing || normalizeCode(editing.code) !== code) {
        payload.code = code;
      }
      if (editing) {
        await updatePaymentMethod(editing.id, payload);
      } else {
        await createPaymentMethod(payload);
      }
      setIsOpen(false);
      await load();
      window.dispatchEvent(new CustomEvent("payment-methods:changed"));
      toast.success("Método guardado");
    } catch (error) {
      console.error("Failed to save payment method", error);
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el método");
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async (item: PaymentMethodOption) => {
    if (!window.confirm(`¿Eliminar el método ${item.name}? Si tiene ventas asociadas, el sistema pedirá desactivarlo.`)) return;
    try {
      const result = await deletePaymentMethod(item.id);
      await load();
      window.dispatchEvent(new CustomEvent("payment-methods:changed"));
      toast.success(result.hidden ? (result.detail || "Método ocultado del POS. Las ventas históricas se conservaron.") : "Método eliminado");
    } catch (error) {
      console.error("Failed to delete payment method", error);
      toast.error(error instanceof Error ? error.message : "No se pudo eliminar el método");
    }
  };

  return (
    <Card className="space-y-4 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold">Métodos de Pago</h3>
          <p className="text-sm text-muted-foreground">Configura métodos, colores, default y vínculo automático con tipos de pedido.</p>
        </div>
        <Button onClick={openCreate}>Nuevo método</Button>
      </div>

      <div className="space-y-2">
        {sorted.map((item) => {
          const color = item.colorHex && isValidHexColor(item.colorHex) ? item.colorHex : "";
          return (
            <div key={item.id} className="flex flex-col gap-3 rounded-xl border p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="h-4 w-4 rounded-full border shadow-sm" style={color ? { backgroundColor: color } : undefined} />
                  <p className="font-semibold">{item.name}</p>
                  {item.isDefault ? <Badge>Default</Badge> : null}
                  <Badge variant="secondary">{FISCAL_LABELS[item.fiscalPaymentType || "TRANSFER"]}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {item.code} · Orden: {item.sortOrder ?? 0} · {item.isActive ? "Activo" : "Oculto/Inactivo"} · Vinculado: {item.linkedOrderTypeName || "Sin vínculo"}
                </p>
              </div>
              <div className="flex gap-2 sm:shrink-0">
                <Button variant="outline" onClick={() => openEdit(item)}>Editar</Button>
                <Button variant="destructive" onClick={() => void onDelete(item)}>Eliminar</Button>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 ? <div className="rounded-xl border p-6 text-center text-sm text-muted-foreground">No hay métodos configurados.</div> : null}
      </div>

      <Dialog open={isOpen} onOpenChange={(open) => !isSaving && setIsOpen(open)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar método" : "Nuevo método"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <Label>Nombre</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value, code: editing ? prev.code : normalizeCode(event.target.value) }))} />
            </div>
            <div className="space-y-1">
              <Label>Código</Label>
              <Input value={form.code} onChange={(event) => setForm((prev) => ({ ...prev, code: normalizeCode(event.target.value) }))} />
            </div>
            <div className="space-y-1">
              <Label>Orden</Label>
              <Input type="number" value={form.sortOrder} onChange={(event) => setForm((prev) => ({ ...prev, sortOrder: event.target.value }))} />
            </div>
            <div className="flex items-center justify-between rounded-xl border p-3">
              <Label>Activo</Label>
              <Switch checked={form.isActive} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, isActive: checked, isDefault: checked ? prev.isDefault : false }))} />
            </div>
            <div className="flex items-center justify-between rounded-xl border p-3">
              <div>
                <Label>Categoría fiscal</Label>
                <p className="text-xs text-muted-foreground">Define el código DTE: efectivo, tarjeta o transferencia.</p>
              </div>
              <Select value={form.fiscalPaymentType} onValueChange={(value) => setForm((prev) => ({ ...prev, fiscalPaymentType: value as NonNullable<PaymentMethodOption["fiscalPaymentType"]>, isCash: value === "CASH" }))}>
                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="CASH">Efectivo</SelectItem>
                  <SelectItem value="CARD">Tarjeta</SelectItem>
                  <SelectItem value="TRANSFER">Transferencia</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-xl border p-3">
              <div>
                <Label>Método Default</Label>
                <p className="text-xs text-muted-foreground">Se selecciona al abrir una venta si no hay vínculo del tipo.</p>
              </div>
              <Switch checked={form.isDefault} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, isDefault: checked, isActive: checked ? true : prev.isActive }))} />
            </div>
            <div className="space-y-1">
              <Label>Vincular automáticamente a Tipo de Pedido</Label>
              <Select value={form.linkedOrderTypeId} onValueChange={(value) => setForm((prev) => ({ ...prev, linkedOrderTypeId: value }))}>
                <SelectTrigger><SelectValue placeholder="Sin vínculo" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">Sin vínculo</SelectItem>
                  {orderTypes.map((type) => (
                    <SelectItem key={type.id} value={String(type.id)}>{type.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3 rounded-xl border p-3 sm:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <Label>Color</Label>
                  <p className="text-xs text-muted-foreground">Toca un color rápido o escribe uno custom.</p>
                </div>
                {isValidHexColor(form.colorHex) ? (
                  <div className="rounded-full px-4 py-2 text-sm font-semibold" style={{ backgroundColor: form.colorHex, color: getReadableTextColor(form.colorHex) }}>
                    {form.name || "Vista previa"}
                  </div>
                ) : null}
              </div>
              <div className="grid grid-cols-5 gap-2 sm:grid-cols-10">
                {COLOR_PALETTE.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={cn("h-11 rounded-xl border shadow-sm transition active:scale-95", form.colorHex.toUpperCase() === color && "ring-2 ring-primary ring-offset-2 ring-offset-background")}
                    style={{ backgroundColor: color }}
                    aria-label={`Usar color ${color}`}
                    onClick={() => setForm((prev) => ({ ...prev, colorHex: color }))}
                  />
                ))}
              </div>
              <div className="flex gap-2">
                <Input value={form.colorHex} onChange={(event) => setForm((prev) => ({ ...prev, colorHex: event.target.value.toUpperCase() }))} placeholder="#16A34A" maxLength={7} />
                <Button type="button" variant="outline" onClick={() => setForm((prev) => ({ ...prev, colorHex: "" }))}>Sin color</Button>
              </div>
              {form.colorHex && !isValidHexColor(form.colorHex) ? <p className="text-xs text-destructive">Usa formato HEX #RRGGBB.</p> : null}
              {colorUsers.length > 0 ? <p className="text-xs text-amber-600 dark:text-amber-400">Actualmente usado por: {colorUsers.join(", ")}</p> : null}
            </div>
            <Button onClick={() => void onSave()} disabled={isSaving} className="sm:col-span-2">{isSaving ? "Guardando..." : "Guardar"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
};
