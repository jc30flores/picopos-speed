import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyAppearanceSettings } from "@/lib/theme";
import { getAppearanceSettings, updateAppearanceSettings, type AppearanceSettings } from "@/lib/api";

const safePalette = ["#1F7A4D", "#2563EB", "#0F766E", "#B45309", "#BE123C", "#6D28D9", "#374151"];

export const AppearanceTab = () => {
  const [settings, setSettings] = useState<AppearanceSettings | null>(null);
  const [color, setColor] = useState("#1F7A4D");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAppearanceSettings()
      .then((value) => {
        setSettings(value);
        setColor(value.primaryColor);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "No se pudo cargar apariencia"));
  }, []);

  const preview = useMemo(() => settings, [settings]);

  const save = async (restoreDefault = false) => {
    setSaving(true);
    try {
      const saved = await updateAppearanceSettings({ primaryColor: color, restoreDefault });
      setSettings(saved);
      setColor(saved.primaryColor);
      applyAppearanceSettings(saved);
      toast.success("Color aplicado. Vuelve a iniciar sesión para cargar la nueva apariencia.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Color inválido");
    } finally {
      setSaving(false);
    }
  };

  if (!preview) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando apariencia...</CardContent></Card>;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Apariencia del sistema</CardTitle>
          <CardDescription>Define un color principal con contraste válido para modo claro y oscuro.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Paleta recomendada</Label>
            <div className="flex flex-wrap gap-2">
              {safePalette.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="h-10 w-10 rounded-md border border-border shadow-sm"
                  style={{ background: item }}
                  title={item}
                  aria-label={`Color ${item}`}
                  onClick={() => setColor(item)}
                />
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="primary-color">Color personalizado</Label>
            <div className="flex gap-2">
              <Input id="primary-color" value={color} onChange={(event) => setColor(event.target.value.toUpperCase())} placeholder="#1F7A4D" />
              <Input type="color" value={/^#[0-9A-F]{6}$/i.test(color) ? color : "#1F7A4D"} onChange={(event) => setColor(event.target.value.toUpperCase())} className="h-10 w-16 p-1" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void save(false)} disabled={saving}>Aplicar</Button>
            <Button variant="outline" onClick={() => void save(true)} disabled={saving}>Restaurar predeterminado</Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {["Claro", "Oscuro"].map((mode) => (
          <Card key={mode} className={mode === "Oscuro" ? "bg-slate-950 text-white" : "bg-white text-slate-950"}>
            <CardHeader>
              <CardTitle className="text-base">Vista previa {mode.toLowerCase()}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-md border p-3" style={{ borderColor: preview.colorPrimaryBorder }}>
                <div className="mb-2 font-semibold" style={{ color: preview.colorPrimaryText }}>Tarjeta</div>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-md px-3 py-2 text-sm font-semibold" style={{ background: preview.colorPrimary, color: preview.colorPrimaryContrast }}>Principal</button>
                  <button className="rounded-md border px-3 py-2 text-sm font-semibold" style={{ borderColor: preview.colorPrimaryBorder, color: preview.colorPrimaryText }}>Secundario</button>
                  <span className="rounded-full px-2 py-1 text-xs font-semibold" style={{ background: preview.colorPrimarySoft, color: preview.colorPrimaryText }}>Badge</span>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-md p-3" style={{ background: preview.colorPrimary }}>
                <div className="h-8 w-1 rounded-full bg-white/80" />
                <span className="font-semibold" style={{ color: preview.colorPrimaryContrast }}>Sidebar/menu</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Toggle</span>
                <span className="h-6 w-11 rounded-full p-1" style={{ background: preview.colorPrimary }}><span className="block h-4 w-4 translate-x-5 rounded-full bg-white" /></span>
              </div>
              <div className="flex h-20 items-end gap-2">
                {[38, 62, 45, 75, 58].map((height, idx) => <span key={idx} className="w-full rounded-t" style={{ height, background: idx % 2 ? preview.colorPrimaryHover : preview.colorPrimary }} />)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};
