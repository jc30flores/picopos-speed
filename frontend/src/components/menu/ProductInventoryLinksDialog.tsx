import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { InventoryItem, InventoryProductLink, getInventoryItems } from "@/lib/api";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: InventoryProductLink[];
  onSave: (value: InventoryProductLink[]) => void;
}

export const ProductInventoryLinksDialog = ({ open, onOpenChange, value, onSave }: Props) => {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [draft, setDraft] = useState<Record<number, number>>({});

  useEffect(() => {
    if (!open) return;
    getInventoryItems(query).then(setItems).catch(() => setItems([]));
  }, [open, query]);

  useEffect(() => {
    const map: Record<number, number> = {};
    value.forEach((v) => { map[v.inventoryItemId] = v.quantityRequired; });
    setDraft(map);
  }, [value, open]);

  const selectedCount = useMemo(() => Object.values(draft).filter((n) => n > 0).length, [draft]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Vincular inventario</DialogTitle></DialogHeader>
        <Input placeholder="Buscar insumo" value={query} onChange={(e) => setQuery(e.target.value)} className="h-11" />
        <div className="max-h-[380px] overflow-auto space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-3 rounded-lg border p-3">
              <input type="checkbox" checked={Boolean(draft[item.id] > 0)} onChange={(e) => setDraft((prev) => ({ ...prev, [item.id]: e.target.checked ? prev[item.id] || 1 : 0 }))} />
              <div className="flex-1">
                <p className="font-medium">{item.name}</p>
                <p className="text-xs text-muted-foreground">{item.unit} · Stock: {item.currentStock.toFixed(3)}</p>
              </div>
              <Input className="w-28 h-10" type="number" min="0" step="0.001" value={draft[item.id] ?? ""} onChange={(e) => setDraft((prev) => ({ ...prev, [item.id]: Number(e.target.value || 0) }))} />
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{selectedCount} vinculaciones seleccionadas</p>
          <Button className="h-11 px-6" onClick={() => {
            const next = items
              .filter((item) => (draft[item.id] ?? 0) > 0)
              .map((item) => ({
                inventoryItemId: item.id,
                inventoryItemName: item.name,
                inventoryItemUnit: item.unit,
                quantityRequired: Number(draft[item.id]),
              }));
            onSave(next);
            onOpenChange(false);
          }}>Guardar vínculos</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
