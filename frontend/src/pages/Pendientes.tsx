import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { formatMoney } from "@/lib/money";
import { formatDateTimeSV } from "@/lib/datetime";
import { getPendingOrders, setOrderPending, verifyPrivilegedPin, type Order } from "@/lib/api";
import { useAuth } from "@/context/useAuth";

const stateLabel: Record<string, string> = {
  pending_payment: "Pendiente de pago",
  paid_pending_delivery: "Pagada pendiente entrega",
  in_kitchen: "En cocina",
  ready: "Lista",
  none: "Sin estado",
};

const PendientesPage = () => {
  const [rows, setRows] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingPinOrderId, setPendingPinOrderId] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const data = await getPendingOrders();
      setRows(data.results);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo cargar Pendientes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const canAutoUnmark = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
  const summary = useMemo(() => ({ total: rows.length, totalAmount: rows.reduce((acc, row) => acc + (row.totalPayable ?? row.total), 0) }), [rows]);

  const goToPos = (orderId: number, mode: "edit" | "pay") => navigate(`/pos?pending_order_id=${orderId}&mode=${mode}`);

  const handleRemovePending = async (order: Order, authorizationPin = "") => {
    try {
      await setOrderPending(order.id, { isPending: false, authorizationPin });
      toast.success("Orden retirada de Pendientes.");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo retirar la orden.");
    }
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <Card className="p-4 md:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">Pendientes</h1>
              <p className="text-sm text-muted-foreground">Órdenes guardadas para retomar, editar o cobrar.</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{summary.total} órdenes</Badge>
              <Badge variant="outline">{formatMoney(summary.totalAmount)}</Badge>
              <Button variant="outline" onClick={() => navigate("/")}>Menú</Button>
              <Button onClick={() => navigate("/pos")}>Ir al POS</Button>
            </div>
          </div>
        </Card>

        <Card className="p-0">
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead># Orden</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Servicio</TableHead>
                  <TableHead>Pago</TableHead>
                  <TableHead>Estado operativo</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Fecha/Hora</TableHead>
                  <TableHead>Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-semibold">#{row.orderNumber}</TableCell>
                    <TableCell>{row.customerName || "Consumidor final"}</TableCell>
                    <TableCell>{row.serviceType || "-"}</TableCell>
                    <TableCell>{row.paymentStatus === "paid" ? "Pagada" : "Pendiente"}</TableCell>
                    <TableCell>{stateLabel[row.pendingState || "none"]}</TableCell>
                    <TableCell>{formatMoney(row.totalPayable ?? row.total)}</TableCell>
                    <TableCell>{formatDateTimeSV((row.pendingMarkedAt || row.createdAt) as string | Date)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => goToPos(row.id, "edit")}>Editar</Button>
                        <Button size="sm" onClick={() => goToPos(row.id, "pay")}>Pagar</Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            if (canAutoUnmark) {
                              void handleRemovePending(row);
                            } else {
                              setPendingPinOrderId(row.id);
                            }
                          }}
                        >
                          Quitar de pendientes
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">No hay órdenes pendientes.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </Card>
      </div>

      <Dialog open={Boolean(pendingPinOrderId)} onOpenChange={(open) => { if (!open) { setPendingPinOrderId(null); setPin(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Autorización requerida</DialogTitle>
            <DialogDescription>Ingresa PIN de gerente/admin para retirar de pendientes.</DialogDescription>
          </DialogHeader>
          <Input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D+/g, "").slice(0, 6))} maxLength={6} autoFocus />
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPendingPinOrderId(null); setPin(""); }}>Cancelar</Button>
            <Button
              onClick={async () => {
                if (!pendingPinOrderId) return;
                try {
                  await verifyPrivilegedPin(pin);
                  await handleRemovePending({ id: pendingPinOrderId } as Order, pin);
                  setPendingPinOrderId(null);
                  setPin("");
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
