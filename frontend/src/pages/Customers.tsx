import { Navigation } from "@/components/Navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useEffect, useMemo, useState } from "react";
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
const emptyForm: FormState = { fullName: "", clientType: "CF", companyName: "", dui: "", nit: "", nrc: "", phone: "", email: "", direccion: "", departmentCode: "12", municipalityCode: "22", activityCode: "", activityDescription: "" };

export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [departments, setDepartments] = useState<Array<{ code: string; name: string }>>([]);
  const [municipalities, setMunicipalities] = useState<Array<{ code: string; department_code: string; name: string }>>([]);
  const [activities, setActivities] = useState<Array<{ code: string; description: string }>>([]);

  const load = async (q = search) => {
    try { setRows(await listCustomers(q)); } catch (e) { toast.error(String(e)); }
  };

  useEffect(() => { void load(""); void listDepartments().then(setDepartments); }, []);
  useEffect(() => { void listMunicipalities(form.departmentCode).then(setMunicipalities); }, [form.departmentCode]);
  useEffect(() => { void listActivities().then(setActivities); }, []);

  const validate = () => {
    if (form.clientType === "CCF") {
      if (!form.fullName || !form.nit || !form.nrc || !form.direccion || !form.departmentCode || !form.municipalityCode || !(form.activityCode || form.activityDescription)) {
        toast.error("CCF requiere NIT, NRC, actividad y dirección completa");
        return false;
      }
    }
    if (form.clientType === "SX") {
      if (!form.dui || !form.direccion || !form.departmentCode || !form.municipalityCode) {
        toast.error("SX requiere DUI y dirección completa");
        return false;
      }
    }
    return true;
  };

  const principalDoc = (c: Customer) => (c.clientType === "CCF" ? c.nit : c.dui || c.nit || "—");
  const canSave = useMemo(() => form.fullName.trim().length > 0, [form.fullName]);

  const onSave = async () => {
    if (!validate()) return;
    try {
      if (editingId) await updateCustomer(editingId, form);
      else await createCustomer(form);
      setForm(emptyForm);
      setEditingId(null);
      await load();
      toast.success(editingId ? "Cliente actualizado" : "Cliente creado");
    } catch (e: any) {
      const detail = e?.message || "No se pudo guardar";
      toast.error(String(detail));
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto px-4 py-24 space-y-4">
        <Card className="p-4 space-y-3">
          <h1 className="text-xl font-semibold">Clientes</h1>
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar nombre/documento" />
            <Button onClick={() => void load(search)}>Buscar</Button>
          </div>
        </Card>

        <Card className="p-4 grid md:grid-cols-3 gap-3">
          <div><Label>Nombre</Label><Input value={form.fullName} onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))} /></div>
          <div><Label>Empresa</Label><Input value={form.companyName || ""} onChange={(e) => setForm((f) => ({ ...f, companyName: e.target.value }))} /></div>
          <div><Label>Tipo</Label><Select value={form.clientType} onValueChange={(v: any) => setForm((f) => ({ ...f, clientType: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="CF">CF</SelectItem><SelectItem value="CCF">CCF</SelectItem><SelectItem value="SX">SX</SelectItem></SelectContent></Select></div>
          <div><Label>DUI</Label><Input value={form.dui || ""} onChange={(e) => setForm((f) => ({ ...f, dui: e.target.value }))} /></div>
          <div><Label>NIT</Label><Input value={form.nit || ""} onChange={(e) => setForm((f) => ({ ...f, nit: e.target.value }))} /></div>
          <div><Label>NRC</Label><Input value={form.nrc || ""} onChange={(e) => setForm((f) => ({ ...f, nrc: e.target.value }))} /></div>
          <div><Label>Teléfono</Label><Input value={form.phone || ""} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div>
          <div><Label>Email</Label><Input value={form.email || ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></div>
          <div><Label>Dirección</Label><Input value={form.direccion || ""} onChange={(e) => setForm((f) => ({ ...f, direccion: e.target.value }))} /></div>
          <div><Label>Departamento</Label><Select value={form.departmentCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, departmentCode: v, municipalityCode: "" }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{departments.map((d) => <SelectItem key={d.code} value={d.code}>{d.name}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Municipio</Label><Select value={form.municipalityCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, municipalityCode: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{municipalities.map((m) => <SelectItem key={m.code} value={m.code}>{m.name}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Actividad</Label><Select value={form.activityCode || ""} onValueChange={(v) => setForm((f) => ({ ...f, activityCode: v, activityDescription: activities.find((a) => a.code === v)?.description || f.activityDescription }))}><SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger><SelectContent>{activities.map((a) => <SelectItem key={a.code} value={a.code}>{a.code} - {a.description}</SelectItem>)}</SelectContent></Select></div>
          <div className="md:col-span-3 flex gap-2">
            <Button onClick={onSave} disabled={!canSave}>{editingId ? "Guardar" : "Nuevo cliente"}</Button>
            {editingId && <Button variant="outline" onClick={() => { setEditingId(null); setForm(emptyForm); }}>Cancelar</Button>}
          </div>
        </Card>

        <div className="space-y-2">
          {rows.map((c) => (
            <Card key={c.id} className="p-3 flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">{c.fullName}</div>
                <div className="text-xs text-muted-foreground">{c.clientType} · {principalDoc(c)} · NRC: {c.nrc || "—"}</div>
              </div>
              <div className="flex items-center gap-2">
                {c.clientType === "CF" && (
                  <div className="flex items-center gap-2 text-sm">
                    <span>Consumidor final</span>
                    <Switch checked={c.isConsumerFinal} onCheckedChange={async (v) => { if (!v) return; await setConsumerFinalCustomer(c.id); await load(); }} />
                  </div>
                )}
                <Button variant="outline" onClick={() => { setEditingId(c.id); setForm({ fullName: c.fullName, companyName: c.companyName || "", clientType: c.clientType, dui: c.dui || "", nit: c.nit || "", nrc: c.nrc || "", phone: c.phone || "", email: c.email || "", direccion: c.direccion || "", departmentCode: c.departmentCode || "", municipalityCode: c.municipalityCode || "", activityCode: c.activityCode || "", activityDescription: c.activityDescription || "" }); }}>Editar</Button>
                <Button variant="destructive" onClick={async () => { if (!window.confirm("¿Eliminar cliente?")) return; await deleteCustomer(c.id); await load(); }}>Eliminar</Button>
              </div>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
