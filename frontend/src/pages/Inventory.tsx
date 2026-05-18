import { useEffect, useMemo, useRef, useState } from "react";
import { PageLayout } from "@/components/layout/PageLayout";
import { ClockSV } from "@/components/ClockSV";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { InventoryItem, InventoryMovement, createInventoryAdjustment, createInventoryItem, getInventoryItems, getInventoryMovements, updateInventoryItem } from "@/lib/api";

const UNITS = [
  { value: "unidad", label: "Unidad" }, { value: "docena", label: "Docena" }, { value: "media_docena", label: "Media docena" },
  { value: "caja_25", label: "Caja 25" }, { value: "caja_50", label: "Caja 50" }, { value: "caja_75", label: "Caja 75" }, { value: "caja_100", label: "Caja 100" },
  { value: "libra", label: "Libra" }, { value: "media_libra", label: "Media libra" }, { value: "onza", label: "Onza" }, { value: "kilogramo", label: "Kilogramo" },
  { value: "gramo", label: "Gramo" }, { value: "litro", label: "Litro" }, { value: "mililitro", label: "Mililitro" }, { value: "bolsa", label: "Bolsa" },
  { value: "paquete", label: "Paquete" }, { value: "rollo", label: "Rollo" }, { value: "bandeja", label: "Bandeja" }, { value: "botella", label: "Botella" }, { value: "lata", label: "Lata" },
];
const UNIT_LABEL_BY_VALUE = Object.fromEntries(UNITS.map((unit) => [unit.value, unit.label]));
const ITEM_FILTERS = ["Todos", "Stock bajo", "Activos", "Inactivos"] as const;
const MOVEMENT_FILTERS = ["Todos", "Entradas", "Pérdidas", "Dañados", "Correcciones", "Ventas"] as const;
const ADJUSTMENT_OPTIONS = [
  { value: "entry", label: "Entrada de producto", description: "Aumenta el stock cuando ingresan productos al inventario." },
  { value: "loss", label: "Pérdida", description: "Descuenta productos perdidos del inventario." },
  { value: "damaged", label: "Producto dañado", description: "Descuenta productos que ya no pueden utilizarse o venderse." },
  { value: "correction", label: "Corrección de stock", description: "Fija el stock real después de una revisión física." },
] as const;
type AdjustmentType = typeof ADJUSTMENT_OPTIONS[number]["value"];

const MOVEMENT_LABELS: Record<string, string> = {
  initial_stock: "Stock inicial", stock_add: "Entrada de producto", stock_adjustment: "Corrección de stock", inventory_entry: "Entrada de producto",
  inventory_loss: "Pérdida", inventory_damaged: "Producto dañado", inventory_correction: "Corrección de stock", sale_deduction: "Descuento por venta", reversal: "Reversión",
};

const formatQuantity = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "—";
  if (Number.isInteger(value)) return String(value);
  return value.toLocaleString("es-SV", { minimumFractionDigits: 0, maximumFractionDigits: 3 });
};
const isLowStock = (item: InventoryItem) => item.minStock != null && item.currentStock < item.minStock;
const parseOptionalNumber = (value: string) => (value.trim() === "" ? null : Number(value));

export default function InventoryPage() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [openForm, setOpenForm] = useState(false);
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [itemFilter, setItemFilter] = useState<(typeof ITEM_FILTERS)[number]>("Todos");
  const [movementFilter, setMovementFilter] = useState<(typeof MOVEMENT_FILTERS)[number]>("Todos");
  const [openAdjustment, setOpenAdjustment] = useState(false);
  const [lockedAdjustmentItem, setLockedAdjustmentItem] = useState(false);

  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [unit, setUnit] = useState("unidad");
  const [stock, setStock] = useState("0");
  const [minStock, setMinStock] = useState("");
  const [maxStock, setMaxStock] = useState("");
  const [notes, setNotes] = useState("");
  const [active, setActive] = useState(true);
  const [adjustItemId, setAdjustItemId] = useState("");
  const [adjustType, setAdjustType] = useState<AdjustmentType>("entry");
  const [adjustQuantity, setAdjustQuantity] = useState("");
  const [adjustSetStock, setAdjustSetStock] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const load = async (q = query) => {
    const [rows, logs] = await Promise.all([getInventoryItems(q), getInventoryMovements()]);
    setItems(rows); setMovements(logs);
  };

  useEffect(() => { load().catch(() => toast.error("No se pudo cargar inventario")); }, []);
  useEffect(() => { if (!openForm) return; const t = window.setTimeout(() => nameInputRef.current?.focus(), 30); return () => window.clearTimeout(t); }, [openForm]);

  const resetForm = () => { setName(""); setSku(""); setUnit("unidad"); setStock(""); setMinStock(""); setMaxStock(""); setNotes(""); setActive(true); setEditing(null); };
  const openAdjustmentModal = (item?: InventoryItem) => {
    setAdjustItemId(item ? String(item.id) : ""); setLockedAdjustmentItem(Boolean(item)); setAdjustType("entry"); setAdjustQuantity(""); setAdjustSetStock(""); setAdjustReason(""); setOpenAdjustment(true);
  };
  const selectedAdjustmentItem = useMemo(() => items.find((item) => String(item.id) === adjustItemId) ?? null, [adjustItemId, items]);
  const estimatedFinalStock = useMemo(() => {
    if (!selectedAdjustmentItem) return null;
    const current = selectedAdjustmentItem.currentStock;
    if (adjustType === "correction") return adjustSetStock.trim() === "" ? current : Number(adjustSetStock);
    const qty = Number(adjustQuantity || 0);
    return adjustType === "entry" ? current + qty : current - qty;
  }, [adjustQuantity, adjustSetStock, adjustType, selectedAdjustmentItem]);

  const filtered = useMemo(() => items
    .filter((i) => i.name.toLowerCase().includes(query.toLowerCase()) || i.sku.toLowerCase().includes(query.toLowerCase()))
    .filter((i) => itemFilter === "Todos" || (itemFilter === "Stock bajo" && isLowStock(i)) || (itemFilter === "Activos" && i.isActive) || (itemFilter === "Inactivos" && !i.isActive)), [items, query, itemFilter]);
  const filteredMovements = useMemo(() => movements.filter((m) => {
    const type = m.movementType;
    if (movementFilter === "Todos") return true;
    if (movementFilter === "Entradas") return ["initial_stock", "stock_add", "inventory_entry"].includes(type);
    if (movementFilter === "Pérdidas") return type === "inventory_loss";
    if (movementFilter === "Dañados") return type === "inventory_damaged";
    if (movementFilter === "Correcciones") return ["stock_adjustment", "inventory_correction"].includes(type);
    return type === "sale_deduction";
  }), [movements, movementFilter]);

  const saveAdjustment = async () => {
    if (!selectedAdjustmentItem) return toast.error("Selecciona un artículo.");
    const quantity = Number(adjustQuantity || 0);
    const realStock = Number(adjustSetStock || 0);
    if (adjustType !== "correction" && quantity <= 0) return toast.error("La cantidad debe ser mayor a 0.");
    if (adjustType === "correction" && (adjustSetStock.trim() === "" || realStock < 0)) return toast.error("El stock real debe ser mayor o igual a 0.");
    if (["loss", "damaged", "correction"].includes(adjustType) && !adjustReason.trim()) return toast.error("El motivo es obligatorio para este ajuste.");
    if (["loss", "damaged"].includes(adjustType) && quantity > selectedAdjustmentItem.currentStock) return toast.error("La cantidad no puede ser mayor al stock disponible.");
    try {
      await createInventoryAdjustment({ inventoryItem: selectedAdjustmentItem.id, adjustmentType: adjustType, quantity: adjustType === "correction" ? undefined : quantity, setStock: adjustType === "correction" ? realStock : undefined, reason: adjustReason });
      await load(query); setOpenAdjustment(false); toast.success("Ajuste registrado correctamente.");
    } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo registrar el ajuste"); }
  };

  return (
    <PageLayout title="Inventario" subtitle="Control simple, rápido y totalmente integrado." actions={<ClockSV timeClassName="text-2xl sm:text-3xl" className="min-w-[220px]" />}>
      <div className="space-y-4">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <Input placeholder="Buscar por nombre o código" value={query} onChange={(e) => setQuery(e.target.value)} className="h-12 flex-1" />
          <Button className="h-12 px-6 sm:min-w-[190px]" variant="outline" onClick={() => openAdjustmentModal()}>Ajustar inventario</Button>
          <Button className="h-12 px-6 sm:min-w-[190px]" onClick={() => { resetForm(); setOpenForm(true); }}>Nuevo artículo</Button>
        </div>
        <div className="mx-auto flex w-full max-w-5xl flex-wrap gap-2">
          {ITEM_FILTERS.map((filter) => <Button key={filter} size="sm" variant={itemFilter === filter ? "default" : "outline"} onClick={() => setItemFilter(filter)}>{filter}</Button>)}
        </div>

        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader><TableRow><TableHead>Producto</TableHead><TableHead>Código</TableHead><TableHead>Unidad</TableHead><TableHead>Stock</TableHead><TableHead>Mínimo</TableHead><TableHead>Máximo</TableHead><TableHead>Estado</TableHead><TableHead>Acciones</TableHead></TableRow></TableHeader>
            <TableBody>{filtered.map((item) => {
              const low = isLowStock(item);
              return <TableRow key={item.id} className={cn(low && "border-l-2 border-l-red-500/80 bg-red-500/5")}>
                <TableCell className="font-semibold">{item.name}</TableCell><TableCell>{item.sku || "—"}</TableCell><TableCell>{UNIT_LABEL_BY_VALUE[item.unit] ?? item.unit}</TableCell>
                <TableCell className={cn("font-semibold", low && "text-red-500")}>{formatQuantity(item.currentStock)}</TableCell><TableCell>{formatQuantity(item.minStock)}</TableCell><TableCell>{formatQuantity(item.maxStock)}</TableCell>
                <TableCell><div className="flex flex-wrap gap-1"><Badge variant={item.isActive ? "default" : "outline"}>{item.isActive ? "Activo" : "Inactivo"}</Badge>{low ? <Badge className="bg-red-600 text-white hover:bg-red-600">Stock bajo</Badge> : null}</div></TableCell>
                <TableCell className="space-x-2"><Button size="sm" variant="outline" onClick={() => { setEditing(item); setName(item.name); setSku(item.sku); setUnit(item.unit); setMinStock(item.minStock == null ? "" : String(item.minStock)); setMaxStock(item.maxStock == null ? "" : String(item.maxStock)); setNotes(item.notes ?? ""); setActive(item.isActive); setOpenForm(true); }}>Editar</Button><Button size="sm" variant="outline" onClick={() => openAdjustmentModal(item)}>Ajustar</Button></TableCell>
              </TableRow>;
            })}</TableBody>
          </Table>
        </div>

        <div className="rounded-xl border bg-card p-4">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><h3 className="text-lg font-semibold">Movimientos recientes</h3><div className="flex flex-wrap gap-2">{MOVEMENT_FILTERS.map((filter) => <Button key={filter} size="sm" variant={movementFilter === filter ? "default" : "outline"} onClick={() => setMovementFilter(filter)}>{filter}</Button>)}</div></div>
          <div className="max-h-[320px] overflow-auto"><Table><TableHeader><TableRow><TableHead>Fecha</TableHead><TableHead>Producto</TableHead><TableHead>Tipo</TableHead><TableHead>Cambio</TableHead><TableHead>Antes</TableHead><TableHead>Después</TableHead><TableHead>Usuario</TableHead><TableHead>Motivo</TableHead></TableRow></TableHeader><TableBody>{filteredMovements.map((m) => (<TableRow key={m.id}><TableCell>{new Date(m.createdAt).toLocaleString()}</TableCell><TableCell>{m.inventoryItemName}</TableCell><TableCell>{MOVEMENT_LABELS[m.movementType] ?? m.movementType}</TableCell><TableCell>{formatQuantity(m.quantityChange)}</TableCell><TableCell>{formatQuantity(m.quantityBefore)}</TableCell><TableCell>{formatQuantity(m.quantityAfter)}</TableCell><TableCell>{m.createdByUsername || "—"}</TableCell><TableCell>{m.reason || "—"}</TableCell></TableRow>))}</TableBody></Table></div>
        </div>
      </div>

      <Dialog open={openForm} onOpenChange={setOpenForm}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>{editing ? "Editar" : "Nuevo"} artículo de inventario</DialogTitle></DialogHeader><div className="grid gap-3">
        <Label>Código/SKU</Label><Input value={sku} onChange={(e) => setSku(e.target.value)} className="h-11" /><Label>Nombre</Label><Input ref={nameInputRef} value={name} onChange={(e) => setName(e.target.value)} className="h-11" />
        <Label>Unidad</Label><Select value={unit} onValueChange={setUnit}><SelectTrigger className="h-11"><SelectValue placeholder="Unidad" /></SelectTrigger><SelectContent>{UNITS.map((u) => <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent></Select>
        {!editing ? <><Label>Stock inicial</Label><Input type="number" value={stock} onChange={(e) => setStock(e.target.value)} className="h-11" /></> : null}
        <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Stock mínimo</Label><Input type="number" value={minStock} onChange={(e) => setMinStock(e.target.value)} className="h-11" /></div><div className="space-y-2"><Label>Stock máximo</Label><Input type="number" value={maxStock} onChange={(e) => setMaxStock(e.target.value)} className="h-11" /></div></div>
        <Label>Notas</Label><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /><Label className="flex items-center gap-2"><input type="checkbox" checked={active} onChange={(e)=>setActive(e.target.checked)} /> Activo</Label>
        <Button className="h-11" onClick={async () => { try { const payload = { name, sku, unit, minStock: parseOptionalNumber(minStock), maxStock: parseOptionalNumber(maxStock), notes, isActive: active }; if (editing) await updateInventoryItem(editing.id, payload); else await createInventoryItem({ ...payload, initialStock: Number(stock || 0) }); await load(query); setOpenForm(false); toast.success("Inventario guardado"); } catch { toast.error("No se pudo guardar"); } }}>Guardar</Button>
      </div></DialogContent></Dialog>

      <Dialog open={openAdjustment} onOpenChange={setOpenAdjustment}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Ajustar inventario</DialogTitle></DialogHeader><div className="space-y-4">
        <div className="space-y-2"><Label>Artículo</Label><Select value={adjustItemId} onValueChange={setAdjustItemId} disabled={lockedAdjustmentItem}><SelectTrigger className="h-11"><SelectValue placeholder="Selecciona un artículo" /></SelectTrigger><SelectContent>{items.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.name} · Stock {formatQuantity(item.currentStock)}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-2"><Label>Tipo de ajuste</Label><div className="grid gap-2 sm:grid-cols-2">{ADJUSTMENT_OPTIONS.map((option) => <button key={option.value} type="button" className={cn("rounded-xl border p-3 text-left transition", adjustType === option.value ? "border-primary bg-primary/10" : "hover:bg-muted/40")} onClick={() => setAdjustType(option.value)}><p className="font-semibold">{option.label}</p><p className="text-xs text-muted-foreground">{option.description}</p></button>)}</div></div>
        {adjustType === "correction" ? <div className="space-y-2"><Label>Stock real</Label><Input type="number" value={adjustSetStock} onChange={(e) => setAdjustSetStock(e.target.value)} placeholder="Stock real" className="h-11" /></div> : <div className="space-y-2"><Label>Cantidad</Label><Input type="number" value={adjustQuantity} onChange={(e)=>setAdjustQuantity(e.target.value)} placeholder="Cantidad" className="h-11" /></div>}
        <div className="space-y-2"><Label>Motivo/nota{adjustType === "entry" ? "" : " (obligatorio)"}</Label><Textarea value={adjustReason} onChange={(e)=>setAdjustReason(e.target.value)} placeholder="Motivo del ajuste" /></div>
        <div className="grid gap-2 rounded-xl border bg-muted/20 p-3 text-sm sm:grid-cols-3"><div><p className="text-muted-foreground">Stock actual</p><p className="font-semibold">{formatQuantity(selectedAdjustmentItem?.currentStock)}</p></div><div><p className="text-muted-foreground">Cambio</p><p className="font-semibold">{selectedAdjustmentItem ? formatQuantity((estimatedFinalStock ?? selectedAdjustmentItem.currentStock) - selectedAdjustmentItem.currentStock) : "—"}</p></div><div><p className="text-muted-foreground">Stock final estimado</p><p className={cn("font-semibold", estimatedFinalStock != null && estimatedFinalStock < 0 && "text-red-500")}>{formatQuantity(estimatedFinalStock)}</p></div></div>
        <Button className="h-11 w-full" onClick={() => void saveAdjustment()}>Guardar ajuste</Button>
      </div></DialogContent></Dialog>
    </PageLayout>
  );
}
