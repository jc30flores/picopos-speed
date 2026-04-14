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

const ALERT_TOLERANCE = 0.01;
const WARNING_TOLERANCE = 1.0;

const getDifferenceTone = (value: number) => {
  const abs = Math.abs(value);
  if (abs <= ALERT_TOLERANCE) return "ok";
  if (abs <= WARNING_TOLERANCE) return "warn";
  return "alert";
};

const differenceTextClass = (value: number) => {
  const tone = getDifferenceTone(value);
  if (tone === "ok") return "text-emerald-600 dark:text-emerald-400";
  if (tone === "warn") return "text-amber-600 dark:text-amber-400";
  return "text-destructive";
};

const badgeClassesByTone: Record<string, string> = {
  ok: "border-emerald-300/70 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300",
  warn: "border-amber-300/70 bg-amber-500/10 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300",
  alert: "border-red-300/70 bg-red-500/10 text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-300",
};

type AuditSnapshot = {
  expectedCash: number;
  countedCash: number;
  countedBills: number;
  countedCoins: number;
  expectedCard: number;
  countedPosCards: number;
  expectedPedidosYa: number;
  countedPedidosYa: number;
  expectedTransfer: number;
  expectedPayPal: number;
  cashIn: number;
  cashOut: number;
  totalSales: number;
  overallDiff: number;
  effectiveDiff: number;
  posDiff: number;
  pedidosYaDiff: number;
};

const buildAuditSnapshot = (row: CashSessionHistoryRow | null): AuditSnapshot => {
  const summary = row?.summary;
  const expectedCash = summary?.expectedCashInDrawer ?? 0;
  const countedBills = summary?.countedBills ?? 0;
  const countedCoins = summary?.countedCoins ?? 0;
  const countedCash = (summary?.countedCash ?? 0) || countedBills + countedCoins;
  const expectedCard = summary?.methods.card ?? 0;
  const countedPosCards = summary?.countedPosCards ?? 0;
  const expectedPedidosYa = summary?.methods.pedidosYa ?? 0;
  const countedPedidosYa = summary?.countedPedidosYa ?? 0;
  const expectedTransfer = summary?.methods.transfer ?? 0;
  const expectedPayPal = summary?.methods.payPal ?? 0;
  const totalSales = expectedCash + expectedCard + expectedTransfer + expectedPedidosYa + expectedPayPal;
  return {
    expectedCash,
    countedCash,
    countedBills,
    countedCoins,
    expectedCard,
    countedPosCards,
    expectedPedidosYa,
    countedPedidosYa,
    expectedTransfer,
    expectedPayPal,
    cashIn: summary?.totalCashSales ?? 0,
    cashOut: summary?.totalCashOut ?? 0,
    totalSales,
    overallDiff: row?.difference ?? 0,
    effectiveDiff: countedCash - expectedCash,
    posDiff: countedPosCards - expectedCard,
    pedidosYaDiff: countedPedidosYa - expectedPedidosYa,
  };
};

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
  const selectedAudit = useMemo(() => buildAuditSnapshot(selectedRow), [selectedRow]);

  const tableAuditSummary = (row: CashSessionHistoryRow) => {
    const audit = buildAuditSnapshot(row);
    const issues = [audit.effectiveDiff, audit.posDiff, audit.pedidosYaDiff].filter((v) => Math.abs(v) > ALERT_TOLERANCE).length;
    if (issues === 0) return { label: "Cuadra", tone: "ok" as const };
    if (issues === 1) return { label: "Revisar 1 diferencia", tone: "warn" as const };
    return { label: `Revisar ${issues} diferencias`, tone: "alert" as const };
  };

  const detailAlerts = useMemo(() => {
    if (!selectedRow) return [];
    const alerts: Array<{ tone: "ok" | "warn" | "alert"; text: string }> = [];
    const addAlert = (diff: number, okText: string, problemText: string) => {
      const tone = getDifferenceTone(diff);
      if (tone === "ok") {
        alerts.push({ tone: "ok", text: okText });
        return;
      }
      alerts.push({ tone, text: `${problemText} (${formatMoney(diff)})` });
    };
    addAlert(selectedAudit.effectiveDiff, "El efectivo contado cuadra con lo esperado.", "El efectivo contado no coincide con el esperado del sistema");
    addAlert(selectedAudit.posDiff, "POS tarjetas coincide con ventas en tarjeta.", "El total reportado en POS tarjetas no coincide con las ventas tarjeta");
    addAlert(selectedAudit.pedidosYaDiff, "PedidosYa reportado coincide con ventas PedidosYa.", "El total reportado de PedidosYa no coincide con lo esperado");
    if (
      Math.abs(selectedAudit.effectiveDiff) > WARNING_TOLERANCE &&
      Math.abs(selectedAudit.posDiff) > WARNING_TOLERANCE
    ) {
      alerts.push({
        tone: "warn",
        text: "Se recomienda revisar clasificación de métodos de pago (efectivo/tarjeta).",
      });
    }
    return alerts;
  }, [selectedAudit, selectedRow]);

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
                <TableHead>Auditoría</TableHead>
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
                  <TableCell>
                    {(() => {
                      const audit = tableAuditSummary(r);
                      return (
                        <Badge className={`border font-medium ${badgeClassesByTone[audit.tone]}`}>
                          {audit.label}
                        </Badge>
                      );
                    })()}
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
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
          <DialogHeader className="space-y-2">
            <DialogTitle className="text-xl font-semibold">Detalle de cierre de caja</DialogTitle>
            <p className="text-sm text-muted-foreground">
              Vista de auditoría: sistema vs reportado por usuario.
            </p>
          </DialogHeader>
          <div className="space-y-4 text-sm">
            <Card className="p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-foreground">Resumen general</h4>
                {(() => {
                  const tone = getDifferenceTone(selectedAudit.overallDiff);
                  const label = tone === "ok" ? "Cuadra" : selectedAudit.overallDiff > 0 ? "Sobrante" : "Faltante";
                  return <Badge className={`border ${badgeClassesByTone[tone]}`}>{label}</Badge>;
                })()}
              </div>
              <div className="grid gap-3 text-sm md:grid-cols-2 lg:grid-cols-3">
                <div><p className="text-xs text-muted-foreground">Estado</p><p className="font-medium">{selectedRow?.status === "closed" ? "Cerrada" : "Abierta"}</p></div>
                <div><p className="text-xs text-muted-foreground">Usuario apertura</p><p className="font-medium">{selectedRow?.openedByUsername || "-"}</p></div>
                <div><p className="text-xs text-muted-foreground">Usuario cierre</p><p className="font-medium">{selectedRow?.closedByUsername || "-"}</p></div>
                <div><p className="text-xs text-muted-foreground">Fecha apertura</p><p className="font-medium">{selectedRow?.openedAt ? formatDateTimeSV(selectedRow.openedAt) : "-"}</p></div>
                <div><p className="text-xs text-muted-foreground">Fecha cierre</p><p className="font-medium">{selectedRow?.closedAt ? formatDateTimeSV(selectedRow.closedAt) : "-"}</p></div>
                <div><p className="text-xs text-muted-foreground">Monto de apertura</p><p className="font-semibold">{formatMoney(selectedRow?.summary?.openingCash ?? 0)}</p></div>
                <div><p className="text-xs text-muted-foreground">Total ventas</p><p className="font-semibold">{formatMoney(selectedAudit.totalSales)}</p></div>
                <div><p className="text-xs text-muted-foreground">Diferencia final</p><p className={`font-semibold ${differenceTextClass(selectedAudit.overallDiff)}`}>{formatMoney(selectedAudit.overallDiff)}</p></div>
              </div>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">Efectivo</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Esperado por sistema</span><span>{formatMoney(selectedAudit.expectedCash)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Billetes reportados</span><span>{formatMoney(selectedAudit.countedBills)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Monedas reportadas</span><span>{formatMoney(selectedAudit.countedCoins)}</span></div>
                  <div className="flex items-center justify-between border-t pt-2 font-medium"><span>Efectivo contado</span><span>{formatMoney(selectedAudit.countedCash)}</span></div>
                  <div className="flex items-center justify-between font-semibold">
                    <span>Diferencia efectivo</span>
                    <span className={differenceTextClass(selectedAudit.effectiveDiff)}>{formatMoney(selectedAudit.effectiveDiff)}</span>
                  </div>
                  <div className={`rounded-md px-2 py-1 text-sm font-semibold ${selectedAudit.effectiveDiff >= 0 ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-red-500/15 text-red-700 dark:text-red-300"}`}>
                    {selectedAudit.effectiveDiff >= 0 ? "Sobrante" : "Faltante"}: {formatMoney(Math.abs(selectedAudit.effectiveDiff))}
                  </div>
                </div>
              </Card>

              <Card className="p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">Medios externos / no efectivo</h4>
                <div className="space-y-3">
                  <div className="rounded-lg border p-3">
                    <div className="mb-1 flex items-center justify-between"><span className="font-medium">Tarjeta POS</span><span className={`font-semibold ${differenceTextClass(selectedAudit.posDiff)}`}>{formatMoney(selectedAudit.posDiff)}</span></div>
                    <div className="flex items-center justify-between text-muted-foreground"><span>Esperado sistema</span><span>{formatMoney(selectedAudit.expectedCard)}</span></div>
                    <div className="flex items-center justify-between text-muted-foreground"><span>Reportado usuario</span><span>{formatMoney(selectedAudit.countedPosCards)}</span></div>
                  </div>
                  <div className="rounded-lg border p-3">
                    <div className="mb-1 flex items-center justify-between"><span className="font-medium">PedidosYa</span><span className={`font-semibold ${differenceTextClass(selectedAudit.pedidosYaDiff)}`}>{formatMoney(selectedAudit.pedidosYaDiff)}</span></div>
                    <div className="flex items-center justify-between text-muted-foreground"><span>Esperado sistema</span><span>{formatMoney(selectedAudit.expectedPedidosYa)}</span></div>
                    <div className="flex items-center justify-between text-muted-foreground"><span>Reportado usuario</span><span>{formatMoney(selectedAudit.countedPedidosYa)}</span></div>
                  </div>
                </div>
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">Otros datos operativos</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Ventas transferencia</span><span>{formatMoney(selectedAudit.expectedTransfer)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Ventas PayPal</span><span>{formatMoney(selectedAudit.expectedPayPal)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Ingresos en efectivo</span><span>{formatMoney(selectedAudit.cashIn)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Gastos / salidas</span><span>{formatMoney(selectedAudit.cashOut)}</span></div>
                </div>
              </Card>

              <Card className="p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">Alertas / observaciones de auditoría</h4>
                <div className="space-y-2">
                  {detailAlerts.map((alert, index) => (
                    <div key={`${alert.text}-${index}`} className={`rounded-lg border px-3 py-2 text-sm ${badgeClassesByTone[alert.tone]}`}>
                      {alert.text}
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <Card className="p-4">
              <h4 className="mb-2 text-sm font-semibold text-foreground">Notas del cierre</h4>
              <div className="rounded-md border bg-muted/30 p-3 text-muted-foreground">{selectedRow?.notes?.trim() || "Sin notas"}</div>
            </Card>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
