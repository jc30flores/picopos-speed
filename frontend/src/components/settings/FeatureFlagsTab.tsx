import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getFeatureSettings, getFeatureSettingsOptions, updateFeatureSettings, type FeatureSettings, type FeatureSettingsOptions } from "@/lib/api";

const defaultState: FeatureSettings = {
  kioskEnabled: true,
  customerDisplayEnabled: true,
  kitchenDisplayEnabled: true,
  cashCloseExpectedTotalsControlEnabled: true,
  cashCloseExpectedTotalsAllowedRoles: [],
  cashCloseExpectedTotalsVisibleFields: [],
  inventoryStockPolicy: "allow",
};

export const FeatureFlagsTab = () => {
  const [settings, setSettings] = useState<FeatureSettings>(defaultState);
  const [options, setOptions] = useState<FeatureSettingsOptions>({ roles: [], cashCloseExpectedTotalFields: [] });
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, o] = await Promise.all([getFeatureSettings(), getFeatureSettingsOptions()]);
      setSettings(s);
      setOptions(o);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudieron cargar funciones");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const persist = async (patch: Partial<FeatureSettings>) => {
    const previous = settings;
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      const saved = await updateFeatureSettings(patch);
      setSettings(saved);
      toast.success("Configuración guardada");
    } catch (error) {
      setSettings(previous);
      toast.error(error instanceof Error ? error.message : "No se pudo guardar");
    }
  };

  const toggleRole = (code: string) => {
    const current = settings.cashCloseExpectedTotalsAllowedRoles;
    const next = current.includes(code) ? current.filter((item) => item !== code) : [...current, code];
    void persist({ cashCloseExpectedTotalsAllowedRoles: next });
  };
  const toggleField = (code: string) => {
    const current = settings.cashCloseExpectedTotalsVisibleFields;
    const next = current.includes(code) ? current.filter((item) => item !== code) : [...current, code];
    void persist({ cashCloseExpectedTotalsVisibleFields: next });
  };

  if (loading) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando funciones...</CardContent></Card>;

  return (
    <div className="space-y-4">
      <Card><CardHeader><CardTitle>KIOSK</CardTitle><CardDescription>Mostrar u ocultar el módulo KIOSK para todos los usuarios.</CardDescription></CardHeader><CardContent className="flex justify-end"><Switch checked={settings.kioskEnabled} onCheckedChange={(checked) => void persist({ kioskEnabled: checked })} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Pantalla Cliente</CardTitle><CardDescription>Mostrar u ocultar la pantalla cliente para todos los usuarios.</CardDescription></CardHeader><CardContent className="flex justify-end"><Switch checked={settings.customerDisplayEnabled} onCheckedChange={(checked) => void persist({ customerDisplayEnabled: checked })} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Pantalla Cocina</CardTitle><CardDescription>Mostrar u ocultar Cocina para todos los usuarios.</CardDescription></CardHeader><CardContent className="flex justify-end"><Switch checked={settings.kitchenDisplayEnabled} onCheckedChange={(checked) => void persist({ kitchenDisplayEnabled: checked })} /></CardContent></Card>

      <Card>
        <CardHeader><CardTitle>Inventario avanzado</CardTitle><CardDescription>Activa proveedores, costos y órdenes de compra dentro del inventario.</CardDescription></CardHeader>
        <CardContent className="flex justify-end"><Switch checked={settings.inventoryAdvancedEnabled} onCheckedChange={(checked) => void persist({ inventoryAdvancedEnabled: checked })} /></CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Política de stock insuficiente</CardTitle>
          <CardDescription>Define cómo debe comportarse el POS cuando una venta necesita más inventario del disponible.</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={settings.inventoryStockPolicy} onValueChange={(value) => void persist({ inventoryStockPolicy: value as FeatureSettings["inventoryStockPolicy"] })}>
            <SelectTrigger className="max-w-sm"><SelectValue placeholder="Política de stock" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="allow">Permitir venta</SelectItem>
              <SelectItem value="warn">Advertir antes de vender</SelectItem>
              <SelectItem value="block">Bloquear venta</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Totales esperados en cierre de caja</CardTitle><CardDescription>Controlar visibilidad de totales esperados.</CardDescription></CardHeader>
        <CardContent className="flex items-center justify-between">
          <Switch checked={settings.cashCloseExpectedTotalsControlEnabled} onCheckedChange={(checked) => void persist({ cashCloseExpectedTotalsControlEnabled: checked })} />
          <Button onClick={() => setOpen(true)}>Configurar permisos</Button>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader><DialogTitle>Configurar permisos de totales esperados</DialogTitle></DialogHeader>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-3">
              <div className="flex items-center justify-between"><h4 className="font-semibold">Roles autorizados</h4><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => void persist({ cashCloseExpectedTotalsAllowedRoles: options.roles.map((r) => r.code) })}>Todos</Button><Button size="sm" variant="outline" onClick={() => void persist({ cashCloseExpectedTotalsAllowedRoles: [] })}>Ninguno</Button></div></div>
              <div className="space-y-2">{options.roles.map((role) => <Button key={role.code} type="button" className="w-full justify-start" variant={settings.cashCloseExpectedTotalsAllowedRoles.includes(role.code) ? "default" : "outline"} onClick={() => toggleRole(role.code)}>{role.label}</Button>)}</div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between"><h4 className="font-semibold">Datos visibles</h4><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => void persist({ cashCloseExpectedTotalsVisibleFields: options.cashCloseExpectedTotalFields.map((f) => f.code) })}>Todos</Button><Button size="sm" variant="outline" onClick={() => void persist({ cashCloseExpectedTotalsVisibleFields: [] })}>Ninguno</Button></div></div>
              <div className="space-y-2">{options.cashCloseExpectedTotalFields.map((field) => <Button key={field.code} type="button" className="w-full justify-start" variant={settings.cashCloseExpectedTotalsVisibleFields.includes(field.code) ? "default" : "outline"} onClick={() => toggleField(field.code)}>{field.label}</Button>)}</div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
