import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  TrendingUp,
  Store,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";

type TimeFilter = "daily" | "weekly" | "monthly" | "all";

// Mock data
const mockSalesByHour = [
  { time: "9:00", ventas: 120 },
  { time: "10:00", ventas: 250 },
  { time: "11:00", ventas: 380 },
  { time: "12:00", ventas: 520 },
  { time: "13:00", ventas: 680 },
  { time: "14:00", ventas: 590 },
  { time: "15:00", ventas: 420 },
  { time: "16:00", ventas: 310 },
  { time: "17:00", ventas: 280 },
  { time: "18:00", ventas: 450 },
  { time: "19:00", ventas: 620 },
  { time: "20:00", ventas: 580 },
];

const mockServiceTypes = [
  { name: "En local", value: 45, amount: 560.0, color: "hsl(var(--primary))" },
  { name: "Kiosk", value: 30, amount: 375.0, color: "hsl(var(--secondary))" },
  { name: "Para llevar", value: 18, amount: 225.0, color: "hsl(var(--info))" },
  { name: "Delivery", value: 7, amount: 90.5, color: "hsl(var(--warning))" },
];

const mockRecentSales = [
  {
    id: "001",
    date: "2025-11-23 19:45",
    orderNumber: "#1234",
    serviceType: "En local",
    channel: "POS",
    amount: 34.5,
  },
  {
    id: "002",
    date: "2025-11-23 19:32",
    orderNumber: "#1233",
    serviceType: "Kiosk",
    channel: "Kiosk",
    amount: 18.75,
  },
  {
    id: "003",
    date: "2025-11-23 19:18",
    orderNumber: "#1232",
    serviceType: "Para llevar",
    channel: "POS",
    amount: 42.0,
  },
  {
    id: "004",
    date: "2025-11-23 19:05",
    orderNumber: "#1231",
    serviceType: "En local",
    channel: "POS",
    amount: 27.5,
  },
  {
    id: "005",
    date: "2025-11-23 18:52",
    orderNumber: "#1230",
    serviceType: "Delivery",
    channel: "POS",
    amount: 56.25,
  },
  {
    id: "006",
    date: "2025-11-23 18:40",
    orderNumber: "#1229",
    serviceType: "Kiosk",
    channel: "Kiosk",
    amount: 15.0,
  },
  {
    id: "007",
    date: "2025-11-23 18:28",
    orderNumber: "#1228",
    serviceType: "En local",
    channel: "POS",
    amount: 68.5,
  },
  {
    id: "008",
    date: "2025-11-23 18:15",
    orderNumber: "#1227",
    serviceType: "Para llevar",
    channel: "POS",
    amount: 22.75,
  },
];

const Reports = () => {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("daily");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState("all");

  // Mock KPIs
  const totalSales = 1250.5;
  const totalTickets = 87;
  const averageTicket = totalSales / totalTickets;
  const mainChannel = "POS";
  const mainChannelPercentage = 62;

  const filteredSales = mockRecentSales.filter(
    (sale) =>
      sale.orderNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sale.serviceType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-8">
        <div className="max-w-7xl mx-auto space-y-6">
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
                <p className="text-xs text-muted-foreground mt-1">Total vendido</p>
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
                <CardTitle className="text-sm font-medium">Ticket promedio</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">${averageTicket.toFixed(2)}</div>
                <p className="text-xs text-muted-foreground mt-1">Por orden</p>
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
                  <BarChart data={mockSalesByHour}>
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
                      data={mockServiceTypes}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {mockServiceTypes.map((entry, index) => (
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
                  {mockServiceTypes.map((type, index) => (
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
                      <TableRow key={sale.id}>
                        <TableCell className="text-muted-foreground">{sale.date}</TableCell>
                        <TableCell className="font-medium">{sale.orderNumber}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{sale.serviceType}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={sale.channel === "POS" ? "default" : "secondary"}
                            className="text-xs"
                          >
                            {sale.channel}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          ${sale.amount.toFixed(2)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Reports;
