import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  getDteSettings,
  initializeDteCorrelatives,
  testDteConnectionSettings,
  updateDteCorrelative,
  updateDteSettings,
  type DteSettings,
} from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";

const statusLabel: Record<string, string> = {
  disabled: "Desactivado",
  pending: "Pendiente de configuración",
  configured: "Configurado",
  invalid: "Error",
};

const Field = ({ label, value, disabled, onChange, type = "text" }: { label: string; value: string | number; disabled?: boolean; type?: string; onChange: (value: string) => void }) => (
  <div className="space-y-2">
    <Label>{label}</Label>
    <Input type={type} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
  </div>
);

export const DteSettingsTab = () => {
  const [settings, setSettings] = useState<DteSettings | null>(null);
  const [draft, setDraft] = useState<DteSettings | null>(null);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correlativeReason, setCorrelativeReason] = useState("");

  const load = () => {
    setLoading(true);
    setError(null);
    getDteSettings()
      .then((value) => {
        setSettings(value);
        setDraft(value);
      })
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

  const persist = async (patch?: Partial<DteSettings> & { apiToken?: string }) => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await updateDteSettings({ ...draft, ...patch, apiToken: patch?.apiToken ?? (token || undefined) });
      setSettings(saved);
      setDraft(saved);
      setToken("");
      toast.success(saved.haciendaEnabled ? "Configuración DTE guardada" : "Facturación electrónica desactivada");
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar DTE";
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const patchDraft = (patch: Partial<DteSettings>) => draft && setDraft({ ...draft, ...patch });
  const patchIssuer = (field: keyof DteSettings["issuer"], value: string) => draft && setDraft({ ...draft, issuer: { ...draft.issuer, [field]: value } });
  const patchBranch = (field: keyof DteSettings["branch"], value: string) => draft && setDraft({ ...draft, branch: { ...draft.branch, [field]: value } });

  if (loading && !draft) return <Card><CardContent className="pt-6 text-sm text-muted-foreground">Cargando Hacienda/DTE...</CardContent></Card>;
  if (error && !draft) {
    return (
      <Card>
        <CardContent className="space-y-3 pt-6">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" onClick={load}>Reintentar</Button>
        </CardContent>
      </Card>
    );
  }
  if (!draft) return null;

  const canEditTechnical = Boolean(draft.permissions?.canEditTechnical || draft.canManageTechnical);
  const canEditCorrelatives = Boolean(draft.permissions?.canEditCorrelatives);
  const disabled = !canEditTechnical || saving;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Estado general</CardTitle>
          <CardDescription>{draft.message || "Configura facturación electrónica para GastroPOSV."}</CardDescription>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-3">
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <div className="font-semibold">Envíos Hacienda activos</div>
              <p className="text-xs text-muted-foreground">Apagado opera como POS local.</p>
            </div>
            <Switch checked={draft.haciendaEnabled} disabled={disabled} onCheckedChange={(checked) => void persist({ haciendaEnabled: checked })} />
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Estado</div>
            <div className="font-semibold">{statusLabel[draft.status] || draft.status}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Token API</div>
            <div className="font-semibold">{draft.apiTokenConfigured ? "Configurado" : "No configurado"}</div>
          </div>
          {draft.pendingFields.length ? (
            <div className="lg:col-span-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
              Faltan campos: {draft.pendingFields.join(", ")}.
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Entrega fiscal</CardTitle>
          <CardDescription>Estas acciones solo se muestran cuando Hacienda/DTE está activo. Si está apagado, GastroPOSV opera como POS local.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            ["fiscalEmailEnabled", "Correo fiscal", "Permitir envío fiscal por correo."],
            ["fiscalWhatsappEnabled", "WhatsApp fiscal", "Permitir envío fiscal por WhatsApp."],
            ["fiscalPdfEnabled", "PDF fiscal", "Permitir generación/descarga PDF fiscal."],
            ["fiscalJsonEnabled", "JSON fiscal", "Permitir generación/descarga JSON fiscal."],
          ].map(([key, title, description]) => (
            <div key={key} className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <div className="font-semibold">{title}</div>
                <p className="text-xs text-muted-foreground">{description}</p>
              </div>
              <Switch
                checked={Boolean(draft[key as keyof DteSettings])}
                disabled={disabled}
                onCheckedChange={(checked) => patchDraft({ [key]: checked } as Partial<DteSettings>)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>API / conexión</CardTitle></CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <Label>Ambiente</Label>
            <Select value={draft.ambiente} disabled={disabled} onValueChange={(value) => patchDraft({ ambiente: value as "00" | "01" })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="00">Pruebas</SelectItem>
                <SelectItem value="01">Producción</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Field label="URL API" value={draft.baseUrl} disabled={disabled} onChange={(value) => patchDraft({ baseUrl: value })} />
          <Field label="API token/key" value={token} disabled={disabled} onChange={setToken} />
          <Field label="Timeout segundos" type="number" value={draft.timeoutSeconds} disabled={disabled} onChange={(value) => patchDraft({ timeoutSeconds: Number(value) })} />
          <Field label="Reintentos" type="number" value={draft.retryCount} disabled={disabled} onChange={(value) => patchDraft({ retryCount: Number(value) })} />
          <div className="flex flex-wrap items-end gap-2">
            <Button disabled={disabled} onClick={() => void persist()}>Guardar configuración</Button>
            <Button variant="outline" disabled={!canEditTechnical || saving} onClick={async () => {
              const result = await testDteConnectionSettings();
              toast[result.ok ? "success" : "warning"](result.message);
            }}>Probar configuración</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Datos del emisor</CardTitle></CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <Field label="Razón social" value={draft.issuer.legalName} disabled={disabled} onChange={(value) => patchIssuer("legalName", value)} />
          <Field label="Nombre comercial" value={draft.issuer.commercialName} disabled={disabled} onChange={(value) => patchIssuer("commercialName", value)} />
          <Field label="NIT" value={draft.issuer.nit} disabled={disabled} onChange={(value) => patchIssuer("nit", value)} />
          <Field label="DUI" value={draft.issuer.dui} disabled={disabled} onChange={(value) => patchIssuer("dui", value)} />
          <Field label="NRC" value={draft.issuer.nrc} disabled={disabled} onChange={(value) => patchIssuer("nrc", value)} />
          <Field label="Código actividad" value={draft.issuer.activityCode} disabled={disabled} onChange={(value) => patchIssuer("activityCode", value)} />
          <Field label="Actividad económica" value={draft.issuer.activityDescription} disabled={disabled} onChange={(value) => patchIssuer("activityDescription", value)} />
          <Field label="Correo" value={draft.issuer.email} disabled={disabled} onChange={(value) => patchIssuer("email", value)} />
          <Field label="Teléfono" value={draft.issuer.phone} disabled={disabled} onChange={(value) => patchIssuer("phone", value)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Dirección fiscal y sucursal principal</CardTitle></CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <Field label="Departamento" value={draft.issuer.department} disabled={disabled} onChange={(value) => patchIssuer("department", value)} />
          <Field label="Municipio" value={draft.issuer.municipality} disabled={disabled} onChange={(value) => patchIssuer("municipality", value)} />
          <Field label="Complemento dirección" value={draft.issuer.address} disabled={disabled} onChange={(value) => patchIssuer("address", value)} />
          <Field label="Nombre sucursal" value={draft.branch.name} disabled={disabled} onChange={(value) => patchBranch("name", value)} />
          <Field label="Código establecimiento MH" value={draft.branch.establishmentCodeMh} disabled={disabled} onChange={(value) => patchBranch("establishmentCodeMh", value)} />
          <Field label="Código establecimiento interno" value={draft.branch.establishmentCode} disabled={disabled} onChange={(value) => patchBranch("establishmentCode", value)} />
          <Field label="Código punto venta MH" value={draft.branch.posCodeMh} disabled={disabled} onChange={(value) => patchBranch("posCodeMh", value)} />
          <Field label="Código punto venta interno" value={draft.branch.posCode} disabled={disabled} onChange={(value) => patchBranch("posCode", value)} />
          <Field label="Tipo establecimiento" value={draft.branch.establishmentType} disabled={disabled} onChange={(value) => patchBranch("establishmentType", value)} />
          <Field label="Dirección sucursal" value={draft.branch.branchAddress} disabled={disabled} onChange={(value) => patchBranch("branchAddress", value)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Correlativos / Last number</CardTitle>
          <CardDescription>Cambiar correlativos puede afectar la numeración fiscal. Use solo si sabe lo que hace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={!canEditCorrelatives || saving} onClick={async () => {
              const rows = await initializeDteCorrelatives();
              setDraft({ ...draft, correlatives: rows });
              setSettings(settings ? { ...settings, correlatives: rows } : settings);
              toast.success("Correlativos inicializados.");
            }}>Inicializar correlativos</Button>
            <Input className="max-w-md" value={correlativeReason} onChange={(event) => setCorrelativeReason(event.target.value)} placeholder="Motivo obligatorio para editar last number" />
          </div>
          <div className="overflow-auto rounded-md border">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-muted/60 text-left">
                <tr>
                  <th className="p-2">Tipo DTE</th>
                  <th className="p-2">Ambiente</th>
                  <th className="p-2">Est/PV</th>
                  <th className="p-2">Último</th>
                  <th className="p-2">Próximo</th>
                  <th className="p-2">Actualizado</th>
                  <th className="p-2">Acción</th>
                </tr>
              </thead>
              <tbody>
                {draft.correlatives.map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="p-2">{row.label}</td>
                    <td className="p-2">{row.ambiente === "01" ? "Producción" : "Pruebas"}</td>
                    <td className="p-2">{row.establishmentCode}/{row.posCode}</td>
                    <td className="p-2 tabular-nums">{row.lastNumber}</td>
                    <td className="p-2 tabular-nums">{row.nextNumber}</td>
                    <td className="p-2">{row.updatedAt ? formatDateTime(row.updatedAt) : "-"}</td>
                    <td className="p-2">
                      <Button size="sm" variant="outline" disabled={!canEditCorrelatives || !correlativeReason.trim()} onClick={async () => {
                        const raw = window.prompt("Nuevo último número usado", String(row.lastNumber));
                        if (raw === null) return;
                        const next = Number(raw);
                        const rows = await updateDteCorrelative(row.id, { lastNumber: next, reason: correlativeReason, confirmDecrease: next < row.lastNumber && window.confirm("¿Confirmas bajar el correlativo?") });
                        setDraft({ ...draft, correlatives: rows });
                        toast.success("Correlativo actualizado.");
                      }}>Editar last number</Button>
                    </td>
                  </tr>
                ))}
                {draft.correlatives.length === 0 ? <tr><td className="p-4 text-muted-foreground" colSpan={7}>No hay correlativos inicializados.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {!canEditTechnical ? (
        <p className="text-sm text-muted-foreground">Solo superadmin puede cambiar URL, token, producción, activación de Hacienda y correlativos.</p>
      ) : null}
    </div>
  );
};
