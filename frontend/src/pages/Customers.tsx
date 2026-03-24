import { Navigation } from "@/components/Navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

type FormState = Partial<Customer> & { fullName: string; clientType: "CF" | "CCF" | "SX" };

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
  departmentCode: "12",
  municipalityCode: "22",
  activityCode: "",
  activityDescription: "",
};

const normalizeText = (value?: string | null, { uppercase = false } = {}) => {
  const normalized = (value || "").replace(/\s+/g, " ").trim();
  return uppercase ? normalized.toUpperCase() : normalized;
};

export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [departments, setDepartments] = useState<Array<{ code: string; name: string }>>([]);
  const [municipalities, setMunicipalities] = useState<Array<{ code: string; department_code: string; name: string }>>([]);
  const [activities, setActivities] = useState<Array<{ code: string; description: string }>>([]);

  const load = useCallback(async (q = search) => {
    setIsLoading(true);
    try {
      setRows(await listCustomers(q));
    } catch (e) {
      toast.error(String(e));
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    void load("");
    void listDepartments().then(setDepartments);
    void listActivities().then(setActivities);
  }, [load]);

  useEffect(() => {
    void listMunicipalities(form.departmentCode).then(setMunicipalities);
  }, [form.departmentCode]);

  const validate = () => {
    const fullName = normalizeText(form.fullName);
    if (!fullName) {
      toast.error("El nombre es requerido");
      return false;
    }
    if (form.clientType === "CCF") {
      if (!normalizeText(form.nit) || !normalizeText(form.nrc) || !normalizeText(form.companyName) || !normalizeText(form.direccion)) {
        toast.error("CCF requiere Empresa, NIT, NRC y Dirección");
        return false;
      }
    }
    if (form.clientType === "SX") {
      if (!normalizeText(form.dui) || !normalizeText(form.direccion)) {
        toast.error("SX requiere DUI y Dirección");
        return false;
      }
    }
    return true;
  };

  const principalDoc = (c: Customer) => (c.clientType === "CCF" ? c.nit || "—" : c.dui || c.nit || "—");

  const onNew = () => {
    setEditingId(null);
    setForm(emptyForm);
  };

  const onSelect = (c: Customer) => {
    setEditingId(c.id);
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
      departmentCode: c.departmentCode || "12",
      municipalityCode: c.municipalityCode || "22",
      activityCode: c.activityCode || "",
      activityDescription: c.activityDescription || "",
      isConsumerFinal: c.isConsumerFinal,
    });
  };

  const payloadFromForm = (): Partial<Customer> & { fullName: string } => ({
    fullName: normalizeText(form.fullName, { uppercase: true }),
    companyName: normalizeText(form.companyName, { uppercase: true }),
    clientType: form.clientType,
    dui: normalizeText(form.dui),
    nit: normalizeText(form.nit),
    nrc: normalizeText(form.nrc),
    phone: normalizeText(form.phone),
    email: normalizeText(form.email),
    direccion: normalizeText(form.direccion),
    departmentCode: form.departmentCode,
    municipalityCode: form.municipalityCode,
    activityCode: normalizeText(form.activityCode),
    activityDescription: normalizeText(form.activityDescription),
    isConsumerFinal: Boolean(form.isConsumerFinal),
  });

  const onSave = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      if (editingId) {
        await updateCustomer(editingId, payloadFromForm());
        toast.success("Cliente actualizado");
      } else {
        await createCustomer(payloadFromForm());
        toast.success("Cliente creado");
      }
      await load();
      onNew();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "No se pudo guardar";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async () => {
    if (!editingId) return;
    if (!window.confirm("¿Eliminar cliente seleccionado?")) return;
    setIsSaving(true);
    try {
      await deleteCustomer(editingId);
      toast.success("Cliente eliminado");
      await load();
      onNew();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "No se pudo eliminar";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const filteredCountLabel = useMemo(() => `${rows.length} cliente${rows.length === 1 ? "" : "s"}`, [rows.length]);

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto space-y-4 px-4 py-24">
        <Card className="p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex-1">
              <h1 className="text-xl font-semibold">Clientes</h1>
              <p className="text-sm text-muted-foreground">Buscar, seleccionar, editar y crear clientes rápidamente.</p>
            </div>
            <div className="flex w-full gap-2 md:w-auto md:min-w-[420px]">
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar nombre, empresa, DUI, NIT, teléfono o email" />
              <Button onClick={() => void load(search)} disabled={isLoading}>Buscar</Button>
              <Button variant="outline" onClick={onNew}>Nuevo cliente</Button>
            </div>
          </div>
        </Card>

        <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
          <Card className="p-3">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Listado</h2>
              <span className="text-xs text-muted-foreground">{isLoading ? "Cargando..." : filteredCountLabel}</span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Empresa</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>DUI/NIT</TableHead>
                  <TableHead>Teléfono</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">Sin clientes para mostrar.</TableCell>
                  </TableRow>
                ) : (
                  rows.map((c) => (
                    <TableRow key={c.id} className={editingId === c.id ? "bg-muted/40" : ""}>
                      <TableCell className="font-medium">{c.fullName}</TableCell>
                      <TableCell>{c.companyName || "—"}</TableCell>
                      <TableCell>{c.clientType}</TableCell>
                      <TableCell>{principalDoc(c)}</TableCell>
                      <TableCell>{c.phone || "—"}</TableCell>
                      <TableCell>{c.email || "—"}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => onSelect(c)}>Editar</Button>
                          {c.clientType === "CF" && (
                            <div className="flex items-center gap-2 pr-1 text-xs text-muted-foreground">
                              <span>CF</span>
                              <Switch checked={c.isConsumerFinal} onCheckedChange={async (v) => { if (!v) return; await setConsumerFinalCustomer(c.id); await load(); toast.success("Consumidor final actualizado"); }} />
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>

          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{editingId ? `Editar cliente #${editingId}` : "Nuevo cliente"}</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="md:col-span-2"><Label>Nombre</Label><Input value={form.fullName} onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))} /></div>
              <div className="md:col-span-2"><Label>Empresa</Label><Input value={form.companyName || ""} onChange={(e) => setForm((f) => ({ ...f, companyName: e.target.value }))} /></div>
              <div><Label>Tipo</Label><Select value={form.clientType} onValueChange={(v: "CF" | "CCF" | "SX") => setForm((f) => ({ ...f, clientType: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="CF">CF</SelectItem><SelectItem value="CCF">CCF</SelectItem><SelectItem value="SX">SX</SelectItem></SelectContent></Select></div>
              <div><Label>DUI</Label><Input value={form.dui || ""} onChange={(e) => setForm((f) => ({ ...f, dui: e.target.value }))} /></div>
              <div><Label>NIT</Label><Input value={form.nit || ""} onChange={(e) => setForm((f) => ({ ...f, nit: e.target.value }))} /></div>
              <div><Label>NRC</Label><Input value={form.nrc || ""} onChange={(e) => setForm((f) => ({ ...f, nrc: e.target.value }))} /></div>
              <div><Label>Teléfono</Label><Input value={form.phone || ""} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div>
              <div><Label>Email</Label><Input value={form.email || ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></div>
              <div className="md:col-span-2"><Label>Dirección</Label><Input value={form.direccion || ""} onChange={(e) => setForm((f) => ({ ...f, direccion: e.target.value }))} /></div>
              <div><Label>Departamento</Label><Select value={form.departmentCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, departmentCode: v, municipalityCode: "" }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{departments.map((d) => <SelectItem key={d.code} value={d.code}>{d.name}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Municipio</Label><Select value={form.municipalityCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, municipalityCode: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{municipalities.map((m) => <SelectItem key={m.code} value={m.code}>{m.name}</SelectItem>)}</SelectContent></Select></div>
              <div className="md:col-span-2"><Label>Actividad</Label><Select value={form.activityCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, activityCode: v, activityDescription: activities.find((a) => a.code === v)?.description || f.activityDescription }))}><SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger><SelectContent>{activities.map((a) => <SelectItem key={a.code} value={a.code}>{a.code} - {a.description}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="mt-4 flex gap-2">
              <Button onClick={onSave} disabled={isSaving}>{isSaving ? "Guardando..." : editingId ? "Actualizar" : "Guardar"}</Button>
              <Button variant="outline" onClick={onNew} disabled={isSaving}>Limpiar</Button>
              {editingId && <Button variant="destructive" onClick={onDelete} disabled={isSaving}>Eliminar</Button>}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
