import { useEffect, useMemo, useState } from "react";
import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import {
  dteCreateCreditNote,
  dteInvalidate,
  dteIssuedDetail,
  dteIssuedList,
  dteResend,
  dteSendEmail,
  dteSendWhatsapp,
  downloadOrderReceiptPdf,
  type DTERecord,
} from "@/lib/api";
import { formatDateTimeSV } from "@/lib/datetime";

const canResend = (s: string) => ["PENDIENTE", "RECHAZADO"].includes(s);

export default function DTEPage() {
  const [rows, setRows] = useState<DTERecord[]>([]);
  const [selected, setSelected] = useState<DTERecord | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const { toast } = useToast();

  const filters = useMemo(
    () => ({ q: query || undefined, status: status === "all" ? undefined : status, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }),
    [query, status, dateFrom, dateTo],
  );

  const load = async () => {
    try {
      setRows(await dteIssuedList(filters));
    } catch (error) {
      toast({ title: "Error cargando DTE", description: String(error), variant: "destructive" });
    }
  };

  useEffect(() => {
    load();
  }, []);

  const copy = async (value?: string) => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    toast({ title: "Copiado" });
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto pt-24 px-4 pb-6 space-y-4">
        <h1 className="text-2xl font-semibold">DTE</h1>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
          <Input placeholder="Buscar (cliente/control/código/uuid)" value={query} onChange={(e) => setQuery(e.target.value)} />
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger><SelectValue placeholder="Estado" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="PENDIENTE">Pendiente</SelectItem>
              <SelectItem value="ENVIANDO">Enviando</SelectItem>
              <SelectItem value="ACEPTADO">Aceptado</SelectItem>
              <SelectItem value="RECHAZADO">Rechazado</SelectItem>
              <SelectItem value="INVALIDADO">Invalidado</SelectItem>
            </SelectContent>
          </Select>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <Button onClick={load}>Aplicar filtros</Button>
        </div>

        <div className="border rounded-lg overflow-auto">
          <table className="w-full text-sm min-w-[1100px]">
            <thead className="bg-muted/40">
              <tr>
                <th className="text-left p-2">Fecha</th><th className="text-left p-2">Estado</th><th className="text-left p-2">Tipo</th><th className="text-left p-2">No. Control</th><th className="text-left p-2">Código generación</th><th className="text-left p-2">Sello</th><th className="text-left p-2">Cliente</th><th className="text-left p-2">Total</th><th className="text-left p-2">Intentos</th><th className="text-left p-2">Último envío</th><th className="text-left p-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{formatDateTimeSV(r.created_at)}</td>
                  <td className="p-2"><Badge>{r.status}</Badge></td>
                  <td className="p-2">{r.dte_type}</td>
                  <td className="p-2">{r.control_number}</td>
                  <td className="p-2">{r.codigo_generacion}</td>
                  <td className="p-2">{r.sello_recibido || r.sello_recepcion || "-"}</td>
                  <td className="p-2">{r.receiver_name}</td>
                  <td className="p-2">${Number(r.total_amount).toFixed(2)}</td>
                  <td className="p-2">{r.attempts ?? "-"}</td>
                  <td className="p-2">{r.last_sent_at ? formatDateTimeSV(r.last_sent_at) : "-"}</td>
                  <td className="p-2 flex gap-2">
                    <Button size="sm" variant="outline" onClick={async () => setSelected(await dteIssuedDetail(r.id))}>Ver</Button>
                    <Button size="sm" variant="outline" disabled={!canResend(r.status)} onClick={async () => { await dteResend(r.id); await load(); }}>Reenviar</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Detalle DTE</DialogTitle></DialogHeader>
          {selected && (
            <div className="space-y-3 text-sm">
              <p><strong>No. Control:</strong> {selected.control_number}</p>
              <p><strong>Código generación:</strong> {selected.codigo_generacion}</p>
              <p><strong>Sello recepción:</strong> {selected.sello_recepcion || "-"}</p>
              <p><strong>Firma:</strong> {selected.firma || "-"}</p>
              <p><strong>Recibido MH:</strong> {selected.recibido_at ? formatDateTimeSV(selected.recibido_at) : "-"}</p>
              <p><strong>Estado MH:</strong> {selected.estado_mh || selected.hacienda_state || "-"}</p>
              <p><strong>Estado Hacienda:</strong> {selected.hacienda_state || "-"}</p>
              <p><strong>Error:</strong> {selected.error_message || "-"}</p>
              <div className="flex gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={() => copy(selected.control_number)}>Copiar control</Button>
                <Button size="sm" variant="outline" onClick={() => copy(selected.codigo_generacion)}>Copiar código</Button>
                <Button size="sm" variant="outline" onClick={() => copy(selected.sello_recepcion)}>Copiar sello</Button>
                <Button size="sm" onClick={async () => { try { await dteSendWhatsapp(selected.id); } catch { toast({ title: "Próximamente" }); } }}>WhatsApp</Button>
                <Button size="sm" variant="outline" onClick={async () => { try { await dteSendEmail(selected.id); } catch { toast({ title: "Próximamente" }); } }}>Correo</Button>
                <Button size="sm" variant="outline" onClick={async () => {
                  const blob = await downloadOrderReceiptPdf(selected.sale_id);
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `receipt_order_${selected.sale_id}.pdf`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}>Descargar PDF</Button>
                <Button size="sm" variant="destructive" onClick={async () => { await dteInvalidate(selected.id, "Anulación desde panel"); toast({ title: "Invalidación creada" }); setSelected(null); await load(); }}>Invalidar</Button>
                <Button size="sm" variant="secondary" onClick={async () => { await dteCreateCreditNote(selected.id, "Nota de crédito desde panel"); toast({ title: "Nota de crédito creada" }); }}>Nota de crédito</Button>
              </div>
              {selected.request_payload && <pre className="bg-muted p-3 rounded text-xs overflow-auto">{JSON.stringify(selected.request_payload, null, 2)}</pre>}
              {(selected.mh_response_json || selected.response_payload) && (
                <pre className="bg-muted p-3 rounded text-xs overflow-auto">
                  {JSON.stringify(selected.mh_response_json || selected.response_payload, null, 2)}
                </pre>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
