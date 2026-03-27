import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Customer,
  createCustomer,
  deleteCustomer,
  listActivities,
  listCustomers,
  listDepartments,
  listMunicipalities,
  setConsumerFinalCustomer,
  updateCustomer,
} from "@/lib/api";
import { toast } from "sonner";

type ClientType = "CF" | "CCF" | "SX";
type FormState = Partial<Customer> & { fullName: string; clientType: ClientType };

const emptyForm: FormState = {
  fullName: "",
  clientType: "CF",
  companyName: "",
  dui: "",
  nit: "",
  nrc: "",
  phone: "",
  email: "",
  direccion: "",
  departmentCode: "",
  municipalityCode: "",
  activityCode: "",
  activityDescription: "",
};

const normalizeText = (value?: string | null, { uppercase = false } = {}) => {
  const normalized = (value || "").replace(/\s+/g, " ").trim();
  return uppercase ? normalized.toUpperCase() : normalized;
};

const digitsOnly = (value: string) => value.replace(/\D+/g, "");

const formatDocumentByType = (raw: string, type: ClientType) => {
  if (type === "CCF") return digitsOnly(raw).slice(0, 14);
  const digits = digitsOnly(raw).slice(0, 14);
  if (digits.length <= 9) {
    if (digits.length <= 8) return digits;
    return `${digits.slice(0, 8)}-${digits.slice(8, 9)}`;
  }
  return digits;
};

const formatPhone = (raw: string) => {
  const digits = digitsOnly(raw).slice(0, 8);
  if (digits.length <= 4) return digits;
  return `${digits.slice(0, 4)}-${digits.slice(4)}`;
};

const isCcf = (type: ClientType) => type === "CCF";

export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [departments, setDepartments] = useState<Array<{ code: string; name: string }>>([]);
  const [municipalities, setMunicipalities] = useState<Array<{ code: string; department_code: string; name: string }>>([]);
  const [activities, setActivities] = useState<Array<{ code: string; description: string }>>([]);
  const [isGeoLoading, setIsGeoLoading] = useState(false);

  const resolveDefaults = useCallback(() => {
    const sanMiguelDept = departments.find((d) => d.name.toUpperCase() === "SAN MIGUEL") || departments.find((d) => d.code === "12");
    const defaultDeptCode = sanMiguelDept?.code || "12";
    const munis = municipalities.filter((m) => m.department_code === (form.departmentCode || defaultDeptCode));
    const sanMiguelCentro = munis.find((m) => m.name.toUpperCase() === "SAN MIGUEL CENTRO");
    const defaultMuniCode = sanMiguelCentro?.code || munis[0]?.code || "22";
    return {
      deptCode: defaultDeptCode,
      deptName: sanMiguelDept?.name || "SAN MIGUEL",
      muniCode: defaultMuniCode,
    };
  }, [departments, municipalities, form.departmentCode]);

  const loadCustomers = useCallback(async (q = "") => {
    setIsLoading(true);
    try {
      setRows(await listCustomers(q));
    } catch (e) {
      toast.error(String(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => {
      void loadCustomers(search);
    }, 250);
    return () => window.clearTimeout(t);
  }, [search, loadCustomers]);

  useEffect(() => {
    void loadCustomers("");
    setIsGeoLoading(true);
    Promise.all([listDepartments(), listActivities()])
      .then(([deps, acts]) => {
        setDepartments(deps);
        setActivities(acts);
      })
      .finally(() => setIsGeoLoading(false));
  }, [loadCustomers]);

  useEffect(() => {
    const dept = form.departmentCode;
    if (!dept) return;
    setIsGeoLoading(true);
    listMunicipalities(dept)
      .then((mun) => {
        setMunicipalities(mun);
        if (!form.municipalityCode && mun.length > 0) {
          setForm((f) => ({ ...f, municipalityCode: mun[0].code }));
        }
      })
      .finally(() => setIsGeoLoading(false));
  }, [form.departmentCode]);

  const principalDoc = (c: Customer) => (c.clientType === "CCF" ? c.nit || "—" : c.dui || c.nit || "—");

  const onNew = () => {
    setSelectedId(null);
    setIsEditing(false);
    setFieldErrors({});
    const { deptCode, muniCode } = resolveDefaults();
    setForm({ ...emptyForm, departmentCode: deptCode, municipalityCode: muniCode });
  };

  const onSelect = (c: Customer) => {
    setSelectedId(c.id);
    setIsEditing(false);
    setFieldErrors({});
    setForm({
      fullName: c.fullName,
      companyName: c.companyName || "",
      clientType: c.clientType,
      dui: c.dui || "",
      nit: c.nit || "",
      nrc: c.nrc || "",
      phone: c.phone || "",
      email: c.email || "",
      direccion: c.direccion || "",
      departmentCode: c.departmentCode || "",
      municipalityCode: c.municipalityCode || "",
      activityCode: c.activityCode || "",
      activityDescription: c.activityDescription || "",
      isConsumerFinal: c.isConsumerFinal,
    });
  };

  const onEdit = () => {
    if (!selectedId) return;
    setIsEditing(true);
  };

  const validate = () => {
    const errors: Record<string, string> = {};
    const fullName = normalizeText(form.fullName);
    if (!fullName) errors.fullName = "Nombre requerido";

    if (isCcf(form.clientType)) {
      if (!normalizeText(form.companyName)) errors.companyName = "Empresa requerida";
      if (digitsOnly(form.nit || "").length !== 14) errors.nit = "NIT de 14 dígitos";
      if (!normalizeText(form.nrc)) errors.nrc = "NRC requerido";
      if (digitsOnly(form.phone || "").length !== 8) errors.phone = "Teléfono de 8 dígitos";
      const email = normalizeText(form.email);
      if (!email || !email.includes("@") || !email.includes(".")) errors.email = "Email válido requerido";
      if (!normalizeText(form.direccion)) errors.direccion = "Dirección requerida";
      if (!form.departmentCode) errors.departmentCode = "Departamento requerido";
      if (!form.municipalityCode) errors.municipalityCode = "Municipio requerido";
      if (!normalizeText(form.activityCode) && !normalizeText(form.activityDescription)) errors.activityCode = "Actividad requerida";
    }

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error("Revisa los campos requeridos");
      return false;
    }
    return true;
  };

  const applyFastDefaults = (input: FormState) => {
    const next = { ...input };
    const { deptCode, deptName, muniCode } = resolveDefaults();

    if (!isCcf(next.clientType)) {
      const doc = formatDocumentByType(next.dui || next.nit || "", next.clientType);
      if (!doc || digitsOnly(doc).length < 9) {
        next.dui = "00000000-0";
        next.nit = "";
      } else if (digitsOnly(doc).length <= 9) {
        next.dui = doc;
        next.nit = "";
      } else {
        next.dui = "";
        next.nit = digitsOnly(doc).slice(0, 14);
      }

      const phoneDigits = digitsOnly(next.phone || "");
      next.phone = phoneDigits.length ? formatPhone(phoneDigits) : "0000-0000";

      if (!next.departmentCode) next.departmentCode = deptCode;
      if (!next.municipalityCode) next.municipalityCode = muniCode;
      if (!normalizeText(next.direccion)) {
        const selectedDept = departments.find((d) => d.code === next.departmentCode);
        next.direccion = selectedDept?.name || deptName || "SAN MIGUEL";
      }
    } else {
      next.nit = digitsOnly(next.nit || "").slice(0, 14);
      next.phone = formatPhone(next.phone || "");
    }

    next.fullName = normalizeText(next.fullName, { uppercase: true });
    next.companyName = normalizeText(next.companyName, { uppercase: true });
    next.nrc = normalizeText(next.nrc);
    next.email = normalizeText(next.email);
    next.activityCode = normalizeText(next.activityCode);
    next.activityDescription = normalizeText(next.activityDescription);
    return next;
  };

  const payloadFromForm = (source: FormState): Partial<Customer> & { fullName: string } => ({
    fullName: source.fullName,
    companyName: source.companyName ?? "",
    clientType: source.clientType,
    dui: source.dui ?? "",
    nit: source.nit ?? "",
    nrc: source.nrc ?? "",
    phone: source.phone ?? "",
    email: source.email ?? "",
    direccion: source.direccion ?? "",
    departmentCode: source.departmentCode ?? "",
    municipalityCode: source.municipalityCode ?? "",
    activityCode: source.activityCode ?? "",
    activityDescription: source.activityDescription ?? "",
    isConsumerFinal: Boolean(source.isConsumerFinal),
  });

  const onSave = async () => {
    const completed = applyFastDefaults(form);
    setForm(completed);
    if (!validate()) return;

    setIsSaving(true);
    try {
      let saved: Customer;
      if (selectedId && isEditing) {
        saved = await updateCustomer(selectedId, payloadFromForm(completed));
        toast.success("Cliente actualizado");
      } else {
        saved = await createCustomer(payloadFromForm(completed));
        if (!isCcf(completed.clientType)) {
          toast.success("Guardado con valores por defecto");
        } else {
          toast.success("Cliente creado");
        }
      }
      await loadCustomers(search);
      setSelectedId(saved.id);
      setIsEditing(false);
    } catch (e: any) {
      const message = e instanceof Error ? e.message : "No se pudo guardar";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async () => {
    if (!selectedId) return;
    if (!window.confirm("¿Eliminar cliente seleccionado?")) return;
    setIsSaving(true);
    try {
      await deleteCustomer(selectedId);
      toast.success("Cliente eliminado");
      await loadCustomers(search);
      onNew();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "No se pudo eliminar";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const filteredCountLabel = useMemo(() => `${rows.length} cliente${rows.length === 1 ? "" : "s"}`, [rows.length]);

  const canWrite = !selectedId || isEditing;

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto space-y-4 px-4 py-24">
        <Card className="p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex-1">
              <h1 className="text-xl font-semibold">Clientes</h1>
              <p className="text-sm text-muted-foreground">Captura veloz de clientes para DTE.</p>
            </div>
            <div className="flex w-full gap-2 md:w-auto md:min-w-[420px]">
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar cliente" />
              <Button variant="outline" onClick={onNew}>Nuevo cliente</Button>
            </div>
          </div>
        </Card>

        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <Card className="p-3">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Listado</h2>
              <span className="text-xs text-muted-foreground">{isLoading ? "Cargando..." : filteredCountLabel}</span>
            </div>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>DUI/NIT</TableHead>
                    <TableHead>Tel</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.length === 0 ? (
                    <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Sin clientes</TableCell></TableRow>
                  ) : rows.map((c) => (
                    <TableRow key={c.id} className={selectedId === c.id ? "bg-muted/50" : ""} onClick={() => onSelect(c)}>
                      <TableCell className="font-medium">{c.fullName}</TableCell>
                      <TableCell>{c.clientType}</TableCell>
                      <TableCell>{principalDoc(c)}</TableCell>
                      <TableCell>{c.phone || "—"}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); onSelect(c); onEdit(); }}>Editar</Button>
                          {c.clientType === "CF" && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>CF</span>
                              <Switch
                                checked={c.isConsumerFinal}
                                onCheckedChange={async (v) => {
                                  if (!v) return;
                                  await setConsumerFinalCustomer(c.id);
                                  await loadCustomers(search);
                                  toast.success("Consumidor final actualizado");
                                }}
                              />
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>

          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{selectedId ? `Cliente #${selectedId}` : "Nuevo cliente"}</h2>
              {selectedId && !isEditing ? <Button size="sm" variant="outline" onClick={onEdit}>Editar</Button> : null}
            </div>

            <div className="mb-3 flex gap-2">
              {(["CF", "CCF", "SX"] as ClientType[]).map((type) => (
                <Button
                  key={type}
                  type="button"
                  variant={form.clientType === type ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => setForm((f) => ({ ...f, clientType: type }))}
                  disabled={!canWrite}
                >
                  {type}
                </Button>
              ))}
            </div>

            <Tabs defaultValue="basico" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basico">Básico</TabsTrigger>
                <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
                <TabsTrigger value="contacto">Contacto</TabsTrigger>
                <TabsTrigger value="direccion">Dirección</TabsTrigger>
              </TabsList>

              <TabsContent value="basico" className="space-y-3">
                <div>
                  <Label>Nombre *</Label>
                  <Input disabled={!canWrite} value={form.fullName} onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))} />
                  {fieldErrors.fullName ? <p className="text-xs text-red-600">{fieldErrors.fullName}</p> : null}
                </div>
                <div>
                  <Label>Documento (DUI/NIT) {!isCcf(form.clientType) ? "(opcional)" : ""}</Label>
                  <Input
                    disabled={!canWrite}
                    value={form.clientType === "CCF" ? form.nit || "" : (form.dui || form.nit || "")}
                    onChange={(e) => {
                      const formatted = formatDocumentByType(e.target.value, form.clientType);
                      if (form.clientType === "CCF") {
                        setForm((f) => ({ ...f, nit: formatted }));
                      } else if (digitsOnly(formatted).length <= 9) {
                        setForm((f) => ({ ...f, dui: formatted, nit: "" }));
                      } else {
                        setForm((f) => ({ ...f, dui: "", nit: formatted }));
                      }
                    }}
                    onBlur={() => {
                      if (form.clientType !== "CCF" && !digitsOnly(form.dui || form.nit || "")) {
                        setForm((f) => ({ ...f, dui: "00000000-0", nit: "" }));
                      }
                    }}
                  />
                  {!isCcf(form.clientType) ? <Badge variant="secondary" className="mt-1">Autocompletado</Badge> : null}
                  {fieldErrors.nit ? <p className="text-xs text-red-600">{fieldErrors.nit}</p> : null}
                </div>
                <div>
                  <Label>Empresa / Razón social {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  <Input disabled={!canWrite} value={form.companyName || ""} onChange={(e) => setForm((f) => ({ ...f, companyName: e.target.value }))} />
                  {fieldErrors.companyName ? <p className="text-xs text-red-600">{fieldErrors.companyName}</p> : null}
                </div>
              </TabsContent>

              <TabsContent value="fiscal" className="space-y-3">
                <div>
                  <Label>NRC {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  <Input disabled={!canWrite} value={form.nrc || ""} onChange={(e) => setForm((f) => ({ ...f, nrc: e.target.value }))} />
                  {fieldErrors.nrc ? <p className="text-xs text-red-600">{fieldErrors.nrc}</p> : null}
                </div>
                <div>
                  <Label>Actividad económica {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  {isGeoLoading ? <Skeleton className="h-10 w-full" /> : (
                    <Select
                      value={form.activityCode || ""}
                      onValueChange={(v) => setForm((f) => ({ ...f, activityCode: v, activityDescription: activities.find((a) => a.code === v)?.description || f.activityDescription }))}
                      disabled={!canWrite}
                    >
                      <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                      <SelectContent>{activities.map((a) => <SelectItem key={a.code} value={a.code}>{a.code} - {a.description}</SelectItem>)}</SelectContent>
                    </Select>
                  )}
                  {fieldErrors.activityCode ? <p className="text-xs text-red-600">{fieldErrors.activityCode}</p> : null}
                </div>
              </TabsContent>

              <TabsContent value="contacto" className="space-y-3">
                <div>
                  <Label>Teléfono {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  <Input
                    disabled={!canWrite}
                    value={form.phone || ""}
                    onChange={(e) => setForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))}
                    onBlur={() => {
                      if (!isCcf(form.clientType) && !digitsOnly(form.phone || "")) {
                        setForm((f) => ({ ...f, phone: "0000-0000" }));
                      }
                    }}
                  />
                  {!isCcf(form.clientType) ? <Badge variant="secondary" className="mt-1">Autocompletado</Badge> : null}
                  {fieldErrors.phone ? <p className="text-xs text-red-600">{fieldErrors.phone}</p> : null}
                </div>
                <div>
                  <Label>Email {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  <Input disabled={!canWrite} value={form.email || ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
                  {fieldErrors.email ? <p className="text-xs text-red-600">{fieldErrors.email}</p> : null}
                </div>
              </TabsContent>

              <TabsContent value="direccion" className="space-y-3">
                <div>
                  <Label>Dirección {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  <Input disabled={!canWrite} value={form.direccion || ""} onChange={(e) => setForm((f) => ({ ...f, direccion: e.target.value }))} />
                  {!isCcf(form.clientType) ? <Badge variant="secondary" className="mt-1">Autocompletado</Badge> : null}
                  {fieldErrors.direccion ? <p className="text-xs text-red-600">{fieldErrors.direccion}</p> : null}
                </div>
                <div>
                  <Label>Departamento {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  {isGeoLoading ? <Skeleton className="h-10 w-full" /> : (
                    <Select value={form.departmentCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, departmentCode: v, municipalityCode: "" }))} disabled={!canWrite}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>{departments.map((d) => <SelectItem key={d.code} value={d.code}>{d.name}</SelectItem>)}</SelectContent>
                    </Select>
                  )}
                  {fieldErrors.departmentCode ? <p className="text-xs text-red-600">{fieldErrors.departmentCode}</p> : null}
                </div>
                <div>
                  <Label>Municipio {isCcf(form.clientType) ? "*" : "(opcional)"}</Label>
                  {isGeoLoading ? <Skeleton className="h-10 w-full" /> : (
                    <Select value={form.municipalityCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, municipalityCode: v }))} disabled={!canWrite}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>{municipalities.map((m) => <SelectItem key={`${m.department_code}-${m.code}`} value={m.code}>{m.name}</SelectItem>)}</SelectContent>
                    </Select>
                  )}
                  {fieldErrors.municipalityCode ? <p className="text-xs text-red-600">{fieldErrors.municipalityCode}</p> : null}
                </div>
              </TabsContent>
            </Tabs>

            <div className="mt-4 flex gap-2">
              <Button onClick={onSave} disabled={isSaving || !canWrite}>{isSaving ? "Guardando..." : selectedId && isEditing ? "Actualizar" : "Guardar"}</Button>
              <Button variant="outline" onClick={onNew} disabled={isSaving}>Nuevo cliente</Button>
              {selectedId ? <Button variant="destructive" onClick={onDelete} disabled={isSaving}>Eliminar</Button> : null}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
