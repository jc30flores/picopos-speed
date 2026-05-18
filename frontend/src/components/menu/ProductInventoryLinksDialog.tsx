import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { InventoryItem, InventoryProductLink, getInventoryItems } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: InventoryProductLink[];
  onSave: (value: InventoryProductLink[]) => void;
}

export const ProductInventoryLinksDialog = ({ open, onOpenChange, value, onSave }: Props) => {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});

  const FRACTIONAL_UNITS = useMemo(
    () => new Set(["libra", "media_libra", "onza", "kilogramo", "gramo", "litro", "mililitro"]),
    [],
  );

  const allowsFractionalQuantity = (unit: string) => FRACTIONAL_UNITS.has(String(unit || "").trim().toLowerCase());
  const getQuantityStep = (unit: string) => (allowsFractionalQuantity(unit) ? "0.001" : "1");

  useEffect(() => {
    if (!open) return;
    getInventoryItems(query).then(setItems).catch(() => setItems([]));
  }, [open, query]);

  useEffect(() => {
    const selectedMap: Record<number, boolean> = {};
    const draftMap: Record<number, string> = {};
    value.forEach((v) => {
      selectedMap[v.inventoryItemId] = v.origin !== "disabled";
      draftMap[v.inventoryItemId] = String(v.quantityRequired);
    });
    setSelected(selectedMap);
    setDraft(draftMap);
    setErrors({});
  }, [value, open]);

  const selectedCount = useMemo(() => Object.values(selected).filter(Boolean).length, [selected]);

  const handleToggleSelected = (item: InventoryItem, checked: boolean) => {
    setSelected((prev) => ({ ...prev, [item.id]: checked }));
    if (checked) {
      setDraft((prev) => ({ ...prev, [item.id]: prev[item.id] ?? "1" }));
      setErrors((prev) => ({ ...prev, [item.id]: "" }));
    }
  };

  const handleQuantityChange = (item: InventoryItem, raw: string) => {
    const normalized = raw.replace(",", ".");
    if (allowsFractionalQuantity(item.unit)) {
      if (!/^\d*\.?\d*$/.test(normalized) && normalized !== "") return;
    } else {
      if (!/^\d*$/.test(normalized) && normalized !== "") return;
    }
    setDraft((prev) => ({ ...prev, [item.id]: normalized }));
    setErrors((prev) => ({ ...prev, [item.id]: "" }));
  };

  const validateQuantity = (item: InventoryItem, rawValue: string): string => {
    if (rawValue.trim() === "") return "Ingresa una cantidad.";
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed) || parsed <= 0) return "Cantidad inválida.";
    if (!allowsFractionalQuantity(item.unit) && !Number.isInteger(parsed)) return "Debe ser un entero para esta unidad.";
    return "";
  };

  const handleSave = () => {
    const nextErrors: Record<number, string> = {};
    const next = items
      .filter((item) => Boolean(selected[item.id]))
      .map((item) => {
        const rawValue = draft[item.id] ?? "";
        const error = validateQuantity(item, rawValue);
        if (error) {
          nextErrors[item.id] = error;
        }
        return {
          inventoryItemId: item.id,
          inventoryItemName: item.name,
          inventoryItemUnit: item.unit,
          quantityRequired: Number(rawValue),
        };
      })
      .filter((row) => !nextErrors[row.inventoryItemId]);

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onSave(next);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Componentes del artículo</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">Los componentes se descontarán solo si Artículo compuesto está activo.</p>
        <Input placeholder="Buscar componente" value={query} onChange={(e) => setQuery(e.target.value)} className="h-11" />
        <div className="max-h-[380px] overflow-auto space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-3 rounded-lg border p-3">
              <input
                type="checkbox"
                checked={Boolean(selected[item.id])}
                onChange={(e) => handleToggleSelected(item, e.target.checked)}
              />
              <div className="flex-1">
                <p className="font-medium">{item.name}</p>
                {value.find((row) => row.inventoryItemId === item.id)?.origin ? (
                  <Badge variant="outline" className="mr-1 mt-1 text-[10px] uppercase">
                    {value.find((row) => row.inventoryItemId === item.id)?.origin === "inherited" ? "Heredado de categoría" : value.find((row) => row.inventoryItemId === item.id)?.origin === "override" ? "Personalizado para este producto" : value.find((row) => row.inventoryItemId === item.id)?.origin === "disabled" ? "Desactivado para este producto" : "Componente"}
                  </Badge>
                ) : null}
                <p className="text-xs text-muted-foreground">{item.unit} · Stock: {item.currentStock}</p>
              </div>
              <div className="w-36">
                <Input
                  className="h-10"
                  type="number"
                  inputMode={allowsFractionalQuantity(item.unit) ? "decimal" : "numeric"}
                  min="0"
                  step={getQuantityStep(item.unit)}
                  value={draft[item.id] ?? ""}
                  onChange={(e) => handleQuantityChange(item, e.target.value)}
                  onBlur={(e) => {
                    if (!selected[item.id]) return;
                    const error = validateQuantity(item, e.target.value);
                    setErrors((prev) => ({ ...prev, [item.id]: error }));
                  }}
                  placeholder={allowsFractionalQuantity(item.unit) ? "0.001" : "1"}
                />
                {errors[item.id] ? <p className="mt-1 text-xs text-destructive">{errors[item.id]}</p> : null}
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{selectedCount} componentes seleccionados</p>
          <Button className="h-11 px-6" onClick={handleSave}>Guardar componentes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
