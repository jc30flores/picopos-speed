import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  createRestaurantTable,
  createTableArea,
  deleteRestaurantTable,
  deleteTableArea,
  getFeatureSettings,
  getTableLayout,
  saveTableLayout,
  updateRestaurantTable,
  updateTableArea,
  type DiningArea,
  type RestaurantTable,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const shapeLabel: Record<RestaurantTable["shape"], string> = { round: "Redonda", square: "Cuadrada", rectangle: "Rectangular", booth: "Cabina", bar: "Barra" };

const TablesEditor = () => {
  const navigate = useNavigate();
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [areas, setAreas] = useState<DiningArea[]>([]);
  const [tables, setTables] = useState<RestaurantTable[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState<number | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pendingLayout, setPendingLayout] = useState<Record<number, Pick<RestaurantTable, "x" | "y" | "width" | "height" | "rotation">>>({});
  const [dragging, setDragging] = useState<{ id: number; dx: number; dy: number } | null>(null);
  const [areaModal, setAreaModal] = useState<{ open: boolean; area?: DiningArea }>({ open: false });
  const [tableModal, setTableModal] = useState<{ open: boolean; table?: RestaurantTable; presetAreaId?: number }>({ open: false });

  const [areaForm, setAreaForm] = useState({ name: "", isActive: true });
  const [tableForm, setTableForm] = useState({ area: "", name: "", number: "1", capacity: "4", shape: "round" as RestaurantTable["shape"], width: "110", height: "110", rotation: "0", isActive: true });

  const reload = async () => {
    const layout = await getTableLayout();
    setAreas(layout.areas);
    setTables(layout.tables);
    setPendingLayout({});
    setSelectedAreaId((prev) => prev ?? layout.areas[0]?.id ?? null);
  };

  useEffect(() => {
    getFeatureSettings().then((s) => setEnabled(Boolean(s.tableMapEnabled))).catch(() => setEnabled(false));
  }, []);

  useEffect(() => {
    if (!enabled) return;
    reload().catch(() => toast.error("No se pudo cargar el mapa."));
  }, [enabled]);

  const selectedArea = useMemo(() => areas.find((a) => a.id === selectedAreaId) ?? null, [areas, selectedAreaId]);
  const selectedTable = useMemo(() => tables.find((t) => t.id === selectedTableId) ?? null, [tables, selectedTableId]);

  const filteredTables = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tables.filter((t) => (!selectedAreaId || t.area === selectedAreaId) && (!q || t.name.toLowerCase().includes(q)));
  }, [tables, selectedAreaId, query]);

  const hasPendingChanges = Object.keys(pendingLayout).length > 0;

  const openAreaModal = (area?: DiningArea) => {
    setAreaForm({ name: area?.name ?? "", isActive: area?.isActive ?? true });
    setAreaModal({ open: true, area });
  };

  const openTableModal = (table?: RestaurantTable) => {
    const areaId = table?.area ?? selectedAreaId ?? areas[0]?.id;
    setTableForm({
      area: areaId ? String(areaId) : "",
      name: table?.name ?? `Mesa ${tables.length + 1}`,
      number: String(table?.number ?? 1),
      capacity: String(table?.capacity ?? 4),
      shape: table?.shape ?? "round",
      width: String(table?.width ?? 110),
      height: String(table?.height ?? 110),
      rotation: String(table?.rotation ?? 0),
      isActive: table?.isActive ?? true,
    });
    setTableModal({ open: true, table, presetAreaId: areaId });
  };

  const startDrag = (table: RestaurantTable, ev: React.PointerEvent<HTMLButtonElement>) => {
    const p = pendingLayout[table.id] ?? table;
    (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
    setSelectedTableId(table.id);
    setDragging({ id: table.id, dx: ev.clientX - p.x * zoom, dy: ev.clientY - p.y * zoom });
  };

  const onMove = (ev: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    const nx = Math.max(0, (ev.clientX - dragging.dx) / zoom);
    const ny = Math.max(0, (ev.clientY - dragging.dy) / zoom);
    setPendingLayout((prev) => ({ ...prev, [dragging.id]: { ...(prev[dragging.id] ?? (tables.find((t) => t.id === dragging.id) as RestaurantTable)), x: Number(nx.toFixed(1)), y: Number(ny.toFixed(1)) } }));
    setTables((prev) => prev.map((t) => (t.id === dragging.id ? { ...t, x: Number(nx.toFixed(1)), y: Number(ny.toFixed(1)) } : t)));
  };

  const saveLayout = async () => {
    const payload = Object.entries(pendingLayout).map(([id, row]) => ({ id: Number(id), x: row.x, y: row.y, width: row.width, height: row.height, rotation: row.rotation }));
    if (!payload.length) return;
    await saveTableLayout({ tables: payload });
    setPendingLayout({});
    toast.success("Mapa guardado correctamente.");
  };

  if (enabled === null) return <div className="p-6">Cargando...</div>;
  if (!enabled) return <div className="p-6"><Card className="p-6 space-y-3"><h1 className="text-xl font-semibold">Mapa de mesas no está activo.</h1><Button onClick={() => navigate('/settings')}>Ir a configuración</Button></Card></div>;

  return (
    <div className="p-4 space-y-4">
      <Card className="p-4 flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold mr-auto">Editor de mesas</h1>
        <Input placeholder="Buscar mesa" className="w-52" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Button variant="outline" onClick={() => openAreaModal()}>Nueva área</Button>
        <Button variant="outline" onClick={() => openTableModal()} disabled={!areas.length}>Nueva mesa</Button>
        <Button onClick={() => void saveLayout()} disabled={!hasPendingChanges}>Guardar mapa</Button>
        <Button variant="outline" onClick={() => navigate('/pos?mode=tables')}>Vista operativa</Button>
        <Button variant="outline" onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}>-</Button>
        <Button variant="outline" onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</Button>
        <Button variant="outline" onClick={() => setZoom((z) => Math.min(2, z + 0.1))}>+</Button>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-4">
        <Card className="p-4 space-y-3">
          <div className="flex items-center justify-between"><h2 className="font-semibold">Áreas</h2><Button size="sm" onClick={() => openAreaModal()}>Nueva</Button></div>
          {!areas.length ? <p className="text-sm text-muted-foreground">No hay áreas aún.</p> : areas.map((area) => <button key={area.id} className={cn("w-full rounded border p-2 text-left", selectedAreaId === area.id && "border-primary")} onClick={() => setSelectedAreaId(area.id)}>{area.name}</button>)}
          {selectedArea ? <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => openAreaModal(selectedArea)}>Editar</Button><Button size="sm" variant="destructive" onClick={async () => { if (!confirm("¿Deseas eliminar/desactivar esta área?")) return; const r = await deleteTableArea(selectedArea.id); toast.success(r.detail || "Área actualizada."); await reload(); }}>Eliminar/Desactivar</Button></div> : null}
        </Card>

        <Card className="p-4">
          {!areas.length ? (
            <div className="h-[65vh] rounded-xl border border-dashed flex items-center justify-center text-center p-8">
              <div><h3 className="text-xl font-semibold">No hay áreas configuradas</h3><p className="text-muted-foreground mt-2">Crea tu primera área para empezar a diseñar el mapa del restaurante.</p><Button className="mt-4" onClick={() => openAreaModal()}>Crear primera área</Button></div>
            </div>
          ) : (
            <div ref={canvasRef} className="relative h-[65vh] overflow-auto rounded-xl border bg-[linear-gradient(to_right,#e5e7eb_1px,transparent_1px),linear-gradient(to_bottom,#e5e7eb_1px,transparent_1px)] bg-[size:24px_24px]" onPointerMove={onMove} onPointerUp={() => setDragging(null)}>
              <div className="relative h-[1200px] w-[1800px]" style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}>
                {filteredTables.length === 0 ? <div className="absolute inset-0 flex items-center justify-center"><div className="text-center"><h3 className="text-lg font-semibold">No hay mesas en esta área</h3><p className="text-muted-foreground">Agrega una mesa para comenzar a diseñar el salón.</p><Button className="mt-3" onClick={() => openTableModal()}>Agregar primera mesa</Button></div></div> : null}
                {filteredTables.map((table) => (
                  <button key={table.id} onPointerDown={(e) => startDrag(table, e)} onClick={() => setSelectedTableId(table.id)} className={cn("absolute border bg-background/95 p-2 text-left shadow", selectedTableId === table.id ? "border-primary ring-2 ring-primary/20" : "border-border", table.shape === "round" && "rounded-full", table.shape === "square" && "rounded-md", table.shape === "rectangle" && "rounded-lg", table.shape === "booth" && "rounded-xl border-2", table.shape === "bar" && "rounded-sm")} style={{ left: table.x, top: table.y, width: table.width, height: table.height, transform: `rotate(${table.rotation}deg)` }}>
                    <p className="text-xs font-semibold leading-tight">{table.name}</p>
                    <p className="text-[11px] text-muted-foreground">Cap. {table.capacity}</p>
                    {!table.isActive ? <span className="text-[10px] text-red-500">Inactiva</span> : null}
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card className="p-4 space-y-3">
          <h2 className="font-semibold">Propiedades</h2>
          {!selectedTable ? <p className="text-sm text-muted-foreground">Selecciona una mesa para editar, duplicar o desactivar.</p> : (
            <>
              <p className="text-sm">{selectedTable.name}</p>
              <p className="text-xs text-muted-foreground">Forma: {shapeLabel[selectedTable.shape]} · Capacidad: {selectedTable.capacity}</p>
              <div className="flex gap-2"><Button size="sm" onClick={() => openTableModal(selectedTable)}>Editar</Button><Button size="sm" variant="outline" onClick={async () => { const t = selectedTable; await createRestaurantTable({ area: t.area, name: `${t.name} copia`, number: t.number, capacity: t.capacity, shape: t.shape, width: t.width, height: t.height, rotation: t.rotation, x: t.x + 24, y: t.y + 24, isActive: t.isActive }); toast.success("Mesa duplicada correctamente."); await reload(); }}>Duplicar</Button></div>
              <Button size="sm" variant="destructive" onClick={async () => { if (!confirm("¿Deseas eliminar esta mesa?")) return; const r = await deleteRestaurantTable(selectedTable.id); toast.success(r.detail || "Mesa actualizada."); await reload(); setSelectedTableId(null); }}>Eliminar/Desactivar</Button>
            </>
          )}
        </Card>
      </div>

      <Dialog open={areaModal.open} onOpenChange={(open) => setAreaModal({ open, area: areaModal.area })}>
        <DialogContent>
          <DialogHeader><DialogTitle>{areaModal.area ? "Editar área" : "Nueva área"}</DialogTitle></DialogHeader>
          <div className="space-y-3"><Label>Nombre del área</Label><Input value={areaForm.name} onChange={(e) => setAreaForm((s) => ({ ...s, name: e.target.value }))} /><div className="flex items-center justify-between"><Label>Activa</Label><Switch checked={areaForm.isActive} onCheckedChange={(v) => setAreaForm((s) => ({ ...s, isActive: v }))} /></div></div>
          <DialogFooter><Button variant="outline" onClick={() => setAreaModal({ open: false })}>Cancelar</Button><Button onClick={async () => { if (!areaForm.name.trim()) return toast.error("El nombre del área es obligatorio."); const saved = areaModal.area ? await updateTableArea(areaModal.area.id, { name: areaForm.name.trim(), isActive: areaForm.isActive }) : await createTableArea({ name: areaForm.name.trim(), isActive: areaForm.isActive }); toast.success("Área guardada correctamente."); setAreaModal({ open: false }); await reload(); setSelectedAreaId(saved.id); }}>Guardar área</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={tableModal.open} onOpenChange={(open) => setTableModal({ open, table: tableModal.table })}>
        <DialogContent>
          <DialogHeader><DialogTitle>{tableModal.table ? "Editar mesa" : "Nueva mesa"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2"><Label>Área</Label><Select value={tableForm.area} onValueChange={(v) => setTableForm((s) => ({ ...s, area: v }))}><SelectTrigger><SelectValue placeholder="Selecciona área" /></SelectTrigger><SelectContent>{areas.map((a) => <SelectItem key={a.id} value={String(a.id)}>{a.name}</SelectItem>)}</SelectContent></Select></div>
            <div className="col-span-2"><Label>Nombre</Label><Input value={tableForm.name} onChange={(e) => setTableForm((s) => ({ ...s, name: e.target.value }))} /></div>
            <div><Label>Número</Label><Input value={tableForm.number} onChange={(e) => setTableForm((s) => ({ ...s, number: e.target.value }))} /></div>
            <div><Label>Capacidad</Label><Input value={tableForm.capacity} onChange={(e) => setTableForm((s) => ({ ...s, capacity: e.target.value }))} /></div>
            <div><Label>Forma</Label><Select value={tableForm.shape} onValueChange={(v: RestaurantTable['shape']) => setTableForm((s) => ({ ...s, shape: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(shapeLabel).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Rotación</Label><Input value={tableForm.rotation} onChange={(e) => setTableForm((s) => ({ ...s, rotation: e.target.value }))} /></div>
            <div><Label>Ancho</Label><Input value={tableForm.width} onChange={(e) => setTableForm((s) => ({ ...s, width: e.target.value }))} /></div>
            <div><Label>Alto</Label><Input value={tableForm.height} onChange={(e) => setTableForm((s) => ({ ...s, height: e.target.value }))} /></div>
            <div className="col-span-2 flex items-center justify-between"><Label>Activa</Label><Switch checked={tableForm.isActive} onCheckedChange={(v) => setTableForm((s) => ({ ...s, isActive: v }))} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setTableModal({ open: false })}>Cancelar</Button><Button onClick={async () => {
            const area = Number(tableForm.area);
            const cap = Number(tableForm.capacity);
            const width = Number(tableForm.width);
            const height = Number(tableForm.height);
            if (!area) return toast.error("El área es obligatoria.");
            if (!tableForm.name.trim()) return toast.error("El nombre de la mesa es obligatorio.");
            if (!Number.isFinite(cap) || cap < 1) return toast.error("La capacidad debe ser mayor o igual a 1.");
            if (!Number.isFinite(width) || width <= 0 || !Number.isFinite(height) || height <= 0) return toast.error("Ancho y alto deben ser mayores que 0.");
            const payload = { area, name: tableForm.name.trim(), number: Number(tableForm.number || 1), capacity: cap, shape: tableForm.shape, width, height, rotation: Number(tableForm.rotation || 0), isActive: tableForm.isActive, x: tableModal.table?.x ?? 120, y: tableModal.table?.y ?? 120 };
            const saved = tableModal.table ? await updateRestaurantTable(tableModal.table.id, payload) : await createRestaurantTable(payload);
            toast.success("Mesa guardada correctamente.");
            setTableModal({ open: false });
            await reload();
            setSelectedAreaId(saved.area);
            setSelectedTableId(saved.id);
          }}>Guardar mesa</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TablesEditor;
