import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { createOrderType, deleteOrderType, listOrderTypes, ServiceType, updateOrderType } from "@/lib/api";
import { toast } from "sonner";

const normalizeKey = (value: string) =>
  value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

export const OrderTypesTab = () => {
  const [items, setItems] = useState<ServiceType[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [editing, setEditing] = useState<ServiceType | null>(null);
  const [name, setName] = useState("");
  const [keyValue, setKeyValue] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [isActive, setIsActive] = useState(true);
  const [disposablesEnabled, setDisposablesEnabled] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const load = async () => {
    try {
      setItems(await listOrderTypes());
    } catch (error) {
      console.error("Failed to load order types", error);
      toast.error("No se pudieron cargar los tipos de pedido");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const sorted = useMemo(
    () => [...items].sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.label.localeCompare(b.label)),
    [items],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setKeyValue("");
    setSortOrder("0");
    setIsActive(true);
    setDisposablesEnabled(false);
    setIsOpen(true);
  };

  const openEdit = (item: ServiceType) => {
    setEditing(item);
    setName(item.label);
    setKeyValue(item.key);
    setSortOrder(String(item.sortOrder ?? 0));
    setIsActive(item.isActive !== false);
    setDisposablesEnabled(item.disposablesEnabled === true);
    setIsOpen(true);
  };

  const onSave = async () => {
    const label = name.trim();
    const key = normalizeKey(keyValue || name);
    if (!label || !key) {
      toast.error("Nombre y código son requeridos");
      return;
    }
    setIsSaving(true);
    try {
      if (editing) {
        await updateOrderType(editing.id, {
          label,
          key,
          sortOrder: Number(sortOrder || 0),
          isActive,
          disposablesEnabled,
        });
      } else {
        await createOrderType({
          label,
          key,
          sortOrder: Number(sortOrder || 0),
          isActive,
          disposablesEnabled,
        });
      }
      setIsOpen(false);
      await load();
      toast.success("Tipo guardado");
    } catch (error) {
      console.error("Failed to save order type", error);
      toast.error("No se pudo guardar el tipo");
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async (item: ServiceType) => {
    if (!window.confirm(`Este tipo se desasignará de órdenes existentes y luego se eliminará: ${item.label}`)) return;
    try {
      await deleteOrderType(item.id);
      await load();
      toast.success("Tipo eliminado");
    } catch (error) {
      console.error("Failed to delete order type", error);
      toast.error("No se pudo eliminar el tipo");
    }
  };

  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Tipos de Pedido</h3>
          <p className="text-sm text-muted-foreground">Gestiona los tipos usados en POS, cocina y pantallas de clientes.</p>
        </div>
        <Button onClick={openCreate}>Nuevo tipo</Button>
      </div>

      <div className="space-y-2">
        {sorted.map((item) => (
          <div key={item.id} className="rounded-xl border p-3 flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold">{item.label}</p>
              <p className="text-xs text-muted-foreground">{item.key} · Orden: {item.sortOrder ?? 0} · {item.isActive ? "Activo" : "Inactivo"} · Desechables: {item.disposablesEnabled ? "ON" : "OFF"}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => openEdit(item)}>Editar</Button>
              <Button variant="destructive" onClick={() => onDelete(item)}>Eliminar</Button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Editar tipo" : "Nuevo tipo"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Nombre</Label>
              <Input value={name} onChange={(e) => { setName(e.target.value); if (!editing) setKeyValue(normalizeKey(e.target.value)); }} />
            </div>
            <div className="space-y-1">
              <Label>Código</Label>
              <Input value={keyValue} onChange={(e) => setKeyValue(normalizeKey(e.target.value))} />
            </div>
            <div className="space-y-1">
              <Label>Orden</Label>
              <Input type="number" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
            </div>
            <div className="flex items-center justify-between">
              <Label>Activo</Label>
              <Switch checked={isActive} onCheckedChange={setIsActive} />
            </div>
            <div className="flex items-center justify-between">
              <Label>Aplicar desechables</Label>
              <Switch checked={disposablesEnabled} onCheckedChange={setDisposablesEnabled} />
            </div>
            <Button onClick={onSave} disabled={isSaving} className="w-full">{isSaving ? "Guardando..." : "Guardar"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
};
