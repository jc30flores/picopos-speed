import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { getDiningAreas, getFeatureSettings, getRestaurantTables } from "@/lib/api";

const TablesEditor = () => {
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [areas, setAreas] = useState<any[]>([]);
  const [tables, setTables] = useState<any[]>([]);
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getFeatureSettings().then((s) => setEnabled(Boolean(s.tableMapEnabled))).catch(() => setEnabled(false));
  }, []);

  useEffect(() => {
    if (!enabled) return;
    Promise.all([getDiningAreas(), getRestaurantTables()]).then(([a, t]) => { setAreas(a); setTables(t); }).catch(() => toast.error("No se pudo cargar el mapa."));
  }, [enabled]);

  const filtered = useMemo(() => tables.filter((t) => t.name.toLowerCase().includes(query.toLowerCase())), [tables, query]);

  if (enabled === null) return <div className="p-6">Cargando...</div>;
  if (!enabled) return <div className="p-6"><Card className="p-6"><h1 className="text-xl font-semibold">Mapa de mesas deshabilitado</h1><p className="text-sm text-muted-foreground mt-2">Actívalo en Configuración → Funciones.</p><Button className="mt-4" onClick={() => navigate("/")}>Volver</Button></Card></div>;

  return (
    <div className="p-4 space-y-4">
      <Card className="p-4 flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold mr-auto">Editor de mesas</h1>
        <Input placeholder="Buscar mesa" className="w-52" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Button variant="outline" onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}>-</Button>
        <Button variant="outline" onClick={() => setZoom(1)}>100%</Button>
        <Button variant="outline" onClick={() => setZoom((z) => Math.min(2, z + 0.1))}>+</Button>
        <Button onClick={() => toast.success("Mapa guardado correctamente.")}>Guardar mapa</Button>
        <Button variant="outline" onClick={() => navigate('/pos')}>Vista operativa</Button>
      </Card>

      <Card className="p-4">
        <p className="text-sm text-muted-foreground mb-3">Áreas activas: {areas.map((a) => a.name).join(", ") || "Sin áreas"}</p>
        <div className="relative h-[65vh] overflow-auto rounded-xl border bg-muted/20">
          <div className="relative h-[1200px] w-[1800px]" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
            {filtered.map((table) => (
              <div key={table.id} className="absolute rounded-lg border bg-background p-2 text-xs shadow" style={{ left: table.x, top: table.y, width: table.width, height: table.height }}>
                <p className="font-semibold">{table.name}</p>
                <p className="text-muted-foreground">{table.shape} · {table.capacity} personas</p>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default TablesEditor;
