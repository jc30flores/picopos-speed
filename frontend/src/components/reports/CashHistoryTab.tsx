import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { downloadCashSessionTicketPdf, getCashSessionsHistory, type CashSessionHistoryRow } from "@/lib/api";
import { formatMoney } from "@/lib/money";

export const CashHistoryTab = () => {
  const [rows, setRows] = useState<CashSessionHistoryRow[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [openDetail, setOpenDetail] = useState(false);
  const [selectedRow, setSelectedRow] = useState<CashSessionHistoryRow | null>(null);

  const load = async () => {
    setRows(await getCashSessionsHistory({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }));
  };

  useEffect(() => { load(); }, []);
  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => new Date(b.openedAt).getTime() - new Date(a.openedAt).getTime()),
    [rows]
  );

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <Button onClick={load}>Filtrar</Button>
      </div>
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
            <TableRow key={r.id}>
              <TableCell>{new Date(r.openedAt).toLocaleString()}</TableCell>
              <TableCell>{r.closedAt ? new Date(r.closedAt).toLocaleString() : "-"}</TableCell>
              <TableCell>{r.openedByUsername}</TableCell>
              <TableCell>{formatMoney(r.expectedCash)}</TableCell>
              <TableCell>{formatMoney(r.countedCash)}</TableCell>
              <TableCell className={r.difference === 0 ? "" : r.difference > 0 ? "text-emerald-600 font-semibold" : "text-destructive font-semibold"}>{formatMoney(r.difference)}</TableCell>
              <TableCell>
                <Badge variant={r.status === "closed" ? "default" : "secondary"}>{r.status === "closed" ? "Cerrada" : "Abierta"}</Badge>
              </TableCell>
              <TableCell className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => { setSelectedRow(r); setOpenDetail(true); }}>Ver detalle</Button>
                <Button size="sm" onClick={() => downloadCashSessionTicketPdf(r.id)}>PDF</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={openDetail} onOpenChange={setOpenDetail}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Detalle de cierre de caja</DialogTitle></DialogHeader>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Ventas efectivo</span><span>{formatMoney(selectedRow?.summary?.methods.cash ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas tarjeta</span><span>{formatMoney(selectedRow?.summary?.methods.card ?? 0)}</span></div>
            <div className="flex justify-between"><span>Ventas transferencia</span><span>{formatMoney(selectedRow?.summary?.methods.transfer ?? 0)}</span></div>
            <div className="flex justify-between font-semibold"><span>Total ventas</span><span>{formatMoney((selectedRow?.summary?.totalCashSales ?? 0) + (selectedRow?.summary?.methods.card ?? 0) + (selectedRow?.summary?.methods.transfer ?? 0) + (selectedRow?.summary?.methods.pedidosYa ?? 0) + (selectedRow?.summary?.methods.payPal ?? 0))}</span></div>
            <div className="flex justify-between"><span>Diferencia</span><span>{formatMoney(selectedRow?.difference ?? 0)}</span></div>
            <div className="rounded-md border p-2 text-muted-foreground">{selectedRow?.notes?.trim() || "Sin notas"}</div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
