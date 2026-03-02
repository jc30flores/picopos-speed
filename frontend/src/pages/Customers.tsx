import { Navigation } from "@/components/Navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useEffect, useState } from "react";
import { Customer, createCustomer, listCustomers, updateCustomer } from "@/lib/api";
import { toast } from "sonner";

export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");

  const load = async (q = "") => {
    try {
      setRows(await listCustomers(q));
    } catch (e) {
      toast.error(String(e));
    }
  };

  useEffect(() => { void load(); }, []);

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto px-4 py-24 space-y-4">
        <Card className="p-4 space-y-3">
          <h1 className="text-xl font-semibold">Clientes</h1>
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por nombre o documento" />
            <Button onClick={() => void load(search)}>Buscar</Button>
          </div>
        </Card>

        <Card className="p-4 space-y-3">
          <Label>Nuevo cliente</Label>
          <div className="flex gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre" />
            <Button onClick={async () => {
              if (!name.trim()) return;
              await createCustomer({ name: name.trim() });
              setName("");
              await load(search);
            }}>Nuevo cliente</Button>
          </div>
        </Card>

        <div className="space-y-2">
          {rows.map((c) => (
            <Card key={c.id} className="p-3 flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-muted-foreground">{c.numDocumento} · {c.correo || "—"}</div>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span>Consumidor final</span>
                <Switch checked={c.isDefaultConsumerFinal} onCheckedChange={async (val) => {
                  await updateCustomer(c.id, { isDefaultConsumerFinal: val });
                  await load(search);
                }} />
              </div>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
