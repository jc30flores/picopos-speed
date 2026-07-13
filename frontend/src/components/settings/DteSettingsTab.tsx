import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getDteSettings, updateDteSettings, type DteSettings } from "@/lib/api";

export const DteSettingsTab = () => {
  const [settings, setSettings] = useState<DteSettings | null>(null);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getDteSettings()
      .then(setSettings)
      .catch((error) => {
        const message = error instanceof Error ? error.message : "No se pudo cargar DTE";
        setError(message);
        toast.error(message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const persist = async (patch: Partial<DteSettings> & { apiToken?: string }) => {
    setSaving(true);
    try {
      const saved = await updateDteSettings(patch);
      setSettings(saved);
      setToken("");
      toast.success(saved.haciendaEnabled ? "Configuración DTE guardada" : "Facturación electrónica desactivada");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar DTE");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !settings) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando Hacienda/DTE...</CardContent></Card>;
  if (error && !settings) {
    return (
      <Card>
        <CardContent className="space-y-3 pt-6">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" onClick={load}>Reintentar</Button>
        </CardContent>
      </Card>
    );
  }
  if (!settings) return null;

  const disabled = !settings.canManageTechnical || saving;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Configuración Hacienda / DTE</CardTitle>
          <CardDescription>{settings.message}</CardDescription>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <div className="font-semibold">Envíos Hacienda activos</div>
              <p className="text-xs text-muted-foreground">Si está apagado, el POS opera localmente y no llama API externa.</p>
            </div>
            <Switch checked={settings.haciendaEnabled} disabled={disabled} onCheckedChange={(checked) => void persist({ haciendaEnabled: checked })} />
          </div>
          <div className="space-y-2">
            <Label>Ambiente</Label>
            <Select value={settings.ambiente} disabled={disabled} onValueChange={(value) => void persist({ ambiente: value as "00" | "01" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="00">Pruebas</SelectItem>
                <SelectItem value="01">Producción</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>URL API</Label>
            <Input value={settings.baseUrl} disabled={disabled} onChange={(event) => setSettings({ ...settings, baseUrl: event.target.value })} onBlur={() => void persist({ baseUrl: settings.baseUrl })} placeholder="https://..." />
          </div>
          <div className="space-y-2">
            <Label>API token/key</Label>
            <Input value={token} disabled={disabled} onChange={(event) => setToken(event.target.value)} placeholder={settings.apiTokenMasked || "Nuevo token"} />
          </div>
          <div className="space-y-2">
            <Label>Timeout segundos</Label>
            <Input type="number" min={1} max={120} value={settings.timeoutSeconds} disabled={disabled} onChange={(event) => setSettings({ ...settings, timeoutSeconds: Number(event.target.value) })} />
          </div>
          <div className="space-y-2">
            <Label>Reintentos</Label>
            <Input type="number" min={0} max={10} value={settings.retryCount} disabled={disabled} onChange={(event) => setSettings({ ...settings, retryCount: Number(event.target.value) })} />
          </div>
          <div className="lg:col-span-2 flex flex-wrap items-center gap-2">
            <Button disabled={disabled} onClick={() => void persist({ ...settings, apiToken: token || undefined })}>Guardar configuración técnica</Button>
            <span className="text-sm text-muted-foreground">Estado: {settings.status}</span>
          </div>
        </CardContent>
      </Card>
      {!settings.canManageTechnical ? (
        <p className="text-sm text-muted-foreground">Solo superadmin puede cambiar URL, token, ambiente producción y activación de Hacienda.</p>
      ) : null}
    </div>
  );
};
