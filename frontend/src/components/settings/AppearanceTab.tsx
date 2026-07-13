import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyAppearanceSettings } from "@/lib/theme";
import { ApiRequestError, getAppearanceSettings, updateAppearanceSettings, type AppearanceSettings } from "@/lib/api";

const safePalette = ["#1F7A4D", "#2563EB", "#0F766E", "#0284C7", "#0891B2", "#6D28D9", "#A21CAF", "#DB2777", "#BE123C", "#B45309", "#B7791F", "#374151", "#111827", "#0D9488"];

const hexRegex = /^#[0-9A-F]{6}$/i;

const mixHex = (hex: string, target: string, ratio: number) => {
  const parse = (value: string) => {
    const cleaned = value.replace("#", "");
    return [0, 2, 4].map((idx) => parseInt(cleaned.slice(idx, idx + 2), 16));
  };
  const [r, g, b] = parse(hex);
  const [tr, tg, tb] = parse(target);
  const toHex = (value: number) => Math.round(value).toString(16).padStart(2, "0").toUpperCase();
  return `#${toHex(r + (tr - r) * ratio)}${toHex(g + (tg - g) * ratio)}${toHex(b + (tb - b) * ratio)}`;
};

const luminance = (hex: string) => {
  const cleaned = hex.replace("#", "");
  const channels = [0, 2, 4].map((idx) => parseInt(cleaned.slice(idx, idx + 2), 16) / 255).map((value) => (
    value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  ));
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};

const buildPreviewSettings = (base: AppearanceSettings, draftColor: string): AppearanceSettings => {
  if (!hexRegex.test(draftColor)) return base;
  const color = draftColor.toUpperCase();
  const isLight = luminance(color) > 0.45;
  const hover = mixHex(color, isLight ? "#0F172A" : "#FFFFFF", 0.18);
  const soft = mixHex(color, "#FFFFFF", 0.82);
  const border = mixHex(color, "#FFFFFF", 0.45);
  const text = mixHex(color, isLight ? "#0F172A" : "#FFFFFF", isLight ? 0.5 : 0.45);
  const contrast = isLight ? "#0F172A" : "#FFFFFF";
  return {
    ...base,
    primaryColor: color,
    colorPrimary: color,
    colorPrimaryHover: hover,
    colorPrimarySoft: soft,
    colorPrimaryBorder: border,
    colorPrimaryText: text,
    colorPrimaryContrast: contrast,
    cssVariables: {
      ...base.cssVariables,
      "--color-primary": color,
      "--color-primary-hover": hover,
      "--color-primary-soft": soft,
      "--color-primary-border": border,
      "--color-primary-text": text,
      "--color-primary-contrast": contrast,
      "--color-primary-muted": soft,
      "--color-primary-surface": soft,
    },
  };
};

export const AppearanceTab = () => {
  const [settings, setSettings] = useState<AppearanceSettings | null>(null);
  const [activeColor, setActiveColor] = useState("#1F7A4D");
  const [draftColor, setDraftColor] = useState("#1F7A4D");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const load = () => {
    setLoading(true);
    setError(null);
    getAppearanceSettings()
      .then((value) => {
        setSettings(value);
        setActiveColor(value.primaryColor);
        setDraftColor(value.primaryColor);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "No se pudo cargar apariencia";
        setError(message);
        toast.error(message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const isDraftHexValid = hexRegex.test(draftColor);
  const hasChanges = draftColor.toUpperCase() !== activeColor.toUpperCase();
  const preview = useMemo(() => settings ? buildPreviewSettings(settings, draftColor) : null, [settings, draftColor]);

  const save = async (restoreDefault = false) => {
    if (!restoreDefault && !isDraftHexValid) {
      setError("Usa formato HEX completo, por ejemplo #2563EB.");
      setSuggestions(["#2563EB", "#0F766E", "#DB2777", "#B7791F"]);
      return;
    }
    if (restoreDefault && !window.confirm("Se restaurará el color principal predeterminado de GastroPOSV.")) return;
    setSaving(true);
    setError(null);
    setSuggestions([]);
    try {
      const saved = await updateAppearanceSettings({ primaryColor: draftColor, restoreDefault });
      setSettings(saved);
      setActiveColor(saved.primaryColor);
      setDraftColor(saved.primaryColor);
      applyAppearanceSettings(saved);
      toast.success("Color aplicado.");
    } catch (error) {
      const payload = error instanceof ApiRequestError && error.payload && typeof error.payload === "object" ? error.payload as { message?: string; suggestions?: string[] } : null;
      const message = payload?.message || (error instanceof Error ? error.message : "Color inválido");
      setError(message);
      setSuggestions(Array.isArray(payload?.suggestions) ? payload.suggestions : []);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  if (loading && !preview) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando apariencia...</CardContent></Card>;
  if (error && !preview) {
    return (
      <Card>
        <CardContent className="space-y-3 pt-6">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" onClick={load}>Reintentar</Button>
        </CardContent>
      </Card>
    );
  }
  if (!preview) return null;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Apariencia del sistema</CardTitle>
          <CardDescription>Define un color principal con contraste válido para modo claro y oscuro.</CardDescription>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {suggestions.length ? (
            <div className="flex flex-wrap gap-2 pt-2">
              {suggestions.map((item) => (
                <Button key={item} size="sm" variant="outline" onClick={() => setDraftColor(item.toUpperCase())}>
                  {item}
                </Button>
              ))}
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Paleta recomendada</Label>
            <div className="flex flex-wrap gap-2">
              {(settings?.palette?.length ? settings.palette : safePalette).map((item) => (
                <button
                  key={item}
                  type="button"
                  className="h-10 w-10 rounded-md border border-border shadow-sm"
                  style={{ background: item }}
                  title={item}
                  aria-label={`Color ${item}`}
                  onClick={() => {
                    setDraftColor(item.toUpperCase());
                    setError(null);
                    setSuggestions([]);
                  }}
                />
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="primary-color">Color personalizado</Label>
            <div className="flex gap-2">
              <Input id="primary-color" value={draftColor} onChange={(event) => setDraftColor(event.target.value.toUpperCase())} placeholder="#1F7A4D" aria-invalid={!isDraftHexValid} />
              <Input type="color" value={isDraftHexValid ? draftColor : "#1F7A4D"} onChange={(event) => setDraftColor(event.target.value.toUpperCase())} className="h-10 w-16 p-1" />
            </div>
            {!isDraftHexValid ? <p className="text-xs text-destructive">Usa formato HEX completo, por ejemplo #2563EB.</p> : null}
            <p className="text-xs text-muted-foreground">
              Vista previa: {draftColor.toUpperCase()} · Aplicado: {activeColor.toUpperCase()}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void save(false)} disabled={saving || !hasChanges || !isDraftHexValid}>{saving ? "Aplicando..." : "Aplicar"}</Button>
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
