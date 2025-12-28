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
import { CalendarIcon, Search, Download, Eye } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { getSalesReport, SalesReportRow } from "@/lib/api";

type TimeRange = "daily" | "weekly" | "monthly" | "all";
type ServiceType = "all" | "en-local" | "para-llevar" | "delivery" | "kiosk";
type PaymentMethod = "all" | "efectivo" | "tarjeta" | "transferencia";

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
}

const SERVICE_TYPE_LABELS: Record<string, string> = {
  "dine-in": "En local",
  takeout: "Para llevar",
  delivery: "Delivery",
  kiosk: "Kiosk",
};

const mapStatus = (status: SalesReportRow["status"]): Sale["status"] => {
  if (status === "canceled") return "anulado";
  return "completado";
};

export const SalesHistoryTab = () => {
  const [timeRange, setTimeRange] = useState<TimeRange>("daily");
  const [startDate, setStartDate] = useState<Date>(new Date());
  const [endDate, setEndDate] = useState<Date>(new Date());
  const [serviceType, setServiceType] = useState<ServiceType>("all");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sales, setSales] = useState<Sale[]>([]);

  const dateFrom = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
  const dateTo = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

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
    const serviceTypeFilter =
      serviceType === "all"
        ? undefined
        : serviceType === "en-local"
          ? "dine-in"
          : serviceType === "para-llevar"
            ? "takeout"
            : serviceType;
    getSalesReport({
      dateFrom,
      dateTo,
      serviceType: serviceTypeFilter as SalesReportRow["serviceType"] | undefined,
    })
      .then((data) => {
        const mapped = data.map((row) => ({
          id: String(row.orderId),
          date: row.createdAt,
          orderNumber: `ORD-${row.orderNumber}`,
          serviceType: SERVICE_TYPE_LABELS[row.serviceType] || row.serviceType,
          channel: "POS",
          paymentMethod: "N/A",
          items: 0,
          subtotal: row.subtotal,
          tax: row.tax,
          total: row.total,
          cashier: "Auto",
          status: mapStatus(row.status),
        }));
        setSales(mapped);
      })
      .catch((error) => {
        console.error("Failed to load sales history", error);
      });
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
    const variants = {
      completado: "default",
      anulado: "destructive",
      reembolsado: "secondary",
    };
    return (
      <Badge variant={variants[status] as any}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
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
                      {startDate ? format(startDate, "dd/MM/yyyy") : "Fecha inicio"}
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
                      {endDate ? format(endDate, "dd/MM/yyyy") : "Fecha fin"}
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
                onValueChange={(value) => setServiceType(value as ServiceType)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="en-local">En local</SelectItem>
                  <SelectItem value="kiosk">Kiosk</SelectItem>
                  <SelectItem value="para-llevar">Para llevar</SelectItem>
                  <SelectItem value="delivery">Delivery</SelectItem>
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
                  setPaymentMethod(value as PaymentMethod)
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
                  <TableHead></TableHead>
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
                        {format(sale.date, "dd/MM/yyyy HH:mm")}
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
                        <Button variant="ghost" size="sm">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
