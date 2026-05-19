import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClipboardList, CreditCard, Eye, LayoutGrid, Pencil, Search, Trash2 } from "lucide-react";
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
      toast.error(error instanceof Error ? error.message : "No se pudieron cargar las órdenes abiertas.");
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
      toast.success("Orden removida de Órdenes abiertas.");
      setRemovalReason("");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo remover la orden.");
    }
  };

  const authorizePendingRemoval = async () => {
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
  };

  return (
    <div className="h-[100dvh] overflow-x-hidden overflow-y-auto bg-background">
      <div className="h-full px-2 pb-4 pt-4 lg:px-4">
        <div className="flex h-full min-h-0 flex-col gap-4">
          <Card className="overflow-hidden border-border/70 bg-gradient-to-br from-muted/40 via-background to-background p-4 shadow-sm md:p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-3">
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
                  <div className="mb-1 inline-flex items-center gap-2 rounded-full border bg-background/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    <ClipboardList className="h-3 w-3" /> Gestión de pedidos
                  </div>
                  <h1 className="text-2xl font-semibold md:text-3xl">Órdenes abiertas</h1>
                  <p className="text-sm text-muted-foreground">Órdenes guardadas para retomar, editar o cobrar.</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{summary.total} órdenes</Badge>
                <Badge variant="outline">{formatMoney(summary.totalAmount)}</Badge>
                <Button className="h-11 px-5 font-semibold" onClick={() => navigate("/pos", { state: { fromOpenOrders: true } })}>
                  <LayoutGrid className="mr-2 h-4 w-4" /> Ir al POS
                </Button>
              </div>
            </div>
            <div className="mt-5 grid gap-3 lg:grid-cols-[auto_1fr_auto] lg:items-center">
              <Tabs value={tab} onValueChange={(value) => setTab(value as "pending" | "finalized")}>
                <TabsList className="h-11">
                  <TabsTrigger value="pending" className="min-h-10 px-5">Pendientes</TabsTrigger>
                  <TabsTrigger value="finalized" className="min-h-10 px-5">Finalizadas</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-11 pl-9"
                  placeholder="Buscar por referencia, cliente u orden..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">Estado: {tab === "pending" ? "Pendiente" : "Finalizada"}</Badge>
                <Badge variant="outline">Servicio: todos</Badge>
              </div>
            </div>
          </Card>

          <Card className="min-h-0 flex-1 overflow-hidden border-border/70 p-0 shadow-sm">
            <div className="h-full overflow-auto">
              <Table>
                <TableHeader className="bg-muted/40">
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
                    <TableRow key={row.id} className="align-middle">
                      <TableCell className="font-semibold">#{row.orderNumber}</TableCell>
                      <TableCell>{row.customerName || "Consumidor final"}</TableCell>
                      <TableCell><Badge variant="outline">{row.serviceType || "POS rápido"}</Badge></TableCell>
                      <TableCell>
                        <Badge className={`whitespace-nowrap border-0 ${getEstadoBadgeClass(row)}`}>
                          {tab === "finalized" ? "Finalizada" : getEstadoLabel(row)}
                        </Badge>
                      </TableCell>
                      <TableCell>{row.pendingReference || "-"}</TableCell>
                      <TableCell className="font-semibold">{formatMoney(row.totalPayable ?? row.total)}</TableCell>
                      <TableCell>{formatDateTimeSV((row.pendingCompletedAt || row.pendingMarkedAt || row.createdAt) as string | Date)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1 whitespace-nowrap">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button size="icon" variant="ghost" className="h-10 w-10" onClick={() => goToPos(row.id, "edit")} aria-label="Retomar">
                                  <Pencil className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Retomar</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button size="icon" variant="ghost" className="h-10 w-10" onClick={() => goToPos(row.id, "edit")} aria-label="Ver">
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Ver</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button size="icon" variant="ghost" className="h-10 w-10" onClick={() => goToPos(row.id, "pay")} aria-label="Cobrar">
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
                                  className="h-10 w-10 text-destructive hover:text-destructive"
                                  onClick={() => setPendingPinOrderId(row.id)}
                                  aria-label="Cancelar"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Cancelar</TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!loading && rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="py-14 text-center">
                        <div className="mx-auto flex max-w-sm flex-col items-center gap-2 text-muted-foreground">
                          <ClipboardList className="h-10 w-10 opacity-60" />
                          <p className="font-semibold text-foreground">No hay órdenes abiertas.</p>
                          <p className="text-sm">Las órdenes guardadas aparecerán aquí.</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </div>
      </div>

      <Dialog open={Boolean(pendingPinOrderId)} onOpenChange={(open) => { if (!open) { setPendingPinOrderId(null); setPin(""); setRemovalReason(""); } }}>
        <DialogContent onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void authorizePendingRemoval(); } if (event.key === "Escape") { setPendingPinOrderId(null); setPin(""); setRemovalReason(""); } }}>
          <DialogHeader>
            <DialogTitle>Autorización requerida</DialogTitle>
            <DialogDescription>{canAutoUnmark ? "Ingresa el motivo para remover la orden de Órdenes abiertas." : "Ingresa PIN de gerente/admin para remover de Órdenes abiertas."}</DialogDescription>
          </DialogHeader>
          <Input placeholder="Motivo de remoción" value={removalReason} onChange={(e) => setRemovalReason(e.target.value)} />
          {!canAutoUnmark && <Input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D+/g, "").slice(0, 6))} maxLength={6} autoFocus />}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPendingPinOrderId(null); setPin(""); setRemovalReason(""); }}>Cancelar</Button>
            <Button
              onClick={() => void authorizePendingRemoval()}
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
