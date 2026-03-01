import { useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCustomerOrders } from "@/lib/api";

const CustomerDisplay = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Array<{ id: number; orderNumber: number; status: string; customerName?: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [retryToken, setRetryToken] = useState(0);
  const pollDelayRef = useRef(5000);

  useEffect(() => {
    let timeoutId: number | undefined;
    let isUnmounted = false;
    let currentController: AbortController | null = null;

    const loadOrders = async () => {
      currentController?.abort();
      currentController = new AbortController();
      setIsLoading(true);
      try {
        const data = await getCustomerOrders(currentController.signal);
        if (isUnmounted) return;
        setOrders(data);
        setError(null);
        pollDelayRef.current = 5000;
      } catch (loadError) {
        if (isUnmounted) return;
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        const message =
          loadError instanceof Error ? loadError.message : "No se pudo cargar pedidos de clientes.";
        setError(message);
        pollDelayRef.current = Math.min(pollDelayRef.current * 2, 10000);
      } finally {
        if (!isUnmounted) {
          setIsLoading(false);
          timeoutId = window.setTimeout(loadOrders, pollDelayRef.current);
        }
      }
    };

    void loadOrders();

    return () => {
      isUnmounted = true;
      currentController?.abort();
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [retryToken]);

  const handleRetry = () => {
    pollDelayRef.current = 2000;
    setRetryToken((prev) => prev + 1);
  };

  const preparingOrders = orders.filter((o) => o.status === "preparing");
  const readyOrders = orders.filter((o) => o.status === "ready");

  return (
    <div className="min-h-screen bg-primary text-primary-foreground p-8 relative">
      {/* Back Button - Almost invisible */}
      <button
        onClick={() => navigate(-1)}
        className="fixed top-4 left-4 p-2 text-primary-foreground/20 hover:text-primary-foreground/40 transition-colors z-50"
        aria-label="Volver"
      >
        <ArrowLeft className="h-6 w-6" />
      </button>

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-16 h-16 bg-gradient-accent rounded-2xl flex items-center justify-center shadow-xl">
              <span className="text-4xl">🌶️</span>
            </div>
            <h1 className="text-5xl font-bold">Pico de Gallo</h1>
          </div>
          <p className="text-xl text-primary-foreground/80">Estado de Pedidos</p>
        </div>

        {error && (
          <div className="mb-8 rounded-2xl border border-warning/60 bg-warning/20 p-4 text-warning">
            <div className="flex flex-col items-center gap-2 text-center">
              <p className="text-lg font-semibold">Pantalla de clientes no sincronizada</p>
              <p className="text-sm text-warning/90">{error}</p>
              <button
                type="button"
                onClick={handleRetry}
                className="rounded-full border border-warning px-4 py-1 text-sm font-semibold text-warning hover:bg-warning/10"
              >
                Reintentar
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Preparing */}
          <div className="space-y-6">
            <div className="text-center">
              <div className="inline-flex items-center gap-2 px-6 py-3 bg-warning/20 rounded-full border-2 border-warning">
                <div className="w-3 h-3 bg-warning rounded-full animate-pulse" />
                <h2 className="text-2xl font-bold text-warning">En Preparación</h2>
              </div>
            </div>

            <div className="space-y-4">
              {isLoading && preparingOrders.length === 0 ? (
                <div className="text-center py-12 text-primary-foreground/50">
                  <p className="text-lg">Cargando pedidos...</p>
                </div>
              ) : preparingOrders.length === 0 ? (
                <div className="text-center py-12 text-primary-foreground/50">
                  <p className="text-lg">No hay pedidos en preparación</p>
                </div>
              ) : (
                preparingOrders.map((order) => (
                  <div
                    key={order.id}
                    className="bg-primary-light/50 backdrop-blur-sm rounded-2xl p-6 border border-primary-foreground/10 animate-fade-in"
                  >
                    <div className="text-center">
                      <div className="text-7xl font-black mb-2">#{order.orderNumber}</div>
                      {order.customerName && (
                        <p className="text-2xl font-semibold">{order.customerName}</p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Ready */}
          <div className="space-y-6">
            <div className="text-center">
              <div className="inline-flex items-center gap-2 px-6 py-3 bg-success/20 rounded-full border-2 border-success">
                <div className="w-3 h-3 bg-success rounded-full animate-pulse" />
                <h2 className="text-2xl font-bold text-success">Listo para Recoger</h2>
              </div>
            </div>

            <div className="space-y-4">
              {isLoading && readyOrders.length === 0 ? (
                <div className="text-center py-12 text-primary-foreground/50">
                  <p className="text-lg">Cargando pedidos...</p>
                </div>
              ) : readyOrders.length === 0 ? (
                <div className="text-center py-12 text-primary-foreground/50">
                  <p className="text-lg">No hay pedidos listos</p>
                </div>
              ) : (
                readyOrders.map((order) => (
                  <div
                    key={order.id}
                    className={cn(
                      "bg-gradient-accent rounded-2xl p-6 shadow-2xl animate-fade-in",
                      "border-2 border-success"
                    )}
                  >
                    <div className="text-center">
                      <div className="text-7xl font-black mb-2 text-primary">
                        #{order.orderNumber}
                      </div>
                      {order.customerName && (
                        <p className="text-2xl font-semibold text-primary">
                          {order.customerName}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-primary-foreground/60">
          <p className="text-lg">Gracias por tu preferencia</p>
        </div>
      </div>
    </div>
  );
};

export default CustomerDisplay;
