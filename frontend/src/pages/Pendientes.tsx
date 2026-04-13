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
  pending_payment: "Pending payment",
  paid_pending_delivery: "Paid pending delivery",
  in_kitchen: "In kitchen",
  ready: "Ready",
  none: "No state",
};

const PendientesPage = () => {
  const [rows, setRows] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingPinOrderId, setPendingPinOrderId] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const selectedBranchId = Number(localStorage.getItem("selected_branch_id") || "0") || 0;
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const data = await getPendingOrders({ branchId: selectedBranchId || undefined });
      setRows(data.results);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load Open Orders.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [selectedBranchId]);

  const canAutoUnmark = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
  const summary = useMemo(() => ({ total: rows.length, totalAmount: rows.reduce((acc, row) => acc + (row.totalPayable ?? row.total), 0) }), [rows]);

  const goToPos = (orderId: number, mode: "edit" | "pay") => navigate(`/pos?pending_order_id=${orderId}&mode=${mode}`);

  const handleRemovePending = async (order: Order, authorizationPin = "") => {
    try {
      await setOrderPending(order.id, { isPending: false, authorizationPin });
      toast.success("Order removed from Open Orders.");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove the order.");
    }
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <Card className="p-4 md:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">Open Orders</h1>
              <p className="text-sm text-muted-foreground">Saved orders to resume, edit or charge.</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{summary.total} orders</Badge>
              <Badge variant="outline">{formatMoney(summary.totalAmount)}</Badge>
              <Button variant="outline" onClick={() => navigate("/")}>Menu</Button>
              <Button onClick={() => navigate("/pos")}>Go to POS</Button>
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
                  <TableHead>Service</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Operational state</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Date/Time</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-semibold">#{row.orderNumber}</TableCell>
                    <TableCell>{row.customerName || "Consumer final"}</TableCell>
                    <TableCell>{row.serviceType || "-"}</TableCell>
                    <TableCell>{row.paymentStatus === "paid" ? "Paid" : "Pending"}</TableCell>
                    <TableCell>{stateLabel[row.pendingState || "none"]}</TableCell>
                    <TableCell>{formatMoney(row.totalPayable ?? row.total)}</TableCell>
                    <TableCell>{formatDateTimeSV((row.pendingMarkedAt || row.createdAt) as string | Date)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => goToPos(row.id, "edit")}>Edit</Button>
                        <Button size="sm" onClick={() => goToPos(row.id, "pay")}>Pay</Button>
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
                          Remove
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">No open orders.</TableCell>
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
            <DialogTitle>Authorization required</DialogTitle>
            <DialogDescription>Enter manager/admin PIN to remove from Open Orders.</DialogDescription>
          </DialogHeader>
          <Input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D+/g, "").slice(0, 6))} maxLength={6} autoFocus />
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPendingPinOrderId(null); setPin(""); }}>Cancel</Button>
            <Button
              onClick={async () => {
                if (!pendingPinOrderId) return;
                try {
                  await verifyPrivilegedPin(pin);
                  await handleRemovePending({ id: pendingPinOrderId } as Order, pin);
                  setPendingPinOrderId(null);
                  setPin("");
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "Invalid PIN.");
                }
              }}
            >
              Authorize
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PendientesPage;
