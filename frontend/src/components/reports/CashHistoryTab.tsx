import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { downloadCashSessionTicketPdf, getCashSessionsHistory, type CashSessionHistoryRow } from "@/lib/api";
import { formatDateTimeSV } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import { toast } from "sonner";

export const CashHistoryTab = () => {
  const [rows, setRows] = useState<CashSessionHistoryRow[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [openDetail, setOpenDetail] = useState(false);
  const [selectedRow, setSelectedRow] = useState<CashSessionHistoryRow | null>(null);
  const [downloadingSessionId, setDownloadingSessionId] = useState<number | null>(null);

  const load = async () => {
    setRows(await getCashSessionsHistory({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }));
  };

  useEffect(() => { load(); }, []);

  const handleDownloadPdf = async (sessionId: number) => {
    if (downloadingSessionId === sessionId) return;
    setDownloadingSessionId(sessionId);
    try {
      await downloadCashSessionTicketPdf(sessionId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo descargar ticket PDF");
    } finally {
      setDownloadingSessionId((current) => (current === sessionId ? null : current));
    }
  };

  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => new Date(b.openedAt).getTime() - new Date(a.openedAt).getTime()),
    [rows]
  );

  return (
    <div className="space-y-4">
      <Card className="p-4 md:p-6">
        <div className="flex flex-wrap gap-3">
          <Input className="h-12 min-w-[180px] rounded-xl md:h-14" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Input className="h-12 min-w-[180px] rounded-xl md:h-14" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <Button className="min-h-12 rounded-xl px-5 md:min-h-14" onClick={load}>Filtrar</Button>
        </div>
      </Card>

      <Card className="p-0">
        <div className="overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha apertura</TableHead>
                <TableHead>Fecha cierre</TableHead>
                <TableHead>Usuario</TableHead>
                <TableHead>Esperado</TableHead>
                <TableHead>Contado</TableHead>
                <TableHead>Diferencia</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRows.map((r) => (
                <TableRow key={r.id} className="min-h-14">
                  <TableCell>{formatDateTimeSV(r.openedAt)}</TableCell>
                  <TableCell>{r.closedAt ? formatDateTimeSV(r.closedAt) : "-"}</TableCell>
                  <TableCell>{r.openedByUsername}</TableCell>
                  <TableCell>{formatMoney(r.expectedCash)}</TableCell>
                  <TableCell>{formatMoney(r.countedCash)}</TableCell>
                  <TableCell className={r.difference === 0 ? "" : r.difference > 0 ? "text-emerald-600 font-semibold" : "text-destructive font-semibold"}>{formatMoney(r.difference)}</TableCell>
                  <TableCell>
                    <Badge variant={r.status === "closed" ? "default" : "secondary"}>{r.status === "closed" ? "Cerrada" : "Abierta"}</Badge>
                  </TableCell>
                  <TableCell className="flex flex-wrap gap-2 py-3">
                    <Button className="min-h-11 rounded-xl px-4" size="sm" variant="outline" onClick={() => { setSelectedRow(r); setOpenDetail(true); }}>Ver detalle</Button>
                    <Button className="min-h-11 rounded-xl px-4" size="sm" disabled={downloadingSessionId === r.id} onClick={() => void handleDownloadPdf(r.id)}>{downloadingSessionId === r.id ? "Descargando..." : "PDF"}</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <Dialog open={openDetail} onOpenChange={setOpenDetail}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Detalle de cierre de caja</DialogTitle></DialogHeader>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Ventas efectivo</span><span>{formatMoney(selectedRow?.summary?.methods.cash ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas tarjeta</span><span>{formatMoney(selectedRow?.summary?.methods.card ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas transferencia</span><span>{formatMoney(selectedRow?.summary?.methods.transfer ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas PedidosYa</span><span>{formatMoney(selectedRow?.summary?.methods.pedidosYa ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas PayPal</span><span>{formatMoney(selectedRow?.summary?.methods.payPal ?? 0)}</span></div>
            <div className="flex justify-between font-semibold"><span>Total ventas</span><span>{formatMoney((selectedRow?.summary?.methods.cash ?? 0) + (selectedRow?.summary?.methods.card ?? 0) + (selectedRow?.summary?.methods.transfer ?? 0) + (selectedRow?.summary?.methods.pedidosYa ?? 0) + (selectedRow?.summary?.methods.payPal ?? 0))}</span></div>
            <div className="flex justify-between"><span>Pagos/Ingresos en efectivo</span><span>{formatMoney(selectedRow?.summary?.totalCashSales ?? 0)}</span></div>
            <div className="flex justify-between"><span>Gastos/Salidas</span><span>{formatMoney(selectedRow?.summary?.totalCashOut ?? 0)}</span></div>
            <div className="flex justify-between"><span>Efectivo esperado</span><span>{formatMoney(selectedRow?.summary?.expectedCashInDrawer ?? 0)}</span></div>
            <div className="flex justify-between"><span>Efectivo contado</span><span>{formatMoney(selectedRow?.summary?.countedCash ?? 0)}</span></div>
            <div className="flex justify-between"><span>Diferencia</span><span>{formatMoney(selectedRow?.difference ?? 0)}</span></div>
            <div className="rounded-md border p-2 text-muted-foreground">{selectedRow?.notes?.trim() || "Sin notas"}</div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
