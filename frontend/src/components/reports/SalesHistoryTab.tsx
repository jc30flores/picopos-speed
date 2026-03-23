import { useEffect, useMemo, useState } from "react";
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
import { CalendarIcon, Search, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  createRefund,
  createRefundPrintJob,
  getPrintJob,
  getSalesReport,
  markPrintJobPrinted,
  voidOrder,
  PaymentMethod,
  PrintJob,
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
import { PrintPreviewDialog } from "@/components/printing/PrintPreviewDialog";
import { toast } from "sonner";
import { useServiceTypes } from "@/hooks/useServiceTypes";
import { formatDateSV, formatDateTimeSV, getLocalDateSV } from "@/lib/datetime";

type TimeRange = "daily" | "weekly" | "monthly" | "all";
type ServiceTypeFilter = "all" | string;
type PaymentMethodFilter = "all" | "efectivo" | "tarjeta" | "transferencia";

interface Sale {
  id: string;
  date: Date;
  orderNumber: string;
  serviceType: string;
  channel: string;
  paymentMethod: string;
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
  const [timeRange, setTimeRange] = useState<TimeRange>("daily");
  const [startDate, setStartDate] = useState<Date>(new Date());
  const [endDate, setEndDate] = useState<Date>(new Date());
  const [serviceType, setServiceType] = useState<ServiceTypeFilter>("all");
  const { serviceTypes } = useServiceTypes();
  const serviceTypeLabelByKey = useMemo(() => new Map(serviceTypes.map((item) => [item.key, item.label])), [serviceTypes]);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethodFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sales, setSales] = useState<Sale[]>([]);
  const [isRefundOpen, setIsRefundOpen] = useState(false);
  const [isVoidOpen, setIsVoidOpen] = useState(false);
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const [refundAmount, setRefundAmount] = useState("");
  const [refundTip, setRefundTip] = useState("");
  const [refundMethod, setRefundMethod] = useState<PaymentMethod>("cash");
  const [refundReason, setRefundReason] = useState("");
  const [voidReason, setVoidReason] = useState("");
  const [isSubmittingRefund, setIsSubmittingRefund] = useState(false);
  const [isSubmittingVoid, setIsSubmittingVoid] = useState(false);
  const [printJob, setPrintJob] = useState<PrintJob | null>(null);
  const [refundIdForReprint, setRefundIdForReprint] = useState<number | null>(null);
  const [isPrintPreviewOpen, setIsPrintPreviewOpen] = useState(false);

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

  const loadSales = () => {
    const serviceTypeFilter = serviceType === "all" ? undefined : serviceType;
    return getSalesReport({
      dateFrom,
      dateTo,
      serviceType: serviceTypeFilter as SalesReportRow["serviceType"] | undefined,
    })
      .then((report) => {
        const mapped = report.rows.map((row) => ({
          id: String(row.orderId),
          date: row.createdAt,
          orderNumber: `ORD-${row.orderNumber}`,
          serviceType: serviceTypeLabelByKey.get(row.serviceType ?? "") ?? row.serviceType ?? "-",
          channel: "POS",
          paymentMethod: "N/A",
          items: 0,
          subtotal: row.subtotal,
          tax: row.tax,
          total: row.total,
          cashier: "Auto",
          status: mapStatus(row.status, row.financialStatus),
          financialStatus: row.financialStatus,
          refundTotal: row.refundTotal,
          netPaid: row.netPaid,
        }));
        setSales(mapped);
      })
      .catch((error) => {
        console.error("Failed to load sales history", error);
      });
  };

  useEffect(() => {
    loadSales();
  }, [dateFrom, dateTo, serviceType]);

  const filteredSales = sales.filter((sale) => {
    const matchesSearch =
      sale.orderNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sale.cashier.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesService =
      serviceType === "all" ||
      sale.serviceType.toLowerCase().replace(" ", "-") === serviceType;
    const matchesPayment =
      paymentMethod === "all" ||
      sale.paymentMethod.toLowerCase() === paymentMethod;
    return matchesSearch && matchesService && matchesPayment;
  });

  const totalSales = filteredSales.reduce((sum, sale) => sum + sale.total, 0);

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
    setRefundAmount(sale.netPaid.toFixed(2));
    setRefundTip("0");
    setRefundMethod("cash");
    setRefundReason("");
    setIsRefundOpen(true);
  };

  const openVoidDialog = (sale: Sale) => {
    setSelectedSale(sale);
    setVoidReason("");
    setIsVoidOpen(true);
  };

  const handleRefundSubmit = async () => {
    if (!selectedSale) return;
    const amountValue = Number(refundAmount);
    const tipValue = Number(refundTip);

    if (!amountValue || amountValue <= 0) {
      toast.error("Ingresa un monto válido");
      return;
    }
    if (tipValue < 0) {
      toast.error("La propina no puede ser negativa");
      return;
    }
    if (!refundReason.trim()) {
      toast.error("Ingresa un motivo");
      return;
    }

    try {
      setIsSubmittingRefund(true);
      const response = await createRefund({
        orderId: Number(selectedSale.id),
        method: refundMethod,
        amount: amountValue,
        tipRefunded: tipValue,
        reason: refundReason,
      });
      setPrintJob(response.printJob);
      setRefundIdForReprint(response.refund.id);
      setIsPrintPreviewOpen(true);
      setIsRefundOpen(false);
      toast.success("Reembolso registrado");
      await loadSales();
    } catch (error) {
      console.error("Failed to create refund", error);
      toast.error("No se pudo registrar el reembolso");
    } finally {
      setIsSubmittingRefund(false);
    }
  };

  const handleVoidSubmit = async () => {
    if (!selectedSale) return;
    if (!voidReason.trim()) {
      toast.error("Ingresa un motivo");
      return;
    }
    try {
      setIsSubmittingVoid(true);
      const response = await voidOrder(Number(selectedSale.id), voidReason);
      const job = await getPrintJob(response.printJobId);
      setPrintJob(job);
      setRefundIdForReprint(null);
      setIsPrintPreviewOpen(true);
      setIsVoidOpen(false);
      toast.success("Orden anulada");
      await loadSales();
    } catch (error) {
      console.error("Failed to void order", error);
      toast.error("No se pudo anular la orden");
    } finally {
      setIsSubmittingVoid(false);
    }
  };

  const handleMarkPrinted = async () => {
    if (!printJob) return;
    try {
      const job = await markPrintJobPrinted(printJob.id);
      setPrintJob(job);
      toast.success("Ticket marcado como impreso");
    } catch (error) {
      console.error("Failed to mark printed", error);
      toast.error("No se pudo actualizar el ticket");
    }
  };

  const handleReprint = async () => {
    if (!printJob) return;
    try {
      if (refundIdForReprint) {
        const job = await createRefundPrintJob(refundIdForReprint);
        setPrintJob(job);
      } else {
        const job = await getPrintJob(printJob.id);
        setPrintJob(job);
      }
      toast.success("Ticket listo para reimpresión");
    } catch (error) {
      console.error("Failed to reprint ticket", error);
      toast.error("No se pudo reimprimir el ticket");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">Historial de Ventas</h1>
        <p className="text-sm text-muted-foreground">
          Consulta y analiza todas las ventas realizadas en el restaurante.
        </p>
      </div>

      {/* Filters Section */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          {/* Time Range Filters */}
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
                  className="rounded-full"
                >
                  {range.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Date Range Pickers */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Start Date */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Desde
              </label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
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
            </div>

            {/* End Date */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Hasta
              </label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
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
            </div>

            {/* Service Type Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Tipo de servicio
              </label>
              <Select
                value={serviceType}
                onValueChange={(value) => setServiceType(value as ServiceTypeFilter)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {serviceTypes.map((item) => (
                    <SelectItem key={item.id} value={item.key}>{item.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Payment Method Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Método de pago
              </label>
              <Select
                value={paymentMethod}
                onValueChange={(value) =>
                  setPaymentMethod(value as PaymentMethodFilter)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="efectivo">Efectivo</SelectItem>
                  <SelectItem value="tarjeta">Tarjeta</SelectItem>
                  <SelectItem value="transferencia">Transferencia</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Search */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Buscar
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Nº pedido o cajero..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
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
            <p className="text-sm text-muted-foreground mt-1">
              Total de ventas: <span className="font-semibold text-foreground">${totalSales.toFixed(2)}</span> · {filteredSales.length} transacciones
            </p>
          </div>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha y hora</TableHead>
                  <TableHead>Nº de pedido</TableHead>
                  <TableHead>Tipo de servicio</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead>Método de pago</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead className="text-right">Subtotal</TableHead>
                  <TableHead className="text-right">Impuesto</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Cajero</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSales.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={12}
                      className="text-center text-muted-foreground py-8"
                    >
                      No se encontraron ventas
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSales.map((sale) => (
                    <TableRow key={sale.id}>
                      <TableCell className="font-medium">
                        {formatDateTimeSV(sale.date)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {sale.orderNumber}
                      </TableCell>
                      <TableCell>{sale.serviceType}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{sale.channel}</Badge>
                      </TableCell>
                      <TableCell>{sale.paymentMethod}</TableCell>
                      <TableCell>{sale.items}</TableCell>
                      <TableCell className="text-right">
                        ${sale.subtotal.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right">
                        ${sale.tax.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-semibold">
                        ${sale.total.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {sale.cashier}
                      </TableCell>
                      <TableCell>{getStatusBadge(sale.status)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openRefundDialog(sale)}
                            disabled={sale.financialStatus === "voided" || sale.netPaid <= 0}
                          >
                            Reembolsar
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openVoidDialog(sale)}
                            disabled={sale.financialStatus === "voided" || sale.netPaid > 0}
                          >
                            Anular
                          </Button>
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
            <DialogTitle>Registrar reembolso</DialogTitle>
            <DialogDescription>Procesa una devolución parcial o total.</DialogDescription>
          </DialogHeader>
          {selectedSale ? (
            <div className="space-y-4">
              <div className="rounded-md border p-3 text-sm space-y-1">
                <div className="flex justify-between">
                  <span>Pedido</span>
                  <span>{selectedSale.orderNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pagado neto</span>
                  <span>${selectedSale.netPaid.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Reembolsado</span>
                  <span>${selectedSale.refundTotal.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Método</Label>
                <Select value={refundMethod} onValueChange={(value: PaymentMethod) => setRefundMethod(value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cash">Efectivo</SelectItem>
                    <SelectItem value="card">Tarjeta</SelectItem>
                    <SelectItem value="transfer">Transferencia</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Monto</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={refundAmount}
                    onChange={(event) => setRefundAmount(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Propina</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={refundTip}
                    onChange={(event) => setRefundTip(event.target.value)}
                  />
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

      <Dialog open={isVoidOpen} onOpenChange={setIsVoidOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Anular pedido</DialogTitle>
            <DialogDescription>Esta acción cancela un pedido sin pagos.</DialogDescription>
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
                <Input value={voidReason} onChange={(event) => setVoidReason(event.target.value)} />
              </div>

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setIsVoidOpen(false)}>
                  Cancelar
                </Button>
                <Button className="flex-1" onClick={handleVoidSubmit} disabled={isSubmittingVoid}>
                  {isSubmittingVoid ? "Procesando..." : "Confirmar"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No hay orden seleccionada.</div>
          )}
        </DialogContent>
      </Dialog>

      <PrintPreviewDialog
        open={isPrintPreviewOpen}
        onOpenChange={setIsPrintPreviewOpen}
        job={printJob}
        onMarkPrinted={handleMarkPrinted}
        onReprint={handleReprint}
      />
    </div>
  );
};
