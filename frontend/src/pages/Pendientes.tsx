import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CreditCard, LayoutGrid, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "sonner";
import { formatMoney } from "@/lib/money";
import { formatDateTimeSV } from "@/lib/datetime";
import { getPendingOrders, setOrderPending, verifyPrivilegedPin, type Order } from "@/lib/api";
import { useAuth } from "@/context/useAuth";

const getEstadoLabel = (row: Order): string => {
  if (row.pendingCompletionType === "paid") return "Pagada";
  if (row.pendingCompletionType === "canceled" || row.status === "canceled") return "Cancelada";
  if (row.pendingCompletionType === "removed" || !row.isPending) return "Removida";
  if (row.paymentStatus === "paid") return "Pagada";
  return "Pendiente de pago";
};

const getEstadoBadgeClass = (row: Order): string => {
  const label = getEstadoLabel(row);
  if (label === "Pendiente de pago") return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300";
  if (label === "Pagada") return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
  return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300";
};

const PendientesPage = () => {
  const [rows, setRows] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"pending" | "finalized">("pending");
  const [query, setQuery] = useState("");
  const [pendingPinOrderId, setPendingPinOrderId] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const [removalReason, setRemovalReason] = useState("");
  const selectedBranchId = Number(localStorage.getItem("selected_branch_id") || "0") || 0;
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const data = await getPendingOrders({ branchId: selectedBranchId || undefined, tab, query });
      setRows(data.results);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo cargar Open Orders.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [selectedBranchId, tab, query]);

  const canAutoUnmark = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
  const summary = useMemo(() => ({ total: rows.length, totalAmount: rows.reduce((acc, row) => acc + (row.totalPayable ?? row.total), 0) }), [rows]);

  const goToPos = (orderId: number, mode: "edit" | "pay") =>
    navigate(`/pos?pending_order_id=${orderId}&mode=${mode}`, { state: { fromOpenOrders: true } });

  const handleRemovePending = async (order: Order, authorizationPin = "") => {
    try {
      if (!removalReason.trim()) {
        toast.error("El motivo es obligatorio.");
        return;
      }
      await setOrderPending(order.id, { isPending: false, authorizationPin, removalReason: removalReason.trim() });
      toast.success("Orden removida de Open Orders.");
      setRemovalReason("");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo remover la orden.");
    }
  };

  return (
    <div className="h-[100dvh] overflow-x-hidden overflow-y-auto bg-background">
      <div className="h-full px-2 pb-4 pt-4 lg:px-4">
        <div className="flex h-full min-h-0 flex-col gap-4">
        <Card className="p-4 md:p-6">
          <div className="flex items-start justify-between gap-3">
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="h-12 w-12 shrink-0 rounded-full"
              onClick={() => navigate("/")}
              aria-label="Menú principal"
              title="Menú principal"
            >
              <LayoutGrid className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-semibold">Open Orders</h1>
              <p className="text-sm text-muted-foreground">Órdenes guardadas para retomar, editar o cobrar.</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{summary.total} órdenes</Badge>
              <Badge variant="outline">{formatMoney(summary.totalAmount)}</Badge>
              <Button className="h-11 px-6 text-base font-semibold" onClick={() => navigate("/pos", { state: { fromOpenOrders: true } })}>POS</Button>
            </div>
          </div>
          <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <Tabs value={tab} onValueChange={(value) => setTab(value as "pending" | "finalized")}>
              <TabsList>
                <TabsTrigger value="pending">Pendientes</TabsTrigger>
                <TabsTrigger value="finalized">Finalizadas</TabsTrigger>
              </TabsList>
            </Tabs>
            <Input
              className="h-11 md:max-w-md"
              placeholder="Buscar por referencia, cliente u orden..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </Card>

        <Card className="min-h-0 flex-1 p-0">
          <div className="h-full overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead># Orden</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Servicio</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Referencia</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Fecha/Hora</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-semibold">#{row.orderNumber}</TableCell>
                    <TableCell>{row.customerName || "Consumidor final"}</TableCell>
                    <TableCell>{row.serviceType || "-"}</TableCell>
                    <TableCell>
                      <Badge className={`whitespace-nowrap border-0 ${getEstadoBadgeClass(row)}`}>
                        {getEstadoLabel(row)}
                      </Badge>
                    </TableCell>
                    <TableCell>{row.pendingReference || "-"}</TableCell>
                    <TableCell>{formatMoney(row.totalPayable ?? row.total)}</TableCell>
                    <TableCell>{formatDateTimeSV((row.pendingCompletedAt || row.pendingMarkedAt || row.createdAt) as string | Date)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1 whitespace-nowrap">
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-9 w-9" onClick={() => goToPos(row.id, "edit")} aria-label="Editar">
                                <Pencil className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Editar</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-9 w-9" onClick={() => goToPos(row.id, "pay")} aria-label="Cobrar">
                                <CreditCard className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Cobrar</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-9 w-9 text-destructive hover:text-destructive"
                                onClick={() => setPendingPinOrderId(row.id)}
                                aria-label="Remover"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Remover</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">No hay órdenes en Open Orders.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </Card>
        </div>
      </div>

      <Dialog open={Boolean(pendingPinOrderId)} onOpenChange={(open) => { if (!open) { setPendingPinOrderId(null); setPin(""); setRemovalReason(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Autorización requerida</DialogTitle>
            <DialogDescription>{canAutoUnmark ? "Ingresa el motivo para remover la orden de Open Orders." : "Ingresa PIN de gerente/admin para remover de Open Orders."}</DialogDescription>
          </DialogHeader>
          <Input placeholder="Motivo de remoción" value={removalReason} onChange={(e) => setRemovalReason(e.target.value)} />
          {!canAutoUnmark && <Input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D+/g, "").slice(0, 6))} maxLength={6} autoFocus />}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPendingPinOrderId(null); setPin(""); setRemovalReason(""); }}>Cancelar</Button>
            <Button
              onClick={async () => {
                if (!pendingPinOrderId) return;
                try {
                  if (canAutoUnmark) {
                    await handleRemovePending({ id: pendingPinOrderId } as Order);
                  } else {
                    await verifyPrivilegedPin(pin);
                    await handleRemovePending({ id: pendingPinOrderId } as Order, pin);
                  }
                  setPendingPinOrderId(null);
                  setPin("");
                  setRemovalReason("");
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "PIN inválido.");
                }
              }}
            >
              Autorizar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PendientesPage;
