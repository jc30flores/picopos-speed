import { useEffect, useState } from "react";
import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { dteIssuedDetail, dteIssuedList, dteResend, dteSendEmail, dteSendWhatsapp, type DTERecord } from "@/lib/api";

const statusLabel: Record<string, string> = {
  enviando: "ENVIANDO",
  pendiente: "PENDIENTE",
  aceptado: "ACEPTADO",
  rechazado: "RECHAZADO",
  invalidado: "INVALIDADO",
};

export default function DTEPage() {
  const [rows, setRows] = useState<DTERecord[]>([]);
  const [selected, setSelected] = useState<DTERecord | null>(null);
  const [query, setQuery] = useState("");
  const { toast } = useToast();

  const load = async () => {
    try {
      setRows(await dteIssuedList(query));
    } catch (error) {
      toast({ title: "Error cargando DTE", description: String(error), variant: "destructive" });
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto pt-24 px-4 pb-6 space-y-4">
        <div className="flex gap-2">
          <Input placeholder="Buscar por control..." value={query} onChange={(e) => setQuery(e.target.value)} />
          <Button onClick={load}>Buscar</Button>
        </div>
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr>
                <th className="text-left p-2">Fecha</th><th className="text-left p-2">Tipo</th><th className="text-left p-2">No. Control</th><th className="text-left p-2">Código</th><th className="text-left p-2">Cliente</th><th className="text-left p-2">Total</th><th className="text-left p-2">Estado</th><th className="text-left p-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="p-2">{r.dte_type}</td>
                  <td className="p-2">{r.control_number}</td>
                  <td className="p-2">{r.codigo_generacion}</td>
                  <td className="p-2">{r.receiver_name}</td>
                  <td className="p-2">${Number(r.total_amount).toFixed(2)}</td>
                  <td className="p-2"><Badge>{statusLabel[r.status] ?? r.status}</Badge></td>
                  <td className="p-2 flex gap-2">
                    <Button size="sm" variant="outline" onClick={async () => setSelected(await dteIssuedDetail(r.id))}>Ver</Button>
                    <Button size="sm" variant="outline" onClick={async () => { await dteResend(r.id); await load(); }}>Reenviar</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Detalle DTE</DialogTitle></DialogHeader>
          {selected && (
            <div className="space-y-2 text-sm">
              <p><strong>No. Control:</strong> {selected.control_number}</p>
              <p><strong>Código generación:</strong> {selected.codigo_generacion}</p>
              <p><strong>Sello:</strong> {selected.sello_recepcion || "-"}</p>
              <p><strong>Estado:</strong> {selected.status} / {selected.hacienda_state || "-"}</p>
              <p><strong>Cliente:</strong> {selected.receiver_name}</p>
              <div className="flex gap-2">
                <Button size="sm" onClick={async () => { await dteSendWhatsapp(selected.id); toast({ title: "WhatsApp enviado" }); }}>WhatsApp</Button>
                <Button size="sm" variant="outline" onClick={async () => { await dteSendEmail(selected.id); toast({ title: "Correo enviado" }); }}>Correo</Button>
              </div>
              {selected.request_payload && <pre className="bg-muted p-3 rounded text-xs overflow-auto">{JSON.stringify(selected.request_payload, null, 2)}</pre>}
              {selected.response_payload && <pre className="bg-muted p-3 rounded text-xs overflow-auto">{JSON.stringify(selected.response_payload, null, 2)}</pre>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
