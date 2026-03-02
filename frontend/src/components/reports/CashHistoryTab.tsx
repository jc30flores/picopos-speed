import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { getCashSessionDetail, getCashSessionsHistory, type CashSessionHistoryRow, type CashTransaction } from "@/lib/api";

export const CashHistoryTab = () => {
  const [rows, setRows] = useState<CashSessionHistoryRow[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [openDetail, setOpenDetail] = useState(false);
  const [detailTx, setDetailTx] = useState<CashTransaction[]>([]);

  const load = async () => {
    setRows(await getCashSessionsHistory({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }));
  };

  useEffect(() => { load(); }, []);

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
            <TableHead>Apertura</TableHead><TableHead>Cierre</TableHead><TableHead>Caja</TableHead><TableHead>Usuario</TableHead><TableHead>Inicial</TableHead><TableHead>Esperado</TableHead><TableHead>Contado</TableHead><TableHead>Diferencia</TableHead><TableHead>Métodos</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell>{new Date(r.openedAt).toLocaleString()}</TableCell>
              <TableCell>{r.closedAt ? new Date(r.closedAt).toLocaleString() : "-"}</TableCell>
              <TableCell>{r.registerName}</TableCell>
              <TableCell>{r.openedByUsername}</TableCell>
              <TableCell>${r.openingCash.toFixed(2)}</TableCell>
              <TableCell>${r.summary?.expectedCashInDrawer.toFixed(2)}</TableCell>
              <TableCell>${(r.closingCountedCash ?? 0).toFixed(2)}</TableCell>
              <TableCell>${(r.summary?.overShortCash ?? 0).toFixed(2)}</TableCell>
              <TableCell>E: ${r.summary?.methods.cash.toFixed(2)} / T: ${r.summary?.methods.card.toFixed(2)} / Tr: ${r.summary?.methods.transfer.toFixed(2)}</TableCell>
              <TableCell><Button size="sm" variant="outline" onClick={async () => { const d = await getCashSessionDetail(r.id); setDetailTx(d.transactions); setOpenDetail(true); }}>Detalle</Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={openDetail} onOpenChange={setOpenDetail}>
        <DialogContent>
          <DialogHeader><DialogTitle>Transacciones de sesión</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-[50vh] overflow-y-auto">
            {detailTx.map((tx) => (
              <div key={tx.id} className="border rounded px-2 py-1 text-sm flex justify-between">
                <span>{tx.type} - {tx.description}</span>
                <span>${tx.amount.toFixed(2)}</span>
              </div>
            ))}
            {detailTx.length === 0 && <div className="text-sm text-muted-foreground">Sin transacciones</div>}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
