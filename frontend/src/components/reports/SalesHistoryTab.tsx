import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CalendarIcon, Search, Download, X, RotateCcw, Send, Repeat2, Eye, Printer } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  changeInternalPaymentMethod,
  dteDeliverByOrder,
  getDteSettings,
  refundSaleRecord,
  getPaymentMethods,
  getSalesReport,
  getTransactionTicket,
  PaymentMethodOption,
  SalesReportRow,
} from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useServiceTypes } from "@/hooks/useServiceTypes";
import { formatDateSV, formatDateTimeSV, getLocalDateSV } from "@/lib/datetime";
import { useAuth } from "@/context/useAuth";
import { fromCents, toCents } from "@/lib/money";
import { smartPrintTicket } from "@/lib/ticketPrinting";

type TimeRange = "daily" | "weekly" | "monthly" | "all";
type ServiceTypeFilter = "all" | string;
type PaymentMethodFilter = "all" | "cash" | "card" | "transfer" | "pedidos_ya" | "paypal";

interface Sale {
  rowKey: string;
  orderId: number;
  paymentId: number;
  date: Date;
  orderNumber: string;
  controlNumber: string;
  customerName: string;
  serviceType: string;
  channel: string;
  paymentMethod: string;
  paymentMethodCode: string;
  items: number;
  subtotal: number;
  tax: number;
  total: number;
  cashier: string;
  status: "completado" | "anulado" | "reembolsado";
  financialStatus: SalesReportRow["financialStatus"];
  refundTotal: number;
  netPaid: number;
}

const mapStatus = (
  status: SalesReportRow["status"],
  financialStatus: SalesReportRow["financialStatus"]
): Sale["status"] => {
  if (financialStatus === "voided" || status === "canceled") return "anulado";
  if (financialStatus === "refunded_partial" || financialStatus === "refunded_full") {
    return "reembolsado";
  }
  return "completado";
};

export const SalesHistoryTab = () => {
  const { user } = useAuth();
  const restrictedRole = user?.role === "cashier";
  const [timeRange, setTimeRange] = useState<TimeRange>("daily");
  const [startDate, setStartDate] = useState<Date>(new Date());
  const [endDate, setEndDate] = useState<Date>(new Date());
  const [serviceType, setServiceType] = useState<ServiceTypeFilter>("all");
  const { serviceTypes } = useServiceTypes();
  const serviceTypeLabelByKey = useMemo(() => new Map(serviceTypes.map((item) => [item.key, item.label])), [serviceTypes]);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethodFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [sales, setSales] = useState<Sale[]>([]);
  const requestSequence = useRef(0);
  const [isRefundOpen, setIsRefundOpen] = useState(false);
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const [refundReason, setRefundReason] = useState("");
  const [isSubmittingRefund, setIsSubmittingRefund] = useState(false);
  const [isMethodChangeOpen, setIsMethodChangeOpen] = useState(false);
  const [paymentMethodOptions, setPaymentMethodOptions] = useState<PaymentMethodOption[]>([]);
  const [selectedMethodCode, setSelectedMethodCode] = useState("");
  const [methodChangeReason, setMethodChangeReason] = useState("");
  const [isChangingMethod, setIsChangingMethod] = useState(false);
  const [sendingByOrderId, setSendingByOrderId] = useState<number | null>(null);
  const [printingByPaymentId, setPrintingByPaymentId] = useState<number | null>(null);
  const [isTicketOpen, setIsTicketOpen] = useState(false);
  const [ticketLoading, setTicketLoading] = useState(false);
  const [ticketError, setTicketError] = useState<string | null>(null);
  const [ticketHtml, setTicketHtml] = useState("");
  const canChangePaymentMethod = user?.role === "admin" || Boolean(user?.isSuperuser);
  const [dteEnabled, setDteEnabled] = useState(false);

  const dateFrom = startDate ? getLocalDateSV(startDate) : undefined;
  const dateTo = endDate ? getLocalDateSV(endDate) : undefined;

  useEffect(() => {
    const now = new Date();
    if (timeRange === "daily") {
      setStartDate(now);
      setEndDate(now);
    }
    if (timeRange === "weekly") {
      const start = new Date(now);
      start.setDate(now.getDate() - 7);
      setStartDate(start);
      setEndDate(now);
    }
    if (timeRange === "monthly") {
      const start = new Date(now);
      start.setDate(now.getDate() - 30);
      setStartDate(start);
      setEndDate(now);
    }
  }, [timeRange]);

  useEffect(() => {
    const normalized = searchQuery.trim();
    if (!normalized) {
      setDebouncedSearchQuery("");
      return;
    }
    const timer = window.setTimeout(() => {
      setDebouncedSearchQuery(normalized);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const loadSales = (currentSearch: string) => {
    const currentRequest = ++requestSequence.current;
    const serviceTypeFilter = serviceType === "all" ? undefined : serviceType;
    const todayLocal = getLocalDateSV(new Date());
    const useGlobalSearch = currentSearch.length > 0;
    return getSalesReport({
      dateFrom: restrictedRole && !useGlobalSearch ? todayLocal : dateFrom,
      dateTo: restrictedRole && !useGlobalSearch ? todayLocal : dateTo,
      serviceType: serviceTypeFilter as SalesReportRow["serviceType"] | undefined,
      paymentMethod: paymentMethod === "all" ? undefined : paymentMethod,
      today: undefined,
      search: useGlobalSearch ? currentSearch : undefined,
    })
      .then((report) => {
        if (currentRequest !== requestSequence.current) return;
        const mapped = report.rows.map((row) => ({
          rowKey: `${row.paymentId}-${row.orderId}`,
          orderId: row.orderId,
          paymentId: row.paymentId,
          date: row.createdAt,
          orderNumber: `ORD-${row.orderNumber}`,
          controlNumber: row.controlNumber || "—",
          customerName: row.customerName || "-",
          serviceType: row.serviceTypeLabel ?? serviceTypeLabelByKey.get(row.serviceType ?? "") ?? row.serviceType ?? "-",
          channel: "POS",
          paymentMethod: row.paymentMethodLabel || "-",
          paymentMethodCode: row.paymentMethodCode || "",
          items: 0,
          subtotal: 0,
          tax: 0,
          total: row.total,
          cashier: "Auto",
          status: mapStatus(row.status, row.financialStatus),
          financialStatus: row.financialStatus,
          refundTotal: 0,
          netPaid: row.total,
        }));
        const uniqueByKey = new Map<string, (typeof mapped)[number]>();
        mapped.forEach((item) => {
          if (!uniqueByKey.has(item.rowKey)) uniqueByKey.set(item.rowKey, item);
        });
        setSales(Array.from(uniqueByKey.values()));
      })
      .catch((error) => {
        console.error("Failed to load sales history", error);
      });
  };

  useEffect(() => {
    void loadSales(debouncedSearchQuery);
  }, [dateFrom, dateTo, serviceType, paymentMethod, debouncedSearchQuery, restrictedRole]);

  useEffect(() => {
    if (!canChangePaymentMethod) return;
    getPaymentMethods()
      .then(setPaymentMethodOptions)
      .catch((error) => console.error("Failed to load payment methods", error));
  }, [canChangePaymentMethod]);

  useEffect(() => {
    getDteSettings()
      .then((value) => setDteEnabled(value.haciendaEnabled))
      .catch(() => setDteEnabled(false));
  }, []);

  const filteredSales = sales;

  const totalSales = fromCents(filteredSales.reduce((sum, sale) => sum + toCents(sale.total), 0));

  const getStatusBadge = (status: Sale["status"]) => {
    const variants: Record<Sale["status"], "default" | "destructive" | "secondary"> = {
      completado: "default",
      anulado: "destructive",
      reembolsado: "secondary",
    };
    return (
      <Badge variant={variants[status]}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const openRefundDialog = (sale: Sale) => {
    setSelectedSale(sale);
    setRefundReason("");
    setIsRefundOpen(true);
  };

  const openMethodChangeDialog = (sale: Sale) => {
    setSelectedSale(sale);
    setSelectedMethodCode(sale.paymentMethodCode || "");
    setMethodChangeReason("");
    setIsMethodChangeOpen(true);
  };

  const handlePaymentMethodChange = async () => {
    if (!selectedSale) return;
    if (!selectedMethodCode) {
      toast.error("Selecciona un método de pago");
      return;
    }
    const selectedMethod = paymentMethodOptions.find((method) => method.code === selectedMethodCode);
    const currentCode = String(selectedSale.paymentMethodCode || "").trim().toLowerCase();
    const nextCode = String(selectedMethodCode || "").trim().toLowerCase();
    if (currentCode && nextCode && currentCode === nextCode) {
      toast.message("El método de pago ya está aplicado.");
      return;
    }
    console.info("sales.payment_method_change.payload", {
      paymentId: selectedSale.paymentId,
      selectedMethodCode: selectedMethodCode || null,
      selectedMethodId: selectedMethod?.id ?? null,
      selectedMethodName: selectedMethod?.name ?? null,
    });
    try {
      setIsChangingMethod(true);
      await changeInternalPaymentMethod(selectedSale.paymentId, {
        paymentMethodCode: selectedMethodCode || undefined,
        paymentMethodId: selectedMethod?.id,
        reason: methodChangeReason.trim(),
      });
      toast.success("Método de pago actualizado.");
      setIsMethodChangeOpen(false);
      await loadSales(debouncedSearchQuery);
    } catch (error) {
      console.error("Failed to update payment method", error);
      const fallback = "No se pudo cambiar el método de pago. Verifica que el método esté activo.";
      toast.error(error instanceof Error && error.message ? error.message : fallback);
    } finally {
      setIsChangingMethod(false);
    }
  };

  const handleRefundSubmit = async () => {
    if (!selectedSale) return;
    if (!refundReason.trim()) {
      toast.error("Ingresa un motivo");
      return;
    }

    try {
      setIsSubmittingRefund(true);
      const result = await refundSaleRecord(selectedSale.paymentId, { reason: refundReason });
      setIsRefundOpen(false);
      if (result.action === "internal_refund") {
        const detail = result.fiscalResult?.message ? ` ${result.fiscalResult.message}` : "";
        toast.warning((result.message || "Reembolso interno registrado.") + detail);
      } else if (result.action === "credit_note") {
        toast.success("Reembolso registrado con nota de crédito.");
      } else {
        toast.success("Reembolso registrado con invalidación DTE.");
      }
      await loadSales(debouncedSearchQuery);
    } catch (error) {
      console.error("Failed to create refund", error);
      toast.error(error instanceof Error ? error.message : "No se pudo registrar el reembolso");
    } finally {
      setIsSubmittingRefund(false);
    }
  };

  const handleSendDteToCustomer = async (sale: Sale) => {
    setSendingByOrderId(sale.orderId);
    try {
      const result = await dteDeliverByOrder(sale.orderId, ["whatsapp", "email"]);
      const wa = result.results?.whatsapp;
      const email = result.results?.email;
      if (result.success) {
        toast.success("DTE enviado por correo y WhatsApp.");
      } else {
        toast.error(`WhatsApp: ${wa?.error || "OK"} | Correo: ${email?.error || "OK"}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo enviar DTE");
    } finally {
      setSendingByOrderId(null);
    }
  };


  const handlePrintTicket = async (sale: Sale) => {
    if (printingByPaymentId === sale.paymentId) return;
    setPrintingByPaymentId(sale.paymentId);
    try {
      const result = await smartPrintTicket({ paymentId: sale.paymentId });
      if (result.method === "direct") toast.success("Ticket enviado a impresora.");
    } catch (error) {
      console.error("Failed to print transaction ticket", error);
      toast.error(error instanceof Error ? error.message : "No se pudo imprimir el ticket. Intenta nuevamente.");
    } finally {
      setPrintingByPaymentId(null);
    }
  };

  const openTicketDialog = async (sale: Sale) => {
    setIsTicketOpen(true);
    setTicketLoading(true);
    setTicketError(null);
    setTicketHtml("");
    try {
      const payload = await getTransactionTicket(sale.paymentId);
      setTicketHtml(payload.ticketHtml || `<pre class='whitespace-pre-wrap'>${payload.ticketText}</pre>`);
    } catch (error) {
      setTicketError(error instanceof Error ? error.message : "No se pudo cargar el ticket.");
    } finally {
      setTicketLoading(false);
    }
  };


  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">Historial de Transacciones</h1>
        <p className="text-sm text-muted-foreground">
          Consulta y analiza todas las transacciones realizadas en el restaurante.
        </p>
      </div>

      {/* Filters Section */}
      <Card>
        <CardContent className="space-y-4 pt-6 md:pt-7">
          {!restrictedRole ? (
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Período de tiempo
              </label>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: "daily", label: "Diario" },
                  { value: "weekly", label: "Semanal" },
                  { value: "monthly", label: "Mensual" },
                  { value: "all", label: "Todos" },
                ].map((range) => (
                  <Button
                    key={range.value}
                    variant={timeRange === range.value ? "default" : "outline"}
                    onClick={() => setTimeRange(range.value as TimeRange)}
                    className="h-12 rounded-full px-5 text-base"
                  >
                    {range.label}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Filtro activo: <strong>Hoy</strong>.</p>
          )}

          {/* Date Range Pickers */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {!restrictedRole ? <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Desde
              </label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "h-12 w-full justify-start text-left text-base font-normal",
                      !startDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
                    <span className="truncate">
                      {startDate ? formatDateSV(startDate) : "Fecha inicio"}
                    </span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={startDate}
                    onSelect={(newDate) => newDate && setStartDate(newDate)}
                    initialFocus
                    className="pointer-events-auto"
                  />
                </PopoverContent>
              </Popover>
            </div> : null}

            {/* End Date */}
            {!restrictedRole ? <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Hasta
              </label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "h-12 w-full justify-start text-left text-base font-normal",
                      !endDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
                    <span className="truncate">
                      {endDate ? formatDateSV(endDate) : "Fecha fin"}
                    </span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={endDate}
                    onSelect={(newDate) => newDate && setEndDate(newDate)}
                    initialFocus
                    className="pointer-events-auto"
                  />
                </PopoverContent>
              </Popover>
            </div> : null}

            {/* Service Type Filter */}
            {!restrictedRole ? <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Tipo de servicio
              </label>
              <Select
                value={serviceType}
                onValueChange={(value) => setServiceType(value as ServiceTypeFilter)}
              >
                <SelectTrigger className="h-12 text-base">
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {serviceTypes.map((item) => (
                    <SelectItem key={item.id} value={item.key}>{item.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div> : null}

            {/* Payment Method Filter */}
            {!restrictedRole ? <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Método de pago
              </label>
              <Select
                value={paymentMethod}
                onValueChange={(value) =>
                  setPaymentMethod(value as PaymentMethodFilter)
                }
              >
                <SelectTrigger className="h-12 text-base">
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="cash">Efectivo</SelectItem>
                  <SelectItem value="card">Tarjeta</SelectItem>
                  <SelectItem value="transfer">Transferencia</SelectItem>
                  <SelectItem value="pedidos_ya">Pedidos Ya</SelectItem>
                  <SelectItem value="paypal">PayPal</SelectItem>
                </SelectContent>
              </Select>
            </div> : null}

            {/* Search */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Buscar
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar por Nº pedido, No. control o cliente…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-12 pl-10 pr-10 text-base"
                />
                {searchQuery ? (
                  <button
                    type="button"
                    aria-label="Limpiar búsqueda"
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted"
                    onClick={() => setSearchQuery("")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sales Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Transacciones</CardTitle>
            {!restrictedRole ? (
              <p className="text-sm text-muted-foreground mt-1">
                Total de ventas: <span className="font-semibold text-foreground">${totalSales.toFixed(2)}</span> · {filteredSales.length} transacciones
              </p>
            ) : null}
          </div>
          <Button variant="outline" className="min-h-12 rounded-xl px-5 md:min-h-14 md:text-base">
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </CardHeader>
        <CardContent>
          <div className="max-h-[70vh] overflow-auto rounded-xl border">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-background">
                <TableRow>
                  <TableHead>Fecha y hora</TableHead>
                  <TableHead>Nº de pedido</TableHead>
                  <TableHead>No. de control</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Tipo de servicio</TableHead>
                  <TableHead>Método de pago</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSales.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={9}
                      className="text-center text-muted-foreground py-8"
                    >
                      No se encontraron transacciones
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSales.map((sale) => (
                    <TableRow key={sale.rowKey} className="h-14 hover:bg-muted/40">
                      <TableCell className="font-medium">
                        {formatDateTimeSV(sale.date)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {sale.orderNumber}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {sale.controlNumber}
                      </TableCell>
                      <TableCell>{sale.customerName}</TableCell>
                      <TableCell>{sale.serviceType}</TableCell>
                      <TableCell>{sale.paymentMethod}</TableCell>
                      <TableCell className="text-right font-semibold">
                        ${sale.total.toFixed(2)}
                      </TableCell>
                      <TableCell>{getStatusBadge(sale.status)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-9 w-9 rounded-lg p-0"
                            title="Imprimir ticket"
                            aria-label="Imprimir ticket"
                            onClick={() => void handlePrintTicket(sale)}
                            disabled={printingByPaymentId === sale.paymentId}
                          >
                            <Printer className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-9 w-9 rounded-lg p-0"
                            title="Ver ticket"
                            aria-label="Ver ticket"
                            onClick={() => void openTicketDialog(sale)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-9 w-9 rounded-lg p-0"
                            title="Reembolsar"
                            aria-label="Reembolsar"
                            onClick={() => openRefundDialog(sale)}
                            disabled={sale.financialStatus === "voided" || sale.netPaid <= 0}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                          {canChangePaymentMethod ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-9 w-9 rounded-lg p-0"
                              title="Cambiar método"
                              aria-label="Cambiar método"
                              onClick={() => openMethodChangeDialog(sale)}
                              disabled={sale.financialStatus === "voided" || sale.status === "reembolsado"}
                            >
                              <Repeat2 className="h-4 w-4" />
                            </Button>
                          ) : null}
                          {dteEnabled ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-9 rounded-lg px-3"
                              title="Enviar DTE a Cliente"
                              aria-label="Enviar DTE a Cliente"
                              onClick={() => void handleSendDteToCustomer(sale)}
                              disabled={sendingByOrderId === sale.orderId}
                            >
                              <Send className="mr-2 h-4 w-4" />
                              {sendingByOrderId === sale.orderId ? "Enviando..." : "Enviar DTE a Cliente"}
                            </Button>
                          ) : null}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={isRefundOpen} onOpenChange={setIsRefundOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reembolsar venta</DialogTitle>
            <DialogDescription>
              {dteEnabled
                ? "Si hay DTE aceptado, se invalidará o se generará NC según reglas fiscales. Si no hay DTE aceptado, se hará reembolso interno."
                : "Facturación electrónica está desactivada. El reembolso se registrará solo de forma interna."}
            </DialogDescription>
          </DialogHeader>
          {selectedSale ? (
            <div className="space-y-4">
              <div className="rounded-md border p-3 text-sm space-y-1">
                <div className="flex justify-between">
                  <span>Pedido</span>
                  <span>{selectedSale.orderNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total</span>
                  <span>${selectedSale.total.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Motivo</Label>
                <Input value={refundReason} onChange={(event) => setRefundReason(event.target.value)} />
              </div>

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setIsRefundOpen(false)}>
                  Cancelar
                </Button>
                <Button className="flex-1" onClick={handleRefundSubmit} disabled={isSubmittingRefund}>
                  {isSubmittingRefund ? "Procesando..." : "Confirmar"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No hay orden seleccionada.</div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={isTicketOpen} onOpenChange={setIsTicketOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Ticket de transacción</DialogTitle>
          </DialogHeader>
          {ticketLoading ? <p className="text-sm text-muted-foreground">Cargando ticket...</p> : null}
          {ticketError ? <p className="text-sm text-destructive">{ticketError}</p> : null}
          {!ticketLoading && !ticketError ? (
            <div className="max-h-[70vh] overflow-auto rounded-md border bg-white p-3 text-black" dangerouslySetInnerHTML={{ __html: ticketHtml }} />
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={isMethodChangeOpen} onOpenChange={setIsMethodChangeOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Cambiar método de pago</DialogTitle>
            <DialogDescription>
              Esto solo corrige registros internos y cierres de caja; NO cambia el DTE enviado a Hacienda.
            </DialogDescription>
          </DialogHeader>
          {selectedSale ? (
            <div className="space-y-4">
              <div className="rounded-md border p-3 text-sm space-y-1">
                <div className="flex justify-between">
                  <span>Pedido</span>
                  <span>{selectedSale.orderNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span>Método actual</span>
                  <span>{selectedSale.paymentMethod}</span>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Nuevo método</Label>
                <Select value={selectedMethodCode} onValueChange={setSelectedMethodCode}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar método" />
                  </SelectTrigger>
                  <SelectContent>
                    {paymentMethodOptions.filter((method) => method.isActive).map((method) => (
                      <SelectItem key={method.id} value={method.code}>
                        {method.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Motivo de cambio (opcional)</Label>
                <Input value={methodChangeReason} onChange={(event) => setMethodChangeReason(event.target.value)} maxLength={240} />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setIsMethodChangeOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  className="flex-1"
                  onClick={handlePaymentMethodChange}
                  disabled={
                    isChangingMethod ||
                    !selectedMethodCode ||
                    String(selectedMethodCode || "").trim().toLowerCase() === String(selectedSale.paymentMethodCode || "").trim().toLowerCase()
                  }
                >
                  {isChangingMethod ? "Guardando..." : "Confirmar"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No hay orden seleccionada.</div>
          )}
        </DialogContent>
      </Dialog>

    </div>
  );
};
