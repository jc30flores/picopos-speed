import { useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { deleteTicketLogo, getFeatureSettings, getFeatureSettingsOptions, getTicketSettings, updateFeatureSettings, uploadTicketLogo, type FeatureSettings, type FeatureSettingsOptions } from "@/lib/api";
import { useAuth } from "@/context/useAuth";
import { loadAppearanceSettings } from "@/lib/theme";

const defaultState: FeatureSettings = {
  posEnabled: true,
  openOrdersEnabled: true,
  kioskEnabled: true,
  customerDisplayEnabled: true,
  kitchenDisplayEnabled: true,
  menuDiscountsEnabled: true,
  reportsEnabled: true,
  clientsEnabled: true,
  settingsEnabled: true,
  cashCloseExpectedTotalsControlEnabled: true,
  cashCloseExpectedTotalsAllowedRoles: [],
  cashCloseExpectedTotalsVisibleFields: [],
  inventoryStockPolicy: "allow",
  inventoryAdvancedEnabled: false,
  posProductImagesEnabled: false,
  tableMapEnabled: false,
  operationMode: "quick_pos",
  defaultPosEntry: "quick_pos",
  allowTableMerge: true,
  allowTableTransfer: true,
  allowSplitByGuest: true,
  allowSplitByItem: true,
  posQuickSalesButtonMode: "last_sale",
  posQuickSalesHistoryScope: "current_shift",
  posQuickSalesHistoryWindowMinutes: 60,
};

type ToggleSettingKey =
  | "posEnabled"
  | "openOrdersEnabled"
  | "posProductImagesEnabled"
  | "tableMapEnabled"
  | "kioskEnabled"
  | "customerDisplayEnabled"
  | "kitchenDisplayEnabled"
  | "menuDiscountsEnabled"
  | "inventoryAdvancedEnabled"
  | "reportsEnabled"
  | "clientsEnabled"
  | "settingsEnabled"
  | "cashCloseExpectedTotalsControlEnabled";

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
      { key: "posEnabled", title: "POS", description: "Mostrar u ocultar venta rápida/POS." },
      { key: "openOrdersEnabled", title: "Pedidos clientes", description: "Mostrar u ocultar pedidos abiertos y pendientes." },
      {
        key: "posProductImagesEnabled",
        title: "Imágenes de productos en POS",
        description: "Muestra las imágenes guardadas de los productos en las tarjetas del POS.",
      },
      { key: "tableMapEnabled", title: "Mapa de mesas", description: "Activa el modo restaurante con mapa de mesas, editor de salón y órdenes por mesa." },
      { key: "kioskEnabled", title: "KIOSK", description: "Mostrar u ocultar el módulo KIOSK para todos los usuarios." },
    ],
  },
  {
    title: "Pantallas",
    eyebrow: "Operación",
    items: [
      { key: "customerDisplayEnabled", title: "Pantalla Cliente", description: "Mostrar u ocultar la pantalla cliente para todos los usuarios." },
      { key: "kitchenDisplayEnabled", title: "Pantalla Cocina", description: "Mostrar u ocultar Cocina para todos los usuarios." },
      { key: "menuDiscountsEnabled", title: "Menú & descuentos", description: "Mostrar u ocultar gestión de menú y descuentos." },
    ],
  },
  {
    title: "Inventario",
    eyebrow: "Stock",
    items: [
      { key: "inventoryAdvancedEnabled", title: "Inventario avanzado", description: "Activa proveedores, costos y órdenes de compra dentro del inventario." },
    ],
  },
  {
    title: "Reportes y clientes",
    eyebrow: "Administración",
    items: [
      { key: "reportsEnabled", title: "Reportes", description: "Mostrar u ocultar reportes y registros." },
      { key: "clientsEnabled", title: "Clientes", description: "Mostrar u ocultar gestión de clientes." },
      { key: "settingsEnabled", title: "Configuración para admins", description: "Superadmin siempre conserva acceso para reactivar módulos." },
    ],
  },
];

const quickSalesModes = [
  { value: "last_sale", title: "Última venta", description: "Un clic reimprime el ticket local de la última venta. Ideal para cajeros." },
  { value: "history", title: "Historial", description: "Muestra ventas recientes para imprimir ticket local. Solo gerente/admin." },
  { value: "hidden", title: "Oculto", description: "No mostrar este botón en el POS." },
] as const;

const quickSalesWindows = [
  { value: 15, label: "15 minutos" },
  { value: 30, label: "30 minutos" },
  { value: 60, label: "1 hora" },
  { value: 120, label: "2 horas" },
  { value: 240, label: "4 horas" },
  { value: 1440, label: "Hoy" },
] as const;

const operationModes = [
  {
    value: "quick_pos",
    title: "POS rápido",
    description: "Entra directo a caja rápida. Oculta el mapa y el editor de mesas del menú principal.",
  },
  {
    value: "table_service",
    title: "Servicio en mesas",
    description: "El POS abre el mapa de mesas primero para tomar órdenes por mesa o persona.",
  },
  {
    value: "both",
    title: "Ambos",
    description: "Permite venta rápida y servicio en mesas en la misma instalación.",
  },
] as const;

export const FeatureFlagsTab = () => {
  const { user } = useAuth();
  const isSuperadmin = Boolean(user?.permissions?.isSuperadmin || user?.role === "superadmin");
  const [settings, setSettings] = useState<FeatureSettings>(defaultState);
  const [options, setOptions] = useState<FeatureSettingsOptions>({ roles: [], cashCloseExpectedTotalFields: [] });
  const [ticketLogoUrl, setTicketLogoUrl] = useState<string | null>(null);
  const [ticketLogoError, setTicketLogoError] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, o, ticket] = await Promise.all([getFeatureSettings(), getFeatureSettingsOptions(), getTicketSettings()]);
      setSettings(s);
      setOptions(o);
      setTicketLogoUrl(ticket.ticketLogoUrl);
      setTicketLogoError(false);
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

  const handleLogoSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) {
      toast.error("Solo se permiten imágenes PNG o JPG.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error("El logo no debe superar 2 MB.");
      return;
    }
    setLogoBusy(true);
    try {
      const saved = await uploadTicketLogo(file);
      setTicketLogoUrl(saved.ticketLogoUrl);
      setTicketLogoError(false);
      void loadAppearanceSettings();
      toast.success("Logo de ticket guardado");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el logo");
    } finally {
      setLogoBusy(false);
    }
  };

  const handleRemoveLogo = async () => {
    setLogoBusy(true);
    try {
      const saved = await deleteTicketLogo();
      setTicketLogoUrl(saved.ticketLogoUrl);
      setTicketLogoError(false);
      void loadAppearanceSettings();
      toast.success("Logo de ticket eliminado");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo quitar el logo");
    } finally {
      setLogoBusy(false);
    }
  };

  if (loading) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando funciones...</CardContent></Card>;

  const cashSetting: ToggleSetting = {
    key: "cashCloseExpectedTotalsControlEnabled",
    title: "Totales esperados en cierre de caja",
    description: "Controlar visibilidad de totales esperados.",
    action: <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Permisos</Button>,
  };
  const visibleFeatureSections = isSuperadmin
    ? featureSections
    : featureSections.filter((section) => section.title === "Inventario");
  const visibleOperationalSections = [
    ...visibleFeatureSections,
    { title: "Seguridad / Caja", eyebrow: "Control", items: [cashSetting] },
    ...(!isSuperadmin
      ? [{
        title: "Personalización visual",
        eyebrow: "Visual",
        items: [{
          key: "posProductImagesEnabled" as ToggleSettingKey,
          title: "Imágenes de productos en POS",
          description: "Muestra las imágenes guardadas de los productos en las tarjetas del POS.",
        }],
      }]
      : []),
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border bg-gradient-to-br from-muted/40 via-background to-background p-4 shadow-sm">
        <h3 className="text-lg font-semibold">Funciones experimentales y módulos</h3>
        <p className="text-sm text-muted-foreground">Activa solo lo necesario. Los cambios se guardan de inmediato y mantienen las llaves existentes.</p>
      </div>

      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Operación</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Modo del restaurante</h4>
        </div>
        <Card className="gp-primary-border bg-card/90 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Modo de operación</CardTitle>
            <CardDescription className="text-xs">Define si esta instalación trabaja como caja rápida, servicio en mesas o ambos.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div className="grid gap-2 md:grid-cols-3">
              {operationModes.map((mode) => {
                const selected = settings.operationMode === mode.value;
                return (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => {
                      const nextEntry = mode.value === "table_service" ? "table_map" : "quick_pos";
                      void persist({
                        operationMode: mode.value,
                        tableMapEnabled: mode.value !== "quick_pos",
                        defaultPosEntry: nextEntry,
                      });
                    }}
                    className={cn(
                      "rounded-xl border p-3 text-left transition",
                      selected ? "gp-primary-border gp-primary-soft shadow-sm" : "border-border/70 bg-background/40 hover:border-[var(--color-primary-border)]"
                    )}
                  >
                    <div className="font-semibold">{mode.title}</div>
                    <p className="mt-1 text-xs leading-snug text-muted-foreground">{mode.description}</p>
                  </button>
                );
              })}
            </div>
            {settings.operationMode !== "quick_pos" ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-sm font-semibold">Entrada al POS</div>
                  <Select
                    value={settings.defaultPosEntry}
                    onValueChange={(value) => void persist({ defaultPosEntry: value as FeatureSettings["defaultPosEntry"] })}
                  >
                    <SelectTrigger><SelectValue placeholder="Entrada inicial" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="table_map">Mapa de mesas</SelectItem>
                      <SelectItem value="quick_pos">POS rápido</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 text-sm">
                  {[
                    ["allowTableMerge", "Permitir unir mesas"],
                    ["allowTableTransfer", "Permitir mover mesa"],
                    ["allowSplitByGuest", "Dividir por persona"],
                    ["allowSplitByItem", "Dividir por productos"],
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center justify-between rounded-lg border bg-background/50 px-3 py-2">
                      <span>{label}</span>
                      <Switch
                        checked={Boolean(settings[key as keyof FeatureSettings])}
                        onCheckedChange={(checked) => void persist({ [key]: checked } as Partial<FeatureSettings>)}
                      />
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      {visibleOperationalSections.map((section) => (
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
          <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">POS</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Control rápido</h4>
        </div>
        <Card className="gp-primary-border bg-card/90 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Botón rápido de ventas en POS</CardTitle>
            <CardDescription className="text-xs">Define si el botón del POS reimprime la última venta, muestra historial autorizado o queda oculto.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div className="grid gap-2 md:grid-cols-3">
              {quickSalesModes.map((mode) => {
                const selected = settings.posQuickSalesButtonMode === mode.value;
                return (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => void persist({ posQuickSalesButtonMode: mode.value })}
                    className={cn(
                      "rounded-xl border p-3 text-left transition",
                      selected ? "gp-primary-border gp-primary-soft shadow-sm" : "border-border/70 bg-background/40 hover:border-[var(--color-primary-border)]",
                    )}
                  >
                    <div className="font-semibold">{mode.title}</div>
                    <p className="mt-1 text-xs leading-snug text-muted-foreground">{mode.description}</p>
                  </button>
                );
              })}
            </div>

            {settings.posQuickSalesButtonMode === "history" ? (
              <div className="space-y-3 rounded-xl border border-border/70 bg-background/50 p-3">
                <div>
                  <div className="text-sm font-semibold">Qué ventas mostrar</div>
                  <p className="text-xs text-muted-foreground">El historial solo está disponible para gerente/admin y respeta esta ventana.</p>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => void persist({ posQuickSalesHistoryScope: "current_shift" })}
                    className={cn("rounded-lg border p-3 text-left text-sm", settings.posQuickSalesHistoryScope === "current_shift" ? "gp-primary-border gp-primary-soft" : "border-border/70")}
                  >
                    Última apertura de caja
                  </button>
                  <button
                    type="button"
                    onClick={() => void persist({ posQuickSalesHistoryScope: "time_window" })}
                    className={cn("rounded-lg border p-3 text-left text-sm", settings.posQuickSalesHistoryScope === "time_window" ? "gp-primary-border gp-primary-soft" : "border-border/70")}
                  >
                    Período hacia atrás
                  </button>
                </div>
                {settings.posQuickSalesHistoryScope === "time_window" ? (
                  <Select value={String(settings.posQuickSalesHistoryWindowMinutes)} onValueChange={(value) => void persist({ posQuickSalesHistoryWindowMinutes: Number(value) as FeatureSettings["posQuickSalesHistoryWindowMinutes"] })}>
                    <SelectTrigger className="max-w-xs"><SelectValue placeholder="Período" /></SelectTrigger>
                    <SelectContent>
                      {quickSalesWindows.map((window) => <SelectItem key={window.value} value={String(window.value)}>{window.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Tickets</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Personalización visual</h4>
        </div>
        <Card className="border-border/70 bg-card/80 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Logo para ticket</CardTitle>
            <CardDescription className="text-xs">Sube un logo PNG o JPG para mostrarlo centrado en los tickets de venta. Tamaño máximo: 2 MB.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 pt-0 md:flex-row md:items-center md:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-24 w-36 items-center justify-center overflow-hidden rounded-lg border bg-muted/30 p-2">
                {ticketLogoUrl && !ticketLogoError ? (
                  <img
                    src={ticketLogoUrl}
                    alt="Logo para ticket"
                    className="max-h-full max-w-full object-contain"
                    onError={() => setTicketLogoError(true)}
                  />
                ) : (
                  <span className="px-3 text-center text-xs text-muted-foreground">
                    {ticketLogoUrl ? "No se pudo cargar el logo. Sube otro archivo." : "Sin logo configurado"}
                  </span>
                )}
              </div>
              <div className="space-y-1 text-sm">
                <div className="font-medium">Preview del logo actual</div>
                <p className="max-w-md text-xs text-muted-foreground">Si no hay logo, el ticket conserva el encabezado de texto y se imprime normalmente.</p>
                <p className="max-w-md text-xs text-muted-foreground">Si la app ya fue instalada, puede requerir reinstalar el acceso directo para ver un icono nuevo.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <input ref={fileInputRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={handleLogoSelect} />
              <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()} disabled={logoBusy}>
                {logoBusy ? "Guardando..." : "Subir logo"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => void handleRemoveLogo()} disabled={logoBusy || !ticketLogoUrl}>
                Quitar logo
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

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
          <DialogHeader>
            <DialogTitle>Configurar permisos de totales esperados</DialogTitle>
            <DialogDescription>Define qué roles ven los totales esperados y qué campos aparecen al cerrar caja.</DialogDescription>
          </DialogHeader>
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
