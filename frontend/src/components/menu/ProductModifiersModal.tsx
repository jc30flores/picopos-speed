import { useEffect, useMemo, useState } from "react";
import { GripVertical, Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ModifierGroup, Product, reorderProductModifierGroups, updateProductModifierGroups } from "@/lib/api";
import { toast } from "sonner";
import { useReorderableList } from "@/hooks/useReorderableList";

interface ProductModifiersModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedProduct: Product | null;
  modifierGroups: ModifierGroup[];
  onUpdated: (productId?: number) => Promise<void>;
}

export const ProductModifiersModal = ({
  open,
  onOpenChange,
  selectedProduct,
  modifierGroups,
  onUpdated,
}: ProductModifiersModalProps) => {
  const [assignedGroups, setAssignedGroups] = useState<number[]>([]);
  const [selectedForAssign, setSelectedForAssign] = useState<number[]>([]);
  const [showAssignDialog, setShowAssignDialog] = useState(false);
  const [draggingGroupId, setDraggingGroupId] = useState<number | null>(null);
  const [isSavingOrder, setIsSavingOrder] = useState(false);
  const [assignedGroupVisibility, setAssignedGroupVisibility] = useState<Record<number, boolean>>({});
  const groupOrder = useReorderableList(assignedGroups, (groupId) => groupId);

  useEffect(() => {
    if (!selectedProduct) {
      setAssignedGroups([]);
      setAssignedGroupVisibility({});
      return;
    }
    setAssignedGroups(selectedProduct.modifierGroups ?? []);
    const visibility = (selectedProduct.modifierGroupLinks ?? []).reduce<Record<number, boolean>>((acc, link) => {
      acc[link.groupId] = Boolean(link.showInPos);
      return acc;
    }, {});
    setAssignedGroupVisibility(visibility);
  }, [selectedProduct]);

  const defaultShowInPos = (groupId: number) => {
    const group = modifierGroups.find((candidate) => candidate.id === groupId);
    if (!group) return false;
    return group.modifiers.some((modifier) => modifier.price > 0);
  };

  const assignedGroupObjects = useMemo(() => modifierGroups.filter((group) =>
    assignedGroups.includes(group.id)
  ), [modifierGroups, assignedGroups]);

  const orderedAssignedGroups = useMemo(() => [...assignedGroupObjects].sort(
    (a, b) => assignedGroups.indexOf(a.id) - assignedGroups.indexOf(b.id)
  ), [assignedGroupObjects, assignedGroups]);

  const handleAssignGroups = async () => {
    if (!selectedProduct) return;
    const duplicate = selectedForAssign.find((id) => assignedGroups.includes(id));
    if (duplicate) {
      toast.error("Ese grupo ya está asignado");
      return;
    }
    const nextGroupIds = [...new Set([...assignedGroups, ...selectedForAssign])];
    const links = nextGroupIds.map((groupId) => ({
      groupId,
      showInPos: assignedGroupVisibility[groupId] ?? defaultShowInPos(groupId),
    }));
    try {
      await updateProductModifierGroups(selectedProduct.id, nextGroupIds, links);
      setAssignedGroupVisibility((prev) => {
        const next = { ...prev };
        for (const link of links) next[link.groupId] = link.showInPos;
        return next;
      });
      await onUpdated(selectedProduct.id);
      setShowAssignDialog(false);
      setSelectedForAssign([]);
      toast.success("Grupos asignados correctamente");
    } catch {
      toast.error("No se pudieron asignar los grupos");
    }
  };

  const handleRemoveGroup = async (groupId: number) => {
    if (!selectedProduct) return;
    const nextGroupIds = assignedGroups.filter((id) => id !== groupId);
    const links = nextGroupIds.map((id) => ({
      groupId: id,
      showInPos: assignedGroupVisibility[id] ?? defaultShowInPos(id),
    }));
    try {
      await updateProductModifierGroups(selectedProduct.id, nextGroupIds, links);
      setAssignedGroupVisibility((prev) => {
        const next = { ...prev };
        delete next[groupId];
        return next;
      });
      await onUpdated(selectedProduct.id);
      toast.success("Grupo removido correctamente");
    } catch {
      toast.error("No se pudo remover el grupo");
    }
  };

  const handleToggleShowInPos = async (groupId: number, showInPos: boolean) => {
    if (!selectedProduct) return;
    const previous = assignedGroupVisibility[groupId] ?? defaultShowInPos(groupId);
    setAssignedGroupVisibility((prev) => ({ ...prev, [groupId]: showInPos }));
    const links = assignedGroups.map((id) => ({
      groupId: id,
      showInPos: id === groupId ? showInPos : (assignedGroupVisibility[id] ?? defaultShowInPos(id)),
    }));
    try {
      await updateProductModifierGroups(selectedProduct.id, assignedGroups, links);
      await onUpdated(selectedProduct.id);
    } catch {
      setAssignedGroupVisibility((prev) => ({ ...prev, [groupId]: previous }));
      toast.error("No se pudo actualizar visibilidad POS del grupo");
    }
  };

  const handleDragEnterGroup = (targetGroupId: number) => {
    if (draggingGroupId === null || draggingGroupId === targetGroupId || isSavingOrder) return;
    groupOrder.moveById(draggingGroupId, targetGroupId);
  };

  const handleSaveOrder = async () => {
    if (!selectedProduct || isSavingOrder || !groupOrder.isDirty) return;
    setIsSavingOrder(true);
    try {
      await reorderProductModifierGroups(selectedProduct.id, groupOrder.currentItems);
      groupOrder.markSaved();
      await onUpdated(selectedProduct.id);
      toast.success("Orden guardado");
    } catch {
      toast.error("No se pudo guardar el orden");
    } finally {
      setIsSavingOrder(false);
      setDraggingGroupId(null);
    }
  };

  useEffect(() => {
    setAssignedGroups(groupOrder.currentItems);
  }, [groupOrder.currentItems]);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modificadores</DialogTitle>
            <DialogDescription>
              Gestiona asignaciones de grupos para este producto.
            </DialogDescription>
          </DialogHeader>

          {!selectedProduct ? (
            <Card className="p-4 text-sm text-muted-foreground">Selecciona un producto para continuar.</Card>
          ) : (
            <div className="space-y-4">
              <Card className="p-4">
                <h3 className="text-xl font-bold">{selectedProduct.name}</h3>
                <div className="mt-2 flex gap-2">
                  <Badge variant="outline">{selectedProduct.category}</Badge>
                  <Badge variant="default" className="bg-secondary">${selectedProduct.price.toFixed(2)}</Badge>
                </div>
              </Card>

              <Card className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold">Grupos asignados</h4>
                  <Button variant="outline" size="sm" onClick={() => setShowAssignDialog(true)}>
                    <Plus className="h-4 w-4 mr-1" />
                    Asignar grupo
                  </Button>
                </div>

                {orderedAssignedGroups.length === 0 ? (
                  <div className="rounded-lg border py-4 text-center text-sm text-muted-foreground">Sin grupos asignados.</div>
                ) : (
                  <div className="space-y-2">
                    {orderedAssignedGroups.map((group) => (
                      <div
                        key={group.id}
                        className={`flex items-center justify-between gap-2 rounded-lg border p-3 transition-all ${draggingGroupId === group.id ? "opacity-50 ring-2 ring-primary/50" : ""}`}
                        onDragOver={(event) => event.preventDefault()}
                        onDragEnter={() => handleDragEnterGroup(group.id)}
                        onDrop={() => setDraggingGroupId(null)}
                      >
                        <button
                          type="button"
                          className="text-muted-foreground"
                          draggable={!isSavingOrder}
                          onDragStart={() => setDraggingGroupId(group.id)}
                          onDragEnd={() => setDraggingGroupId(null)}
                          title="Arrastrar para reordenar"
                        >
                          <GripVertical className="h-4 w-4" />
                        </button>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold leading-5">{group.name}</div>
                          <div className="text-sm leading-5 text-muted-foreground">
                            Min: {group.minSelection} · Max: {group.maxSelection}
                            {group.required && " · Obligatorio"}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Label htmlFor={`show-pos-${group.id}`} className="text-xs text-muted-foreground">POS</Label>
                          <Switch
                            id={`show-pos-${group.id}`}
                            checked={assignedGroupVisibility[group.id] ?? defaultShowInPos(group.id)}
                            onCheckedChange={(checked) => handleToggleShowInPos(group.id, checked)}
                          />
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => handleRemoveGroup(group.id)}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                {groupOrder.isDirty && (
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={groupOrder.reset} disabled={isSavingOrder}>
                      Deshacer cambios
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void handleSaveOrder()} disabled={isSavingOrder}>
                      {isSavingOrder ? "Guardando..." : "Guardar orden"}
                    </Button>
                  </div>
                )}
              </Card>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={showAssignDialog && Boolean(selectedProduct)} onOpenChange={setShowAssignDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Asignar grupos de modificadores</DialogTitle>
            <DialogDescription>
              Selecciona los grupos que deseas asignar a {selectedProduct?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-96 space-y-3 overflow-y-auto">
            {modifierGroups.map((group) => {
              const isAlreadyAssigned = assignedGroups.includes(group.id);
              return (
                <div key={group.id} className="flex items-start space-x-3 rounded-lg border p-3">
                  <Checkbox
                    id={`assign-${group.id}`}
                    checked={selectedForAssign.includes(group.id) || isAlreadyAssigned}
                    onCheckedChange={(checked) => {
                      if (isAlreadyAssigned) {
                        toast.error("Ese grupo ya está asignado");
                        return;
                      }
                      if (checked) {
                        setSelectedForAssign([...selectedForAssign, group.id]);
                      } else {
                        setSelectedForAssign(selectedForAssign.filter((id) => id !== group.id));
                      }
                    }}
                    disabled={isAlreadyAssigned}
                  />
                  <Label htmlFor={`assign-${group.id}`} className="flex-1 cursor-pointer">
                    <div className="font-semibold">{group.name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Min {group.minSelection} · Max {group.maxSelection}
                      {group.required && " · Obligatorio"}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {group.modifiers.length} opciones disponibles
                    </div>
                  </Label>
                </div>
              );
            })}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowAssignDialog(false)} className="flex-1">Cancelar</Button>
            <Button onClick={handleAssignGroups} className="flex-1" disabled={selectedForAssign.length === 0}>Confirmar</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
