import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Clock, ChefHat } from "lucide-react";
import { cn } from "@/lib/utils";
import { createPrintJob, markPrintJobPrinted, getActiveOrders, updateOrderStatus, Order, PrintJob } from "@/lib/api";
import { useServiceTypes } from "@/hooks/useServiceTypes";
import { PrintPreviewDialog } from "@/components/printing/PrintPreviewDialog";
import { toast } from "sonner";
import { PageLayout } from "@/components/layout/PageLayout";

const Kitchen = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const { activeServiceTypes: serviceTypes } = useServiceTypes();
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [kitchenJob, setKitchenJob] = useState<PrintJob | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  const loadOrders = useCallback(async () => {
    const branchId = localStorage.getItem("selected_branch_id") || undefined;
    const data = await getActiveOrders({ branchId, serviceType: filter === "all" ? "all" : filter });
    setOrders(data);
  }, [filter]);

  useEffect(() => {
    loadOrders().catch((error) => {
      console.error("Failed to load kitchen orders", error);
    });
    const interval = setInterval(() => {
      loadOrders().catch((error) => {
        console.error("Failed to refresh kitchen orders", error);
      });
    }, 5000);
    return () => clearInterval(interval);
  }, [loadOrders]);


  const getStatusColor = (prepTime: number) => {
    if (prepTime < 10) return "status-new";
    if (prepTime < 15) return "status-preparing";
    if (prepTime < 20) return "status-ready";
    return "status-late";
  };

  const getStatusBadge = (prepTime: number) => {
    if (prepTime < 10) return { label: "A Tiempo", variant: "default" as const };
    if (prepTime < 15) return { label: "En Proceso", variant: "secondary" as const };
    if (prepTime < 20) return { label: "Casi Listo", variant: "outline" as const };
    return { label: "Retrasado", variant: "destructive" as const };
  };

  const handleStatusUpdate = async (orderId: number, newStatus: Order["status"]) => {
    try {
      await updateOrderStatus(orderId, newStatus);
      await loadOrders();
    } catch (error) {
      console.error("Failed to update order status", error);
    }
  };

  const handlePrintKitchen = async (order: Order) => {
    try {
      const job = await createPrintJob({ orderId: order.id, type: "kitchen" });
      setSelectedOrder(order);
      setKitchenJob(job);
      setIsPreviewOpen(true);
    } catch (error) {
      console.error("Failed to create kitchen ticket", error);
      toast.error("No se pudo generar la comanda");
    }
  };

  const handleMarkPrinted = async () => {
    if (!kitchenJob) return;
    try {
      const job = await markPrintJobPrinted(kitchenJob.id);
      setKitchenJob(job);
      toast.success("Comanda marcada como impresa");
    } catch (error) {
      console.error("Failed to mark kitchen ticket", error);
      toast.error("No se pudo actualizar la comanda");
    }
  };

  const handleReprint = async () => {
    if (!selectedOrder) return;
    await handlePrintKitchen(selectedOrder);
  };

  const filteredOrders = orders.filter((order) => {
    if (filter === "all") return order.status !== "delivered";
    return order.serviceType === filter && order.status !== "delivered";
  });

  const serviceTypeLabelByKey = serviceTypes.reduce<Record<string, string>>((acc, item) => {
    acc[item.key] = item.label;
    return acc;
  }, {});

  return (
    <PageLayout
      title="Pantalla de Cocina"
      subtitle="Monitorea pedidos activos y gestiona su estado en tiempo real."
      actions={<ChefHat className="h-6 w-6 text-secondary" />}
    >
      <div className="space-y-6">
        <Card className="p-4 md:p-6">
          <div className="flex flex-wrap gap-3">
            {[{ key: "all", label: "Todos" }, ...serviceTypes.map((item) => ({ key: item.key, label: item.label }))].map((item) => (
              <Button
                key={item.key}
                variant={filter === item.key ? "default" : "outline"}
                onClick={() => setFilter(item.key)}
                className="min-h-12 rounded-xl px-5 text-sm font-semibold md:min-h-14 md:text-base"
              >
                {item.label}
              </Button>
            ))}
          </div>
        </Card>

        {filteredOrders.length === 0 ? (
          <Card className="flex min-h-[45vh] items-center justify-center p-8">
            <div className="text-center">
              <ChefHat className="mx-auto mb-4 h-20 w-20 text-muted-foreground/50" />
              <h3 className="mb-2 text-xl font-semibold">No hay pedidos pendientes</h3>
              <p className="text-muted-foreground">Los nuevos pedidos aparecerán aquí automáticamente</p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {filteredOrders.map((order) => {
            const statusBadge = getStatusBadge(order.prepTime);
            const statusColor = getStatusColor(order.prepTime);

            return (
              <Card
                key={order.id}
                className={cn(
                  "p-4 border-l-4 transition-all hover:shadow-lg",
                  `border-l-${statusColor}`
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-2xl font-bold">#{order.orderNumber}</h3>
                    <p className="text-sm text-muted-foreground">
                      {serviceTypeLabelByKey[order.serviceType ?? ""] ?? order.serviceType ?? "Sin tipo"}
                    </p>
                    {order.customerName && (
                      <p className="text-sm font-medium mt-1">{order.customerName}</p>
                    )}
                  </div>
                  <div className="text-right">
                    <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
                    <div className="flex items-center gap-1 mt-2 text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span className="text-xs">{order.prepTime} min</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  {order.items.map((item) => (
                    <div key={item.id} className="text-sm">
                      <div className="flex items-start gap-2">
                        <Badge variant="outline" className="shrink-0">
                          {item.quantity}x
                        </Badge>
                        <div className="flex-1">
                          <p className="font-medium">{item.productName}</p>
                          {item.modifiers.length > 0 && (
                            <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
                              {item.modifiers.map((mod, idx) => (
                                <li key={idx}>• {mod}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex gap-2">
                  {order.status === "new" && (
                    <Button
                      className="min-h-12 flex-1 rounded-xl md:min-h-14"
                      variant="outline"
                      onClick={() => handleStatusUpdate(order.id, "preparing")}
                    >
                      Iniciar
                    </Button>
                  )}
                  {order.status === "preparing" && (
                    <Button
                      className="min-h-12 flex-1 rounded-xl md:min-h-14"
                      variant="default"
                      onClick={() => handleStatusUpdate(order.id, "ready")}
                    >
                      Marcar Listo
                    </Button>
                  )}
                  {order.status === "ready" && (
                    <Button
                      className="min-h-12 flex-1 rounded-xl md:min-h-14"
                      variant="secondary"
                      onClick={() => handleStatusUpdate(order.id, "delivered")}
                    >
                      Entregado
                    </Button>
                  )}
                  <Button
                    className="min-h-12 flex-1 rounded-xl md:min-h-14"
                    variant="outline"
                    onClick={() => handlePrintKitchen(order)}
                  >
                    Imprimir
                  </Button>
                </div>
              </Card>
            );
          })}
          </div>
        )}

        <PrintPreviewDialog
          open={isPreviewOpen}
          onOpenChange={setIsPreviewOpen}
          job={kitchenJob}
          onMarkPrinted={handleMarkPrinted}
          onReprint={handleReprint}
        />

      </div>
    </PageLayout>
  );
};

export default Kitchen;
