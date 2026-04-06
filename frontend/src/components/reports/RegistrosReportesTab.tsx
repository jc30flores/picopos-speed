import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Category,
  Product,
  ReportsComparisonMode,
  ReportsGranularity,
  SalesBreakdownDimension,
  SalesBreakdownRow,
  SalesTimeseriesResponse,
  getCategories,
  getModifierGroups,
  getPaymentMethods,
  getProducts,
  getSalesBreakdown,
  getSalesTimeseries,
} from "@/lib/api";
import { formatMoney } from "@/lib/money";

type GraphType = "line" | "bar";

const toISODate = (date: Date) => date.toISOString().slice(0, 10);
const shiftDays = (date: Date, days: number) => {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
};

const compareRange = (
  from: string,
  to: string,
  granularity: ReportsGranularity,
  mode: ReportsComparisonMode
): { compareFrom?: string; compareTo?: string } => {
  if (mode === "none") return {};
  const start = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  const diffDays = Math.max(1, Math.round((end.getTime() - start.getTime()) / 86400000) + 1);

  if (mode === "previous_year") {
    return {
      compareFrom: toISODate(new Date(start.getFullYear() - 1, start.getMonth(), start.getDate())),
      compareTo: toISODate(new Date(end.getFullYear() - 1, end.getMonth(), end.getDate())),
    };
  }
  if (granularity === "hours" || diffDays === 1) {
    return { compareFrom: toISODate(shiftDays(start, -7)), compareTo: toISODate(shiftDays(end, -7)) };
  }
  return { compareFrom: toISODate(shiftDays(start, -diffDays)), compareTo: toISODate(shiftDays(end, -diffDays)) };
};

const MultiSelect = ({
  title,
  options,
  selected,
  onToggle,
}: {
  title: string;
  options: Array<{ id: string; label: string }>;
  selected: string[];
  onToggle: (id: string) => void;
}) => (
  <div className="space-y-2">
    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
    <div className="max-h-40 space-y-2 overflow-y-auto rounded-lg border p-3">
      {options.map((option) => (
        <label key={option.id} className="flex items-center gap-2 text-sm">
          <Checkbox checked={selected.includes(option.id)} onCheckedChange={() => onToggle(option.id)} />
          <span className="truncate">{option.label}</span>
        </label>
      ))}
      {options.length === 0 && <p className="text-xs text-muted-foreground">Sin opciones</p>}
    </div>
  </div>
);

export const RegistrosReportesTab = () => {
  const today = toISODate(new Date());
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [granularity, setGranularity] = useState<ReportsGranularity>("hours");
  const [graphType, setGraphType] = useState<GraphType>("line");
  const [compareWith, setCompareWith] = useState<ReportsComparisonMode>("none");
  const [breakdownTab, setBreakdownTab] = useState<SalesBreakdownDimension>("service_type");

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [modifierOptions, setModifierOptions] = useState<Array<{ id: string; label: string }>>([]);
  const [paymentMethods, setPaymentMethods] = useState<Array<{ id: string; label: string }>>([]);

  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [selectedServiceTypes, setSelectedServiceTypes] = useState<string[]>([]);
  const [selectedPaymentMethods, setSelectedPaymentMethods] = useState<string[]>([]);
  const [selectedModifiers, setSelectedModifiers] = useState<string[]>([]);

  const [series, setSeries] = useState<SalesTimeseriesResponse | null>(null);
  const [breakdownRows, setBreakdownRows] = useState<SalesBreakdownRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const serviceTypeOptions = [
    { id: "MESA", label: "Mesa" },
    { id: "PARA_LLEVAR", label: "Para llevar" },
    { id: "KIOSK", label: "Kiosk" },
    { id: "PEDIDOS_YA", label: "Pedidos Ya" },
  ];

  useEffect(() => {
    Promise.all([getCategories(), getProducts(), getModifierGroups(), getPaymentMethods()])
      .then(([catRows, productRows, modifierGroups, methods]) => {
        setCategories(catRows);
        setProducts(productRows);
        setModifierOptions(
          modifierGroups.flatMap((group) =>
            group.modifiers.map((modifier) => ({ id: String(modifier.id), label: `${group.name} · ${modifier.name}` }))
          )
        );
        setPaymentMethods(methods.map((method) => ({ id: method.code, label: method.name })));
      })
      .catch(() => undefined);
  }, []);

  const toggle = (current: string[], setter: (next: string[]) => void, id: string) =>
    setter(current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);

  const load = async () => {
    setIsLoading(true);
    try {
      const comparison = compareRange(dateFrom, dateTo, granularity, compareWith);
      const [timeseries, breakdown] = await Promise.all([
        getSalesTimeseries({
          dateFrom,
          dateTo,
          granularity,
          compareWith,
          compareDateFrom: comparison.compareFrom,
          compareDateTo: comparison.compareTo,
        }),
        getSalesBreakdown({ dateFrom, dateTo, dimension: breakdownTab }),
      ]);
      setSeries(timeseries);
      setBreakdownRows(breakdown);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, [breakdownTab]);

  const currentKpis = series?.current ?? { totalSales: 0, transactions: 0, avgTicket: 0 };
  const comparisonKpis = series?.comparison ?? null;
  const comparisonDelta = useMemo(() => {
    if (!comparisonKpis || comparisonKpis.totalSales <= 0) return null;
    return ((currentKpis.totalSales - comparisonKpis.totalSales) / comparisonKpis.totalSales) * 100;
  }, [comparisonKpis, currentKpis.totalSales]);

  return (
    <div className="space-y-6">
      <Card className="p-4 md:p-6">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-12" />
          <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="h-12" />
          <Select value={granularity} onValueChange={(value) => setGranularity(value as ReportsGranularity)}>
            <SelectTrigger className="h-12"><SelectValue placeholder="Granularidad" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="hours">Horas</SelectItem>
              <SelectItem value="week">Semana</SelectItem>
              <SelectItem value="month">Mes</SelectItem>
              <SelectItem value="year">Año</SelectItem>
            </SelectContent>
          </Select>
          <Select value={graphType} onValueChange={(value) => setGraphType(value as GraphType)}>
            <SelectTrigger className="h-12"><SelectValue placeholder="Tipo de gráfica" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="line">Línea</SelectItem>
              <SelectItem value="bar">Barra</SelectItem>
            </SelectContent>
          </Select>
          <Select value={compareWith} onValueChange={(value) => setCompareWith(value as ReportsComparisonMode)}>
            <SelectTrigger className="h-12"><SelectValue placeholder="Comparar con" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Sin comparación</SelectItem>
              <SelectItem value="previous_period">Periodo anterior</SelectItem>
              <SelectItem value="previous_year">Mismo periodo año anterior</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="mt-3 flex justify-end">
          <Button onClick={() => void load()} disabled={isLoading}>{isLoading ? "Cargando..." : "Aplicar filtros"}</Button>
        </div>
      </Card>

      <Accordion type="single" collapsible>
        <AccordionItem value="advanced">
          <AccordionTrigger>Filtros avanzados</AccordionTrigger>
          <AccordionContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
              <MultiSelect title="Categorías" options={categories.map((c) => ({ id: String(c.id), label: c.name }))} selected={selectedCategories} onToggle={(id) => toggle(selectedCategories, setSelectedCategories, id)} />
              <MultiSelect title="Productos" options={products.map((p) => ({ id: String(p.id), label: p.name }))} selected={selectedProducts} onToggle={(id) => toggle(selectedProducts, setSelectedProducts, id)} />
              <MultiSelect title="Tipos de servicio" options={serviceTypeOptions} selected={selectedServiceTypes} onToggle={(id) => toggle(selectedServiceTypes, setSelectedServiceTypes, id)} />
              <MultiSelect title="Métodos de pago" options={paymentMethods} selected={selectedPaymentMethods} onToggle={(id) => toggle(selectedPaymentMethods, setSelectedPaymentMethods, id)} />
              <MultiSelect title="Modificadores" options={modifierOptions} selected={selectedModifiers} onToggle={(id) => toggle(selectedModifiers, setSelectedModifiers, id)} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">UI preparada para enviar filtros multi-select al backend de agregados.</p>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card><CardHeader><CardTitle className="text-sm">Total ventas</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{formatMoney(currentKpis.totalSales)}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Transacciones</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{currentKpis.transactions}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Ticket promedio</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{formatMoney(currentKpis.avgTicket)}</CardContent></Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Ventas por periodo</CardTitle>
          {comparisonDelta !== null ? (
            <Badge variant={comparisonDelta >= 0 ? "default" : "destructive"}>
              {comparisonDelta >= 0 ? "+" : ""}{comparisonDelta.toFixed(1)}%
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            {graphType === "line" ? (
              <LineChart data={series?.points ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bucket" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line dataKey="currentTotal" name="Actual" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                <Line dataKey="comparisonTotal" name="Comparación" stroke="hsl(var(--secondary))" strokeWidth={2} dot={false} />
              </LineChart>
            ) : (
              <BarChart data={series?.points ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bucket" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="currentTotal" name="Actual" fill="hsl(var(--primary))" />
                <Bar dataKey="comparisonTotal" name="Comparación" fill="hsl(var(--secondary))" />
              </BarChart>
            )}
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Desgloses</CardTitle>
          <Tabs value={breakdownTab} onValueChange={(value) => setBreakdownTab(value as SalesBreakdownDimension)}>
            <TabsList className="grid w-full grid-cols-2 gap-2 md:grid-cols-5">
              <TabsTrigger value="category">Categoría</TabsTrigger>
              <TabsTrigger value="product">Producto</TabsTrigger>
              <TabsTrigger value="service_type">Servicio</TabsTrigger>
              <TabsTrigger value="payment_method">Pago</TabsTrigger>
              <TabsTrigger value="modifier">Modificadores</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={breakdownRows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" hide />
                <YAxis />
                <Tooltip />
                <Bar dataKey="total" fill="hsl(var(--primary))" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Elemento</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>%</TableHead>
                  <TableHead>Transacciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {breakdownRows.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell>{formatMoney(row.total)}</TableCell>
                    <TableCell>{row.percentage.toFixed(1)}%</TableCell>
                    <TableCell>{row.transactions}</TableCell>
                  </TableRow>
                ))}
                {breakdownRows.length === 0 && (
                  <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin datos para los filtros actuales.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
