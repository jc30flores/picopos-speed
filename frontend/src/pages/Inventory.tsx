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
import { toast } from "sonner";
import { InventoryItem, InventoryMovement, addInventoryStock, adjustInventoryStock, createInventoryItem, getInventoryItems, getInventoryMovements, updateInventoryItem } from "@/lib/api";

const UNITS = [
  { value: "unidad", label: "Unidad" },
  { value: "docena", label: "Docena" },
  { value: "media_docena", label: "Media docena" },
  { value: "caja_25", label: "Caja 25" },
  { value: "caja_50", label: "Caja 50" },
  { value: "caja_75", label: "Caja 75" },
  { value: "caja_100", label: "Caja 100" },
  { value: "libra", label: "Libra" },
  { value: "media_libra", label: "Media libra" },
  { value: "onza", label: "Onza" },
  { value: "kilogramo", label: "Kilogramo" },
  { value: "gramo", label: "Gramo" },
  { value: "litro", label: "Litro" },
  { value: "mililitro", label: "Mililitro" },
  { value: "bolsa", label: "Bolsa" },
  { value: "paquete", label: "Paquete" },
  { value: "rollo", label: "Rollo" },
  { value: "bandeja", label: "Bandeja" },
  { value: "botella", label: "Botella" },
  { value: "lata", label: "Lata" },
];
const UNIT_LABEL_BY_VALUE = Object.fromEntries(UNITS.map((unit) => [unit.value, unit.label]));

const formatQuantity = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "—";
  if (Number.isInteger(value)) return String(value);
  return value.toLocaleString("es-SV", { minimumFractionDigits: 0, maximumFractionDigits: 3 });
};

export default function InventoryPage() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [openForm, setOpenForm] = useState(false);
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [openAddStock, setOpenAddStock] = useState<InventoryItem | null>(null);
  const [openAdjust, setOpenAdjust] = useState<InventoryItem | null>(null);

  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [unit, setUnit] = useState("unidad");
  const [stock, setStock] = useState("0");
  const [minStock, setMinStock] = useState("");
  const [notes, setNotes] = useState("");
  const [active, setActive] = useState(true);
  const [reason, setReason] = useState("");
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const load = async (q = query) => {
    const [rows, logs] = await Promise.all([getInventoryItems(q), getInventoryMovements()]);
    setItems(rows);
    setMovements(logs);
  };

  useEffect(() => { load().catch(() => toast.error("No se pudo cargar inventario")); }, []);

  const resetForm = () => { setName(""); setSku(""); setUnit("unidad"); setStock(""); setMinStock(""); setNotes(""); setActive(true); setEditing(null); };

  useEffect(() => {
    if (!openForm) return;
    const t = window.setTimeout(() => nameInputRef.current?.focus(), 30);
    return () => window.clearTimeout(t);
  }, [openForm]);

  const filtered = useMemo(() => items.filter((i) => i.name.toLowerCase().includes(query.toLowerCase()) || i.sku.toLowerCase().includes(query.toLowerCase())), [items, query]);

  return (
    <PageLayout title="Inventario" subtitle="Control simple, rápido y totalmente integrado." actions={<ClockSV timeClassName="text-2xl sm:text-3xl" className="min-w-[220px]" />}>
      <div className="space-y-4">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <Input placeholder="Buscar por nombre o código" value={query} onChange={(e) => setQuery(e.target.value)} className="h-12 flex-1" />
          <Button className="h-12 px-6 sm:min-w-[190px]" onClick={() => { resetForm(); setOpenForm(true); }}>Nuevo producto</Button>
        </div>

        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Producto</TableHead><TableHead>Código</TableHead><TableHead>Unidad</TableHead><TableHead>Stock</TableHead><TableHead>Mínimo</TableHead><TableHead>Estado</TableHead><TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-semibold">{item.name}</TableCell>
                  <TableCell>{item.sku || "—"}</TableCell>
                  <TableCell>{UNIT_LABEL_BY_VALUE[item.unit] ?? item.unit}</TableCell>
                  <TableCell>{formatQuantity(item.currentStock)}</TableCell>
                  <TableCell>{formatQuantity(item.minStock)}</TableCell>
                  <TableCell><Badge variant={item.isActive ? "default" : "outline"}>{item.isActive ? "Activo" : "Inactivo"}</Badge></TableCell>
                  <TableCell className="space-x-2">
                    <Button size="sm" variant="outline" onClick={() => { setEditing(item); setName(item.name); setSku(item.sku); setUnit(item.unit); setMinStock(item.minStock == null ? "" : String(item.minStock)); setNotes(item.notes ?? ""); setActive(item.isActive); setOpenForm(true); }}>Editar</Button>
                    <Button size="sm" variant="outline" onClick={() => { setStock(""); setReason(""); setOpenAddStock(item); }}>Agregar stock</Button>
                    <Button size="sm" variant="outline" onClick={() => { setStock(""); setReason(""); setOpenAdjust(item); }}>Corregir stock</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div className="rounded-xl border bg-card p-4">
          <h3 className="mb-3 text-lg font-semibold">Movimientos recientes</h3>
          <div className="max-h-[320px] overflow-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Fecha</TableHead><TableHead>Producto</TableHead><TableHead>Tipo</TableHead><TableHead>Cambio</TableHead><TableHead>Antes</TableHead><TableHead>Después</TableHead><TableHead>Usuario</TableHead><TableHead>Motivo</TableHead></TableRow></TableHeader>
              <TableBody>
                {movements.map((m) => (<TableRow key={m.id}><TableCell>{new Date(m.createdAt).toLocaleString()}</TableCell><TableCell>{m.inventoryItemName}</TableCell><TableCell>{m.movementType}</TableCell><TableCell>{formatQuantity(m.quantityChange)}</TableCell><TableCell>{formatQuantity(m.quantityBefore)}</TableCell><TableCell>{formatQuantity(m.quantityAfter)}</TableCell><TableCell>{m.createdByUsername || "—"}</TableCell><TableCell>{m.reason || "—"}</TableCell></TableRow>))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      <Dialog open={openForm} onOpenChange={setOpenForm}>
        <DialogContent className="max-w-xl">
          <DialogHeader><DialogTitle>{editing ? "Editar" : "Nuevo"} producto de inventario</DialogTitle></DialogHeader>
          <div className="grid gap-3">
            <Label>Código/SKU</Label><Input value={sku} onChange={(e) => setSku(e.target.value)} className="h-11" />
            <Label>Nombre</Label><Input ref={nameInputRef} value={name} onChange={(e) => setName(e.target.value)} className="h-11" />
            <Label>Unidad</Label>
            <Select value={unit} onValueChange={setUnit}>
              <SelectTrigger className="h-11"><SelectValue placeholder="Unidad" /></SelectTrigger>
              <SelectContent>{UNITS.map((u) => <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent>
            </Select>
            {!editing ? <><Label>Stock inicial</Label><Input value={stock} onChange={(e) => setStock(e.target.value)} className="h-11" /></> : null}
            <Label>Stock mínimo</Label><Input value={minStock} onChange={(e) => setMinStock(e.target.value)} className="h-11" />
            <Label>Notas</Label><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
            <Label className="flex items-center gap-2"><input type="checkbox" checked={active} onChange={(e)=>setActive(e.target.checked)} /> Activo</Label>
            <Button className="h-11" onClick={async () => {
              try {
                if (editing) {
                  await updateInventoryItem(editing.id, { name, sku, unit, minStock: minStock ? Number(minStock) : null, notes, isActive: active });
                } else {
                  await createInventoryItem({ name, sku, unit, initialStock: Number(stock || 0), minStock: minStock ? Number(minStock) : null, notes, isActive: active });
                }
                await load(query); setOpenForm(false); toast.success("Inventario guardado");
              } catch { toast.error("No se pudo guardar"); }
            }}>Guardar</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(openAddStock)} onOpenChange={(v) => !v && setOpenAddStock(null)}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Agregar stock</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Este movimiento suma unidades al stock actual.</p>
          <div className="space-y-3"><Input value={stock} onChange={(e)=>setStock(e.target.value)} placeholder="Cantidad a sumar" className="h-11" /><Textarea value={reason} onChange={(e)=>setReason(e.target.value)} placeholder="Motivo (opcional)" />
            <Button className="h-11" onClick={async ()=>{ if(!openAddStock) return; try { await addInventoryStock(openAddStock.id, Number(stock || 0), reason); await load(query); setOpenAddStock(null); setReason(""); toast.success("Stock agregado"); } catch { toast.error("No se pudo agregar stock"); } }}>Confirmar</Button></div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(openAdjust)} onOpenChange={(v) => !v && setOpenAdjust(null)}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Corregir inventario</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Usa esta opción para fijar el stock real después de conteo físico.</p>
          <div className="space-y-3"><Input value={stock} onChange={(e)=>setStock(e.target.value)} placeholder="Nuevo stock exacto" className="h-11" /><Textarea value={reason} onChange={(e)=>setReason(e.target.value)} placeholder="Motivo de corrección" />
            <Button className="h-11" onClick={async ()=>{ if(!openAdjust) return; try { await adjustInventoryStock(openAdjust.id, { setStock: Number(stock || 0), reason }); await load(query); setOpenAdjust(null); setReason(""); toast.success("Stock corregido"); } catch { toast.error("No se pudo ajustar"); } }}>Guardar corrección</Button></div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
