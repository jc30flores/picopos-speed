import { useEffect, useState, type ReactNode } from "react";
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
  inventoryAdvancedEnabled: false,
  posProductImagesEnabled: false,
};

type ToggleSettingKey = "posProductImagesEnabled" | "kioskEnabled" | "customerDisplayEnabled" | "kitchenDisplayEnabled" | "inventoryAdvancedEnabled" | "cashCloseExpectedTotalsControlEnabled";

type ToggleSetting = {
  key: ToggleSettingKey;
  title: string;
  description: string;
  action?: ReactNode;
};

const featureSections: Array<{ title: string; eyebrow: string; items: ToggleSetting[] }> = [
  {
    title: "POS",
    eyebrow: "Venta rápida",
    items: [
      {
        key: "posProductImagesEnabled",
        title: "Imágenes de productos en POS",
        description: "Muestra las imágenes guardadas de los productos en las tarjetas del POS.",
      },
      { key: "kioskEnabled", title: "KIOSK", description: "Mostrar u ocultar el módulo KIOSK para todos los usuarios." },
    ],
  },
  {
    title: "Pantallas",
    eyebrow: "Operación",
    items: [
      { key: "customerDisplayEnabled", title: "Pantalla Cliente", description: "Mostrar u ocultar la pantalla cliente para todos los usuarios." },
      { key: "kitchenDisplayEnabled", title: "Pantalla Cocina", description: "Mostrar u ocultar Cocina para todos los usuarios." },
    ],
  },
  {
    title: "Inventario",
    eyebrow: "Stock",
    items: [
      { key: "inventoryAdvancedEnabled", title: "Inventario avanzado", description: "Activa proveedores, costos y órdenes de compra dentro del inventario." },
    ],
  },
];

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

  const cashSetting: ToggleSetting = {
    key: "cashCloseExpectedTotalsControlEnabled",
    title: "Totales esperados en cierre de caja",
    description: "Controlar visibilidad de totales esperados.",
    action: <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Permisos</Button>,
  };

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border bg-gradient-to-br from-muted/40 via-background to-background p-4 shadow-sm">
        <h3 className="text-lg font-semibold">Funciones experimentales y módulos</h3>
        <p className="text-sm text-muted-foreground">Activa solo lo necesario. Los cambios se guardan de inmediato y mantienen las llaves existentes.</p>
      </div>

      {[...featureSections, { title: "Seguridad / Caja", eyebrow: "Control", items: [cashSetting] }].map((section) => (
        <section key={section.title} className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{section.eyebrow}</span>
            <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{section.title}</h4>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {section.items.map((item) => (
              <Card key={item.key} className="border-border/70 bg-card/80 shadow-sm">
                <CardContent className="flex min-h-[104px] items-center justify-between gap-3 p-4">
                  <div className="min-w-0 space-y-1">
                    <h5 className="font-semibold leading-tight">{item.title}</h5>
                    <p className="text-xs leading-snug text-muted-foreground">{item.description}</p>
                    {item.action ? <div className="pt-1">{item.action}</div> : null}
                  </div>
                  <Switch checked={Boolean(settings[item.key])} onCheckedChange={(checked) => void persist({ [item.key]: checked } as Partial<FeatureSettings>)} />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}

      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Stock</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Inventario</h4>
        </div>
        <Card className="border-border/70 bg-card/80 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Política de stock insuficiente</CardTitle>
            <CardDescription className="text-xs">Define cómo debe comportarse el POS cuando una venta necesita más inventario del disponible.</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
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
      </section>

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
