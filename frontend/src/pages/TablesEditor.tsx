import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Redo2, Save, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { createRestaurantTable, createTableArea, deleteRestaurantTable, deleteTableArea, getRuntimeFeatureSettings, getTableLayout, saveTableLayout, updateRestaurantTable, updateTableArea, type DiningArea, type RestaurantTable } from "@/lib/api";

const GRID_SIZE = 20;
const snapValue = (n: number, enabled: boolean) => enabled ? Math.round(n / GRID_SIZE) * GRID_SIZE : n;
const shapeLabel: Record<RestaurantTable["shape"], string> = { round: "Redonda", square: "Cuadrada", rectangle: "Rectangular", booth: "Cabina", bar: "Barra" };
const isInputLike = (el: EventTarget | null) => {
  const t = el as HTMLElement | null;
  if (!t) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable;
};

type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
type TableClipboard = Omit<RestaurantTable, "id">;

type TableForm = {
  area: string;
  name: string;
  number: string;
  capacity: string;
  shape: RestaurantTable["shape"];
  width: string;
  height: string;
  rotation: string;
  color: string;
  isActive: boolean;
  autoName: boolean;
};

const initialTableForm: TableForm = { area: "", name: "", number: "1", capacity: "4", shape: "round", width: "120", height: "80", rotation: "0", color: "#10b981", isActive: true, autoName: true };

export default function TablesEditor() {
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [areas, setAreas] = useState<DiningArea[]>([]);
  const [tables, setTables] = useState<RestaurantTable[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState<number | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [snapOn, setSnapOn] = useState(true);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [tableModal, setTableModal] = useState<{ open: boolean; table?: RestaurantTable }>({ open: false });
  const [areaModal, setAreaModal] = useState<{ open: boolean; area?: DiningArea }>({ open: false });
  const [tableCtx, setTableCtx] = useState<{ open: boolean; x: number; y: number; id: number | null }>({ open: false, x: 0, y: 0, id: null });
  const [areaCtx, setAreaCtx] = useState<{ open: boolean; x: number; y: number; id: number | null }>({ open: false, x: 0, y: 0, id: null });
  const [undoStack, setUndoStack] = useState<RestaurantTable[][]>([]);
  const [redoStack, setRedoStack] = useState<RestaurantTable[][]>([]);
  const [search, setSearch] = useState("");
  const [tableForm, setTableForm] = useState<TableForm>(initialTableForm);
  const [areaForm, setAreaForm] = useState<any>({ name: "", isActive: true, x: "0", y: "0", width: "320", height: "220", color: "" });

  const clipboardRef = useRef<TableClipboard | null>(null);
  const pendingLayoutRef = useRef<Record<number, { x: number; y: number; width: number; height: number; rotation: number }>>({});
  const autosaveRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const opRef = useRef<null | { type: "drag" | "resize" | "rotate"; id: number; dir?: ResizeDir; startX: number; startY: number; tableStart: RestaurantTable }>(null);

  const reload = async () => {
    const l = await getTableLayout();
    setAreas(l.areas);
    setTables(l.tables);
    setSelectedAreaId((p) => p ?? l.areas[0]?.id ?? null);
  };

  useEffect(() => {
    getRuntimeFeatureSettings().then((s) => setEnabled(Boolean(s.tableMapEnabled))).catch(() => setEnabled(false));
  }, []);

  useEffect(() => {
    if (enabled) void reload();
  }, [enabled]);

  const filteredTables = useMemo(() => tables.filter((t) => (!selectedAreaId || t.area === selectedAreaId) && (!search.trim() || t.name.toLowerCase().includes(search.toLowerCase()))), [tables, selectedAreaId, search]);

  const pushHistory = () => {
    setUndoStack((p) => [...p.slice(-49), tables.map((t) => ({ ...t }))]);
    setRedoStack([]);
  };

  const saveNow = async () => {
    const payload = Object.entries(pendingLayoutRef.current).map(([id, v]) => ({ id: Number(id), ...v }));
    if (!payload.length) {
      setSaveState("saved");
      return;
    }
    try {
      setSaveState("saving");
      await saveTableLayout({ tables: payload });
      pendingLayoutRef.current = {};
      setSaveState("saved");
    } catch {
      setSaveState("error");
      toast.error("Error al guardar cambios.");
    }
  };

  const queueAutosave = () => {
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current);
    autosaveRef.current = window.setTimeout(() => void saveNow(), 350);
  };

  const patchTable = (id: number, patch: Partial<RestaurantTable>) => {
    setTables((prev) => {
      const i = prev.findIndex((t) => t.id === id);
      if (i === -1) return prev;
      const next = prev.slice();
      const current = next[i];
      const updated = { ...current, ...patch };
      next[i] = updated;
      pendingLayoutRef.current[id] = { x: updated.x, y: updated.y, width: updated.width, height: updated.height, rotation: updated.rotation };
      return next;
    });
  };

  const getNextTableNumber = (areaId: number | null) => {
    const inArea = tables.filter((t) => areaId == null || t.area === areaId);
    const nums = inArea.map((t) => {
      const byField = Number(t.number);
      if (Number.isFinite(byField) && byField > 0) return byField;
      const m = String(t.name || "").match(/(\d+)$/);
      return m ? Number(m[1]) : 0;
    }).filter((n) => n > 0);
    return nums.length ? Math.max(...nums) + 1 : inArea.length + 1;
  };

  const openNewTableModal = () => {
    const areaId = selectedAreaId ?? areas[0]?.id ?? null;
    const next = getNextTableNumber(areaId);
    setTableForm({ ...initialTableForm, area: String(areaId ?? ""), number: String(next), name: `Mesa ${next}`, autoName: true });
    setTableModal({ open: true });
  };

  const duplicateTable = async (base: RestaurantTable) => {
    const next = getNextTableNumber(base.area);
    const created = await createRestaurantTable({ ...base, id: undefined as never, name: `Mesa ${next}`, number: next, x: base.x + 30, y: base.y + 30 });
    setTables((p) => [...p, created]);
    setSelectedTableId(created.id);
    setSaveState("saved");
  };

  const handleDeleteTable = async (t: RestaurantTable) => {
    if (!confirm("¿Eliminar/desactivar esta mesa?")) return;
    setTables((p) => p.filter((x) => x.id !== t.id));
    setSelectedTableId(null);
    try {
      await deleteRestaurantTable(t.id);
      setSaveState("saved");
    } catch (e: any) {
      const msg = String(e?.message || "");
      if (msg.includes("404")) {
        toast.message("La mesa ya no existía en servidor, se quitó del mapa.");
        return;
      }
      toast.error("No se pudo eliminar la mesa");
      await reload();
    }
  };

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const op = opRef.current;
      if (!op) return;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const dx = (e.clientX - op.startX) / zoom;
        const dy = (e.clientY - op.startY) / zoom;
        if (op.type === "drag") {
          const nx = Math.max(0, op.tableStart.x + dx);
          const ny = Math.max(0, op.tableStart.y + dy);
          patchTable(op.id, { x: snapValue(nx, snapOn), y: snapValue(ny, snapOn) });
          return;
        }
        if (op.type === "resize") {
          let { x, y, width, height } = op.tableStart;
          const minW = 40, minH = 40;
          if (op.dir?.includes("e")) width = Math.max(minW, op.tableStart.width + dx);
          if (op.dir?.includes("s")) height = Math.max(minH, op.tableStart.height + dy);
          if (op.dir?.includes("w")) { width = Math.max(minW, op.tableStart.width - dx); x = op.tableStart.x + (op.tableStart.width - width); }
          if (op.dir?.includes("n")) { height = Math.max(minH, op.tableStart.height - dy); y = op.tableStart.y + (op.tableStart.height - height); }
          patchTable(op.id, { x: Math.max(0, snapValue(x, snapOn)), y: Math.max(0, snapValue(y, snapOn)), width: Math.max(minW, snapValue(width, snapOn)), height: Math.max(minH, snapValue(height, snapOn)) });
          return;
        }
        if (op.type === "rotate") {
          const cx = op.tableStart.x + op.tableStart.width / 2;
          const cy = op.tableStart.y + op.tableStart.height / 2;
          const angle = (Math.atan2((e.clientY / zoom) - cy, (e.clientX / zoom) - cx) * 180) / Math.PI + 90;
          patchTable(op.id, { rotation: angle });
        }
      });
    };
    const onUp = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (opRef.current) queueAutosave();
      opRef.current = null;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [zoom, snapOn]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (isInputLike(e.target) || tableModal.open || areaModal.open) return;
      const selected = tables.find((t) => t.id === selectedTableId);
      const meta = e.ctrlKey || e.metaKey;

      if (e.key === "Escape") {
        setSelectedTableId(null);
        setTableCtx({ open: false, x: 0, y: 0, id: null });
        setAreaCtx({ open: false, x: 0, y: 0, id: null });
      }
      if ((e.key === "Delete" || e.key === "Backspace") && selected) {
        e.preventDefault();
        void handleDeleteTable(selected);
      }
      if (meta && e.key.toLowerCase() === "c" && selected) {
        e.preventDefault();
        const { id: _id, ...copy } = selected;
        clipboardRef.current = copy;
      }
      if (meta && e.key.toLowerCase() === "v" && clipboardRef.current) {
        e.preventDefault();
        void duplicateTable({ ...clipboardRef.current, id: -1 } as RestaurantTable);
      }
      if (meta && e.key.toLowerCase() === "d" && selected) {
        e.preventDefault();
        void duplicateTable(selected);
      }
      if (meta && e.key.toLowerCase() === "z") {
        e.preventDefault();
        const u = undoStack.at(-1); if (!u) return;
        setRedoStack((r) => [...r, tables]); setTables(u); setUndoStack((prev) => prev.slice(0, -1)); queueAutosave();
      }
      if (meta && (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))) {
        e.preventDefault();
        const r = redoStack.at(-1); if (!r) return;
        setUndoStack((u) => [...u, tables]); setTables(r); setRedoStack((prev) => prev.slice(0, -1)); queueAutosave();
      }
      if (selected && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        const step = snapOn ? GRID_SIZE : 5;
        const dx = e.key === "ArrowRight" ? step : e.key === "ArrowLeft" ? -step : 0;
        const dy = e.key === "ArrowDown" ? step : e.key === "ArrowUp" ? -step : 0;
        pushHistory();
        patchTable(selected.id, { x: Math.max(0, selected.x + dx), y: Math.max(0, selected.y + dy) });
        queueAutosave();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [tables, selectedTableId, undoStack, redoStack, snapOn, tableModal.open, areaModal.open]);

  if (enabled === null) return <div className="p-6">Cargando...</div>;
  if (!enabled) return <div className="p-6"><Card className="p-6">Mapa de mesas no está activo.</Card></div>;

  return <div className="h-[calc(100vh-16px)] max-h-[100vh] overflow-hidden bg-background p-2">
    <div className="grid h-full min-h-0 min-w-0 grid-cols-1 gap-2 lg:grid-cols-[220px_1fr]">
      <Card className="min-h-0 overflow-auto p-2">
        <div className="mb-2 flex items-center justify-between"><strong className="text-sm">Áreas</strong><Button size="icon" variant="outline" onClick={() => { setAreaForm({ name: "", isActive: true, x: "0", y: "0", width: "320", height: "220", color: "" }); setAreaModal({ open: true }); }}>+</Button></div>
        {areas.map((a) => <button key={a.id} className={cn("mb-1 w-full rounded border p-2 text-left text-sm", selectedAreaId === a.id && "border-primary")} onClick={() => setSelectedAreaId(a.id)} onContextMenu={(e) => { e.preventDefault(); setAreaCtx({ open: true, x: e.clientX, y: e.clientY, id: a.id }); }}>{a.name}</button>)}
      </Card>

      <div className="flex min-h-0 min-w-0 flex-col gap-2 overflow-hidden">
        <Card className="p-2">
          <div className="flex flex-wrap items-center gap-1">
            <Button size="icon" variant="outline" className="h-8 w-8 border-emerald-500/70 bg-slate-900 text-emerald-300 hover:bg-slate-800" title="Volver al menú principal" aria-label="Volver al menú principal" onClick={() => navigate("/")}><ArrowLeft className="h-4 w-4" /></Button>
            <Input className="h-8 w-40" placeholder="Buscar mesa" value={search} onChange={(e) => setSearch(e.target.value)} />
            <Button size="sm" variant="outline" onClick={openNewTableModal}>+ Mesa</Button>
            <Button size="sm" variant="outline" onClick={() => navigate('/pos?mode=tables')}>Vista operativa</Button>
            <Button size="icon" variant="outline" title="Guardar ahora" aria-label="Guardar ahora" onClick={() => void saveNow()}><Save className="h-4 w-4" /></Button>
            <Button size="sm" variant="outline" onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}>-</Button><span className="px-1 text-xs">{Math.round(zoom * 100)}%</span><Button size="sm" variant="outline" onClick={() => setZoom((z) => Math.min(2, z + 0.1))}>+</Button>
            <Label className="ml-1 flex items-center gap-1 text-xs" title="Ajustar a cuadrícula" aria-label="Ajustar a cuadrícula"><Switch checked={snapOn} onCheckedChange={setSnapOn} />Snap {snapOn ? 'ON' : 'OFF'}</Label>
            <Button size="icon" variant="outline" title="Deshacer" aria-label="Deshacer" disabled={!undoStack.length} onClick={() => { const u = undoStack.at(-1); if (!u) return; setRedoStack((r) => [...r, tables]); setTables(u); setUndoStack((p) => p.slice(0, -1)); queueAutosave(); }}><Undo2 className="h-4 w-4"/></Button>
            <Button size="icon" variant="outline" title="Rehacer" aria-label="Rehacer" disabled={!redoStack.length} onClick={() => { const r = redoStack.at(-1); if (!r) return; setUndoStack((u) => [...u, tables]); setTables(r); setRedoStack((p) => p.slice(0, -1)); queueAutosave(); }}><Redo2 className="h-4 w-4"/></Button>
            <span className="ml-auto text-xs text-muted-foreground">{saveState === 'saving' ? 'Guardando...' : saveState === 'saved' ? 'Guardado' : saveState === 'error' ? 'Error al guardar' : 'Cambios pendientes'}</span>
          </div>
        </Card>

        <Card className="min-h-0 flex-1 p-2">
          <div className="h-full min-h-0 min-w-0 overflow-auto rounded border bg-slate-950" onPointerDown={(e) => { if (e.target === e.currentTarget) { setSelectedTableId(null); setTableCtx({ open: false, x: 0, y: 0, id: null }); } }}>
            <div className="relative h-[1300px] w-[1900px]" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
              {filteredTables.map((t) => {
                const selected = selectedTableId === t.id;
                return <div key={t.id} className="absolute" style={{ left: t.x, top: t.y, width: t.width, height: t.height, transform: `rotate(${t.rotation}deg)` }}>
                  <button onDoubleClick={() => { setTableForm({ area: String(t.area), name: t.name, number: String(t.number), capacity: String(t.capacity), shape: t.shape, width: String(t.width), height: String(t.height), rotation: String(t.rotation), color: t.color || '#10b981', isActive: t.isActive, autoName: false }); setTableModal({ open: true, table: t }); }} onContextMenu={(e) => { e.preventDefault(); setSelectedTableId(t.id); setTableCtx({ open: true, x: e.clientX, y: e.clientY, id: t.id }); }} onPointerDown={(e) => { e.stopPropagation(); pushHistory(); setSelectedTableId(t.id); opRef.current = { type: "drag", id: t.id, startX: e.clientX, startY: e.clientY, tableStart: { ...t } }; }} className={cn("h-full w-full border-2 text-white", selected && "ring-2 ring-primary", t.shape === 'round' && 'rounded-full', t.shape === 'square' && 'rounded-md', t.shape === 'rectangle' && 'rounded-lg', t.shape === 'booth' && 'rounded-xl', t.shape === 'bar' && 'rounded-sm')} style={{ backgroundColor: `${t.color || '#10b981'}33`, borderColor: t.color || '#10b981' }}><div className="text-xs"><div className="font-semibold">{t.name}</div><div>Cap. {t.capacity}</div></div></button>
                  {selected ? <>
                    {(["nw", "n", "ne", "e", "se", "s", "sw", "w"] as ResizeDir[]).map((dir) => <div key={dir} onPointerDown={(e) => { e.stopPropagation(); pushHistory(); opRef.current = { type: "resize", id: t.id, dir, startX: e.clientX, startY: e.clientY, tableStart: { ...t } }; }} className="absolute z-20 h-3 w-3 rounded-sm border border-white bg-primary" style={{ left: dir.includes("w") ? -6 : dir.includes("e") ? t.width - 6 : t.width / 2 - 6, top: dir.includes("n") ? -6 : dir.includes("s") ? t.height - 6 : t.height / 2 - 6, cursor: `${dir}-resize` }} />)}
                    <div onPointerDown={(e) => { e.stopPropagation(); pushHistory(); opRef.current = { type: "rotate", id: t.id, startX: e.clientX, startY: e.clientY, tableStart: { ...t } }; }} className="absolute z-20 h-3 w-3 rounded-full border border-white bg-amber-400" style={{ left: t.width / 2 - 6, top: -24, cursor: "grab" }} />
                  </> : null}
                </div>;
              })}
            </div>
          </div>
        </Card>
      </div>
    </div>

    <Dialog open={tableModal.open} onOpenChange={(open) => setTableModal({ open, table: tableModal.table })}><DialogContent><DialogHeader><DialogTitle>{tableModal.table ? 'Editar mesa' : 'Nueva mesa'}</DialogTitle></DialogHeader><div className="grid grid-cols-2 gap-2"><div className="col-span-2"><Label>Área</Label><Select value={tableForm.area} onValueChange={(v) => setTableForm((s) => ({ ...s, area: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{areas.map((a) => <SelectItem key={a.id} value={String(a.id)}>{a.name}</SelectItem>)}</SelectContent></Select></div><div className="col-span-2"><Label>Nombre</Label><Input value={tableForm.name} onChange={(e) => setTableForm((s) => ({ ...s, name: e.target.value, autoName: false }))} /></div><div><Label>Número</Label><Input value={tableForm.number} onChange={(e) => setTableForm((s) => ({ ...s, number: e.target.value, name: s.autoName ? `Mesa ${e.target.value || 1}` : s.name }))} /></div><div><Label>Capacidad</Label><Input value={tableForm.capacity} onChange={(e) => setTableForm((s) => ({ ...s, capacity: e.target.value }))} /></div><div><Label>Forma</Label><Select value={tableForm.shape} onValueChange={(v: RestaurantTable["shape"]) => setTableForm((s) => ({ ...s, shape: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(shapeLabel).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></div><div><Label>Color</Label><Input type="color" value={tableForm.color} onChange={(e) => setTableForm((s) => ({ ...s, color: e.target.value }))} /></div><div><Label>Ancho</Label><Input value={tableForm.width} onChange={(e) => setTableForm((s) => ({ ...s, width: e.target.value }))} /></div><div><Label>Alto</Label><Input value={tableForm.height} onChange={(e) => setTableForm((s) => ({ ...s, height: e.target.value }))} /></div><div><Label>Rotación</Label><Input value={tableForm.rotation} onChange={(e) => setTableForm((s) => ({ ...s, rotation: e.target.value }))} /></div><div className="flex items-center justify-between"><Label>Activa</Label><Switch checked={tableForm.isActive} onCheckedChange={(v) => setTableForm((s) => ({ ...s, isActive: v }))} /></div></div><DialogFooter><Button variant="outline" onClick={() => setTableModal({ open: false })}>Cancelar</Button><Button onClick={async () => { const areaId = Number(tableForm.area || selectedAreaId); const wantedNumber = Number(tableForm.number || 1); const duplicate = tables.some((x) => x.area === areaId && x.number === wantedNumber && x.id !== tableModal.table?.id); if (duplicate) { toast.error("Ya existe una mesa con ese número en esta área."); return; } const payload = { area: areaId, name: tableForm.name, number: wantedNumber, capacity: Number(tableForm.capacity || 1), shape: tableForm.shape, width: Number(tableForm.width || 120), height: Number(tableForm.height || 80), rotation: Number(tableForm.rotation || 0), color: tableForm.color, isActive: tableForm.isActive, x: tableModal.table?.x ?? 120, y: tableModal.table?.y ?? 120 }; if (tableModal.table) { const t = await updateRestaurantTable(tableModal.table.id, payload); setTables((p) => p.map((x) => x.id === t.id ? t : x)); } else { const created = await createRestaurantTable(payload); setTables((p) => [...p, created]); setSelectedTableId(created.id); } setTableModal({ open: false }); setSaveState('saved'); }}>Guardar</Button></DialogFooter></DialogContent></Dialog>

    <Dialog open={areaModal.open} onOpenChange={(open) => setAreaModal({ open, area: areaModal.area })}><DialogContent><DialogHeader><DialogTitle>{areaModal.area ? 'Editar área' : 'Nueva área'}</DialogTitle></DialogHeader><div className="grid grid-cols-2 gap-2"><div className="col-span-2"><Label>Nombre</Label><Input value={areaForm.name} onChange={(e) => setAreaForm((s: any) => ({ ...s, name: e.target.value }))} /></div><div><Label>X</Label><Input value={areaForm.x} onChange={(e) => setAreaForm((s: any) => ({ ...s, x: e.target.value }))} /></div><div><Label>Y</Label><Input value={areaForm.y} onChange={(e) => setAreaForm((s: any) => ({ ...s, y: e.target.value }))} /></div></div><DialogFooter><Button variant="outline" onClick={() => setAreaModal({ open: false })}>Cancelar</Button><Button onClick={async () => { const payload = { name: areaForm.name, isActive: areaForm.isActive, x: Number(areaForm.x || 0), y: Number(areaForm.y || 0) }; const area = areaModal.area ? await updateTableArea(areaModal.area.id, payload) : await createTableArea(payload); setAreaModal({ open: false }); if (areaModal.area) setAreas((p) => p.map((x) => x.id === area.id ? area : x)); else setAreas((p) => [...p, area]); }}>Guardar área</Button></DialogFooter></DialogContent></Dialog>

    {tableCtx.open ? <div className="fixed inset-0 z-50" onClick={() => setTableCtx({ open: false, x: 0, y: 0, id: null })}><Card className="absolute w-56 p-2" style={{ left: Math.min(tableCtx.x, window.innerWidth - 240), top: Math.min(tableCtx.y, window.innerHeight - 250) }} onClick={(e) => e.stopPropagation()}>{(() => { const t = tables.find((x) => x.id === tableCtx.id); if (!t) return null; return <><Button className="h-10 w-full justify-start" variant="ghost" onClick={() => { setTableForm({ area: String(t.area), name: t.name, number: String(t.number), capacity: String(t.capacity), shape: t.shape, width: String(t.width), height: String(t.height), rotation: String(t.rotation), color: t.color || '#10b981', isActive: t.isActive, autoName: false }); setTableModal({ open: true, table: t }); setTableCtx({ open: false, x: 0, y: 0, id: null }); }}>Editar mesa</Button><Button className="h-10 w-full justify-start" variant="ghost" onClick={async () => { await duplicateTable(t); setTableCtx({ open: false, x: 0, y: 0, id: null }); }}>Duplicar mesa</Button><Button className="h-10 w-full justify-start text-red-500" variant="ghost" onClick={async () => { await handleDeleteTable(t); setTableCtx({ open: false, x: 0, y: 0, id: null }); }}>Eliminar/desactivar</Button></>; })()}</Card></div> : null}
    {areaCtx.open ? <div className="fixed inset-0 z-50" onClick={() => setAreaCtx({ open: false, x: 0, y: 0, id: null })}><Card className="absolute w-56 p-2" style={{ left: Math.min(areaCtx.x, window.innerWidth - 240), top: Math.min(areaCtx.y, window.innerHeight - 250) }} onClick={(e) => e.stopPropagation()}>{(() => { const a = areas.find((x) => x.id === areaCtx.id); if (!a) return null; return <><Button className="h-10 w-full justify-start" variant="ghost" onClick={() => { setAreaForm({ name: a.name, isActive: a.isActive, x: String(a.x), y: String(a.y) }); setAreaModal({ open: true, area: a }); setAreaCtx({ open: false, x: 0, y: 0, id: null }); }}>Editar área</Button><Button className="h-10 w-full justify-start text-red-500" variant="ghost" onClick={async () => { if (confirm('¿Eliminar/desactivar esta área?')) { await deleteTableArea(a.id); await reload(); } setAreaCtx({ open: false, x: 0, y: 0, id: null }); }}>Eliminar/desactivar</Button></>; })()}</Card></div> : null}
  </div>;
}
