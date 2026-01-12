import { Navigation } from "@/components/Navigation";
import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Clock, ChefHat } from "lucide-react";
import { cn } from "@/lib/utils";
import { createPrintJob, markPrintJobPrinted, getActiveOrders, updateOrderStatus, Order, PrintJob } from "@/lib/api";
import { PrintPreviewDialog } from "@/components/printing/PrintPreviewDialog";
import { toast } from "sonner";

const Kitchen = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState<"all" | "dine-in" | "takeout" | "delivery">("all");
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [kitchenJob, setKitchenJob] = useState<PrintJob | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  const loadOrders = useCallback(async () => {
    const data = await getActiveOrders();
    setOrders(data);
  }, []);

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

  const serviceTypeLabels = {
    "dine-in": "En Local",
    takeout: "Para Llevar",
    delivery: "Delivery",
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <div className="pt-20 px-4 pb-4">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <ChefHat className="h-8 w-8 text-secondary" />
            <h1 className="text-3xl font-bold">Pantalla de Cocina</h1>
          </div>

          <div className="flex gap-2 flex-wrap">
            <Button
              variant={filter === "all" ? "default" : "outline"}
              onClick={() => setFilter("all")}
            >
              Todos
            </Button>
            <Button
              variant={filter === "dine-in" ? "default" : "outline"}
              onClick={() => setFilter("dine-in")}
            >
              En Local
            </Button>
            <Button
              variant={filter === "takeout" ? "default" : "outline"}
              onClick={() => setFilter("takeout")}
            >
              Para Llevar
            </Button>
            <Button
              variant={filter === "delivery" ? "default" : "outline"}
              onClick={() => setFilter("delivery")}
            >
              Delivery
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
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
                      {serviceTypeLabels[order.serviceType]}
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
                      className="flex-1"
                      variant="outline"
                      onClick={() => handleStatusUpdate(order.id, "preparing")}
                    >
                      Iniciar
                    </Button>
                  )}
                  {order.status === "preparing" && (
                    <Button
                      className="flex-1"
                      variant="default"
                      onClick={() => handleStatusUpdate(order.id, "ready")}
                    >
                      Marcar Listo
                    </Button>
                  )}
                  {order.status === "ready" && (
                    <Button
                      className="flex-1"
                      variant="secondary"
                      onClick={() => handleStatusUpdate(order.id, "delivered")}
                    >
                      Entregado
                    </Button>
                  )}
                  <Button
                    className="flex-1"
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

        <PrintPreviewDialog
          open={isPreviewOpen}
          onOpenChange={setIsPreviewOpen}
          job={kitchenJob}
          onMarkPrinted={handleMarkPrinted}
          onReprint={handleReprint}
        />

        {filteredOrders.length === 0 && (
          <div className="text-center py-16">
            <ChefHat className="h-20 w-20 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-xl font-semibold mb-2">No hay pedidos pendientes</h3>
            <p className="text-muted-foreground">
              Los nuevos pedidos aparecerán aquí automáticamente
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Kitchen;
