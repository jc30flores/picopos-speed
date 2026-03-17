import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  DollarSign,
  Receipt,
  Store,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSalesReport, SalesReportRow, SalesReportAggregates } from "@/lib/api";
import { useServiceTypes } from "@/hooks/useServiceTypes";

type TimeFilter = "daily" | "weekly" | "monthly" | "all";

export const ReportsTab = () => {
  const { serviceTypes } = useServiceTypes();
  const serviceTypeLabelByKey = useMemo(() => new Map(serviceTypes.map((item) => [item.key, item.label])), [serviceTypes]);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("daily");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [sales, setSales] = useState<SalesReportRow[]>([]);
  const [aggregates, setAggregates] = useState<SalesReportAggregates>({
    countOrders: 0,
    sumSubtotal: 0,
    sumTax: 0,
    sumTotal: 0,
    sumDiscountTotal: 0,
    grossTotal: 0,
    refundTotal: 0,
    netTotal: 0,
    paymentMethods: {
      cash: 0,
      card: 0,
      transfer: 0,
    },
    tipsTotal: 0,
    tipsNet: 0,
    cashTotal: 0,
    nonCashTotal: 0,
    refundsCount: 0,
    ordersPaid: 0,
    ordersVoided: 0,
    refundsByMethod: {
      cash: 0,
      card: 0,
      transfer: 0,
    },
  });

  const getDateRange = (filter: TimeFilter) => {
    if (filter === "all") return {};
    const now = new Date();
    const end = new Date(now);
    const start = new Date(now);
    if (filter === "daily") {
      start.setDate(end.getDate());
    } else if (filter === "weekly") {
      start.setDate(end.getDate() - 7);
    } else if (filter === "monthly") {
      start.setDate(end.getDate() - 30);
    }
    return {
      dateFrom: start.toISOString().slice(0, 10),
      dateTo: end.toISOString().slice(0, 10),
    };
  };

  useEffect(() => {
    getSalesReport(getDateRange(timeFilter))
      .then((report) => {
        setSales(report.rows);
        setAggregates(report.aggregates);
      })
      .catch((error) => {
        console.error("Failed to load sales report", error);
      });
  }, [timeFilter]);

  const totalSales = aggregates.netTotal || aggregates.sumTotal;
  const totalTickets = aggregates.countOrders;
  const mainChannel = "POS";
  const mainChannelPercentage = totalTickets > 0 ? 100 : 0;

  const filteredSales = sales.filter((sale) => {
    const orderNumber = `#${sale.orderNumber}`;
    const serviceLabel = SERVICE_TYPE_LABELS[sale.serviceType] || sale.serviceType;
    return (
      orderNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      serviceLabel.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  const salesByHour = useMemo(() => {
    const map = new Map<string, number>();
    sales.forEach((sale) => {
      const hours = sale.createdAt.getHours();
      const label = `${hours}:00`;
      map.set(label, (map.get(label) ?? 0) + sale.total);
    });
    return Array.from(map.entries())
      .sort(([a], [b]) => Number(a.split(":")[0]) - Number(b.split(":")[0]))
      .map(([time, ventas]) => ({ time, ventas }));
  }, [sales]);

  const serviceTypeData = useMemo(() => {
    const total = sales.length || 1;
    const map = new Map<string, { count: number; amount: number }>();
    sales.forEach((sale) => {
      const key = sale.serviceType;
      const current = map.get(key) ?? { count: 0, amount: 0 };
      map.set(key, {
        count: current.count + 1,
        amount: current.amount + sale.total,
      });
    });
    const colors = [
      "hsl(var(--primary))",
      "hsl(var(--secondary))",
      "hsl(var(--info))",
      "hsl(var(--warning))",
    ];
    return Array.from(map.entries()).map(([key, value], index) => ({
      name: SERVICE_TYPE_LABELS[key] || key,
      value: Math.round((value.count / total) * 100),
      amount: value.amount,
      color: colors[index % colors.length],
    }));
  }, [sales]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">Reportes</h1>
        <p className="text-sm text-muted-foreground">
          Filtra el período de tiempo para analizar el rendimiento del restaurante.
        </p>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col lg:flex-row gap-4 items-start lg:items-center justify-between">
          <div className="flex gap-2 flex-wrap">
            {(["daily", "weekly", "monthly", "all"] as TimeFilter[]).map((filter) => (
              <Badge
                key={filter}
                variant={timeFilter === filter ? "default" : "outline"}
                className={cn(
                  "cursor-pointer transition-all hover:scale-105 px-4 py-2",
                  timeFilter === filter && "bg-secondary text-secondary-foreground"
                )}
                onClick={() => setTimeFilter(filter)}
              >
                {filter === "daily" && "Diario"}
                {filter === "weekly" && "Semanal"}
                {filter === "monthly" && "Mensual"}
                {filter === "all" && "Todos"}
              </Badge>
            ))}
          </div>

          <div className="flex gap-3 w-full lg:w-auto">
            <Select value={selectedBranch} onValueChange={setSelectedBranch}>
              <SelectTrigger className="w-full lg:w-[180px]">
                <SelectValue placeholder="Sucursal" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las sucursales</SelectItem>
                <SelectItem value="centro">Sucursal Centro</SelectItem>
                <SelectItem value="norte">Sucursal Norte</SelectItem>
                <SelectItem value="sur">Sucursal Sur</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="hover-lift">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ventas del período</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-secondary">${totalSales.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">Ventas netas después de reembolsos</p>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tickets del período</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTickets} tickets</div>
            <p className="text-xs text-muted-foreground mt-1">Órdenes procesadas</p>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Reembolsos</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-warning">${aggregates.refundTotal.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">{aggregates.refundsCount} reembolsos</p>
          </CardContent>
        </Card>

        <Card className="hover-lift">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Canal principal</CardTitle>
            <Store className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mainChannel}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {mainChannelPercentage}% de las ventas
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main Bar Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Ventas por período</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={salesByHour}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="time"
                  className="text-xs"
                  tick={{ fill: "hsl(var(--muted-foreground))" }}
                />
                <YAxis
                  className="text-xs"
                  tick={{ fill: "hsl(var(--muted-foreground))" }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                  }}
                  labelStyle={{ color: "hsl(var(--foreground))" }}
                />
                    <Bar dataKey="ventas" fill="hsl(var(--secondary))" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Service Types Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Ventas por tipo de servicio</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                      data={serviceTypeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                      {serviceTypeData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="space-y-2 mt-4">
                  {serviceTypeData.map((type, index) => (
                    <div key={index} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: type.color }}
                    />
                    <span className="text-muted-foreground">{type.name}</span>
                  </div>
                  <div className="font-semibold">
                    {type.value}% · ${type.amount.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Sales Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <CardTitle>Últimas ventas</CardTitle>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar pedido..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha y hora</TableHead>
                  <TableHead>Nº de pedido</TableHead>
                  <TableHead>Tipo de servicio</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead className="text-right">Monto</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                    {filteredSales.map((sale) => (
                      <TableRow key={sale.orderId}>
                        <TableCell className="text-muted-foreground">
                          {sale.createdAt.toLocaleString()}
                        </TableCell>
                        <TableCell className="font-medium">#{sale.orderNumber}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {SERVICE_TYPE_LABELS[sale.serviceType] || sale.serviceType}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="default"
                            className="text-xs"
                          >
                            POS
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          ${sale.total.toFixed(2)}
                        </TableCell>
                      </TableRow>
                    ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
