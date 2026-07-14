import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ChefHat, CheckCircle2, Clock, RefreshCw, Utensils } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getActiveOrders,
  getTableKitchenSummary,
  markTableKitchenItemReady,
  updateOrderStatus,
  type Order,
  type TableKitchenSessionSummary,
} from "@/lib/api";
import { PageLayout } from "@/components/layout/PageLayout";
import { toast } from "sonner";

type KitchenFilter = "all" | "in_kitchen" | "ready" | "tables" | "takeout" | "kiosk";

type KitchenCardItem = {
  key: string;
  source: "table" | "quick";
  itemId?: number;
  orderId?: number;
  productName: string;
  quantity: number;
  tableLabel: string;
  guestLabel: string;
  modifiers: string[];
  sentAt: string | Date | null;
  status: "sent" | "ready";
  serviceType?: string | null;
};

const FILTERS: Array<{ key: KitchenFilter; label: string }> = [
  { key: "all", label: "Todos" },
  { key: "in_kitchen", label: "En preparación" },
  { key: "ready", label: "Terminados" },
  { key: "tables", label: "Mesa" },
  { key: "takeout", label: "Para llevar" },
  { key: "kiosk", label: "Kiosk" },
];

const elapsedMinutes = (value: string | Date | null) => {
  if (!value) return 0;
  const time = value instanceof Date ? value.getTime() : new Date(value).getTime();
  if (!Number.isFinite(time)) return 0;
  return Math.max(0, Math.floor((Date.now() - time) / 60000));
};

const elapsedLabel = (value: string | Date | null) => {
  const minutes = elapsedMinutes(value);
  if (minutes < 1) return "Ahora";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
};

const statusTone = (item: KitchenCardItem) => {
  if (item.status === "ready") return "border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/40 dark:text-emerald-200";
  const minutes = elapsedMinutes(item.sentAt);
  if (minutes >= 20) return "border-red-300 bg-red-500/10 text-red-700 dark:border-red-500/40 dark:text-red-200";
  if (minutes >= 12) return "border-amber-300 bg-amber-500/10 text-amber-700 dark:border-amber-500/40 dark:text-amber-200";
  return "border-primary/30 bg-primary/10 text-primary";
};

const tableItemsFromSummary = (sessions: TableKitchenSessionSummary[]): KitchenCardItem[] =>
  sessions.flatMap((session) => {
    const people = session.people.length ? session.people : [{ label: "Mesa completa", items: session.items, total: session.total }];
    return people.flatMap((person) =>
      person.items
        .filter((item) => item.kitchenStatus === "sent" || item.kitchenStatus === "ready")
        .map((item) => ({
          key: `table-${item.id}`,
          source: "table" as const,
          itemId: item.id,
          productName: item.productName,
          quantity: item.quantity,
          tableLabel: session.tableLabel || "Mesa",
          guestLabel: item.guestLabel || item.tableGuestLabel || person.label || "Mesa completa",
          modifiers: item.modifiers || [],
          sentAt: item.kitchenSentAt,
          status: item.kitchenStatus === "ready" ? "ready" as const : "sent" as const,
          serviceType: "table",
        }))
    );
  });

const quickItemsFromOrders = (orders: Order[]): KitchenCardItem[] =>
  orders
    .filter((order) => order.status !== "delivered" && order.status !== "canceled")
    .flatMap((order) =>
      order.items.map((item) => ({
        key: `quick-${order.id}-${item.id}`,
        source: "quick" as const,
        orderId: order.id,
        productName: item.productName,
        quantity: item.quantity,
        tableLabel: order.tableLabel || `Orden #${order.orderNumber}`,
        guestLabel: item.assignedName || order.customerName || "Pedido rápido",
        modifiers: item.modifiers || [],
        sentAt: item.kitchenSentAt || order.createdAt,
        status: order.status === "ready" ? "ready" as const : "sent" as const,
        serviceType: order.serviceType,
      }))
    );

const Kitchen = () => {
  const [tableSessions, setTableSessions] = useState<TableKitchenSessionSummary[]>([]);
  const [quickOrders, setQuickOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState<KitchenFilter>("all");
  const [isLoading, setIsLoading] = useState(true);

  const loadKitchen = useCallback(async () => {
    const branchId = localStorage.getItem("selected_branch_id") || undefined;
    const [tableData, activeOrders] = await Promise.all([
      getTableKitchenSummary(),
      getActiveOrders({ branchId, serviceType: "all" }),
    ]);
    setTableSessions(tableData);
    setQuickOrders(activeOrders);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadKitchen().catch((error) => {
      console.error("Failed to load kitchen", error);
      setIsLoading(false);
    });
    const interval = window.setInterval(() => {
      loadKitchen().catch((error) => console.error("Failed to refresh kitchen", error));
    }, 6000);
    return () => window.clearInterval(interval);
  }, [loadKitchen]);

  const items = useMemo(() => [...tableItemsFromSummary(tableSessions), ...quickItemsFromOrders(quickOrders)], [quickOrders, tableSessions]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (filter === "in_kitchen") return item.status === "sent";
      if (filter === "ready") return item.status === "ready";
      if (filter === "tables") return item.source === "table";
      if (filter === "kiosk") return String(item.serviceType || "").toUpperCase() === "KIOSK";
      if (filter === "takeout") return ["TAKEOUT", "PARA_LLEVAR", "PARA LLEVAR"].includes(String(item.serviceType || "").toUpperCase());
      return true;
    });
  }, [filter, items]);

  const completeItem = async (item: KitchenCardItem) => {
    try {
      if (item.source === "table" && item.itemId) {
        await markTableKitchenItemReady(item.itemId);
      } else if (item.orderId) {
        await updateOrderStatus(item.orderId, "ready");
      }
      await loadKitchen();
      toast.success("Producto marcado como terminado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo actualizar cocina.");
    }
  };

  return (
    <PageLayout
      title="Pantalla de Cocina"
      subtitle="Pedidos activos por producto, mesa y persona."
      actions={<Button variant="outline" className="gap-2" onClick={() => void loadKitchen()}><RefreshCw className="h-4 w-4" />Actualizar</Button>}
    >
      <div className="space-y-5">
        <Card className="p-3">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <Button
                key={item.key}
                variant={filter === item.key ? "default" : "outline"}
                onClick={() => setFilter(item.key)}
                className="min-h-11 rounded-lg px-4 text-sm font-semibold"
              >
                {item.label}
              </Button>
            ))}
          </div>
        </Card>

        {isLoading ? (
          <Card className="flex min-h-[42vh] items-center justify-center p-8 text-muted-foreground">Cargando cocina...</Card>
        ) : filteredItems.length === 0 ? (
          <Card className="flex min-h-[48vh] items-center justify-center p-8">
            <div className="text-center">
              <ChefHat className="mx-auto mb-4 h-20 w-20 text-muted-foreground/50" />
              <h3 className="mb-2 text-xl font-semibold">No hay pedidos pendientes</h3>
              <p className="text-muted-foreground">Los productos enviados aparecerán aquí automáticamente.</p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 2xl:grid-cols-3">
            {filteredItems.map((item) => (
              <Card key={item.key} className={cn("flex min-h-72 flex-col justify-between border-2 p-5 shadow-sm", statusTone(item))}>
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="bg-background/70 text-sm">x{item.quantity}</Badge>
                        <Badge variant={item.status === "ready" ? "default" : "secondary"}>{item.status === "ready" ? "Terminado" : "En cocina"}</Badge>
                      </div>
                      <h2 className="break-words text-3xl font-black leading-tight tracking-normal text-foreground">{item.productName}</h2>
                    </div>
                    <div className="shrink-0 text-right text-sm font-semibold text-muted-foreground">
                      <Clock className="ml-auto mb-1 h-5 w-5" />
                      {elapsedLabel(item.sentAt)}
                    </div>
                  </div>

                  <div className="grid gap-2 text-base sm:grid-cols-2">
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="text-xs font-semibold uppercase text-muted-foreground">Mesa</p>
                      <p className="text-lg font-bold text-foreground">{item.tableLabel}</p>
                    </div>
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="text-xs font-semibold uppercase text-muted-foreground">Persona</p>
                      <p className="text-lg font-bold text-foreground">{item.guestLabel || "Mesa completa"}</p>
                    </div>
                  </div>

                  {item.modifiers.length ? (
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Notas / modificadores</p>
                      <p className="text-lg font-semibold text-foreground">{item.modifiers.join(", ")}</p>
                    </div>
                  ) : null}
                </div>

                <Button
                  className="mt-5 min-h-16 rounded-lg text-xl font-black"
                  size="lg"
                  disabled={item.status === "ready"}
                  onClick={() => void completeItem(item)}
                >
                  <CheckCircle2 className="mr-2 h-6 w-6" />
                  {item.status === "ready" ? "Terminado" : "Terminado"}
                </Button>
              </Card>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Utensils className="h-4 w-4" />
          <span>{filteredItems.length} productos visibles</span>
        </div>
      </div>
    </PageLayout>
  );
};

export default Kitchen;
