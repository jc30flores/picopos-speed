import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
  EmployeeWorkedHoursRow,
  Product,
  ReportsComparisonMode,
  ReportsGranularity,
  SalesBreakdownDimension,
  SalesBreakdownRow,
  SalesTimeseriesResponse,
  getCategories,
  getEmployeeWorkedHoursReport,
  getModifierGroups,
  getPaymentMethods,
  getProducts,
  getSalesBreakdown,
  getSalesTimeseries,
} from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { useServiceTypes } from "@/hooks/useServiceTypes";

const toISODate = (date: Date) => date.toISOString().slice(0, 10);
const getMonthRange = () => {
  const now = new Date();
  return {
    start: toISODate(new Date(now.getFullYear(), now.getMonth(), 1)),
    end: toISODate(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
};
const shiftDays = (date: Date, days: number) => {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
};
const formatHours = (minutes: number) => `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;

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
    <div className="max-h-40 space-y-2 overflow-y-auto rounded-lg border border-border/70 bg-background p-3">
      {options.map((option) => (
        <label key={option.id} className="flex items-center gap-2 text-sm text-foreground">
          <Checkbox checked={selected.includes(option.id)} onCheckedChange={() => onToggle(option.id)} />
          <span className="truncate">{option.label}</span>
        </label>
      ))}
      {options.length === 0 && <p className="text-xs text-muted-foreground">Sin opciones</p>}
    </div>
  </div>
);

export const RegistrosReportesTab = () => {
  const initialRange = getMonthRange();
  const [dateFrom, setDateFrom] = useState(initialRange.start);
  const [dateTo, setDateTo] = useState(initialRange.end);
  const [granularity, setGranularity] = useState<ReportsGranularity>("week");
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
  const [employeeHoursRows, setEmployeeHoursRows] = useState<EmployeeWorkedHoursRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hoursLoading, setHoursLoading] = useState(false);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [debouncedFilters, setDebouncedFilters] = useState("");
  const pendingRequestRef = useRef<AbortController | null>(null);
  const hoursRequestRef = useRef<AbortController | null>(null);
  const { activeServiceTypes } = useServiceTypes();

  const serviceTypeOptions = activeServiceTypes.map((item) => ({ id: item.key, label: item.label }));

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

  const load = useCallback(async () => {
    pendingRequestRef.current?.abort();
    const controller = new AbortController();
    pendingRequestRef.current = controller;
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
          categoryIds: selectedCategories,
          productIds: selectedProducts,
          modifierIds: selectedModifiers,
          serviceTypes: selectedServiceTypes,
          paymentMethods: selectedPaymentMethods,
          signal: controller.signal,
        }),
        getSalesBreakdown({
          dateFrom,
          dateTo,
          dimension: breakdownTab,
          compareWith,
          categoryIds: selectedCategories,
          productIds: selectedProducts,
          modifierIds: selectedModifiers,
          serviceTypes: selectedServiceTypes,
          paymentMethods: selectedPaymentMethods,
          signal: controller.signal,
        }),
      ]);
      setSeries(timeseries);
      setBreakdownRows(breakdown);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        throw error;
      }
    } finally {
      if (pendingRequestRef.current === controller) {
        setIsLoading(false);
      }
    }
  }, [breakdownTab, compareWith, dateFrom, dateTo, granularity, selectedCategories, selectedModifiers, selectedPaymentMethods, selectedProducts, selectedServiceTypes]);

  const loadEmployeeHours = useCallback(async () => {
    hoursRequestRef.current?.abort();
    const controller = new AbortController();
    hoursRequestRef.current = controller;
    setHoursLoading(true);
    try {
      const rows = await getEmployeeWorkedHoursReport({ dateFrom, dateTo, signal: controller.signal });
      setEmployeeHoursRows(rows.sort((a, b) => b.totalMinutes - a.totalMinutes));
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        throw error;
      }
    } finally {
      if (hoursRequestRef.current === controller) {
        setHoursLoading(false);
      }
    }
  }, [dateFrom, dateTo]);

  useEffect(() => {
    if (!dateFrom || !dateTo) {
      setFilterError("Selecciona una fecha de inicio y una fecha de fin.");
      return;
    }
    if (dateTo < dateFrom) {
      setFilterError("La fecha fin no puede ser menor que la fecha inicio.");
      return;
    }
    setFilterError(null);

    const next = JSON.stringify({
      dateFrom,
      dateTo,
      granularity,
      compareWith,
      breakdownTab,
      selectedCategories,
      selectedProducts,
      selectedServiceTypes,
      selectedPaymentMethods,
      selectedModifiers,
    });
    const timeout = window.setTimeout(() => setDebouncedFilters(next), 300);
    return () => window.clearTimeout(timeout);
  }, [breakdownTab, compareWith, dateFrom, dateTo, granularity, selectedCategories, selectedModifiers, selectedPaymentMethods, selectedProducts, selectedServiceTypes]);

  useEffect(() => {
    if (!debouncedFilters || filterError) return;
    load().catch(() => undefined);
    loadEmployeeHours().catch(() => undefined);
    return () => {
      pendingRequestRef.current?.abort();
      hoursRequestRef.current?.abort();
    };
  }, [debouncedFilters, filterError, load, loadEmployeeHours]);

  const currentKpis = series?.current ?? { totalSales: 0, transactions: 0, avgTicket: 0 };
  const comparisonKpis = series?.comparison ?? null;
  const comparisonDelta = useMemo(() => {
    if (!comparisonKpis || comparisonKpis.totalSales <= 0) return null;
    return ((currentKpis.totalSales - comparisonKpis.totalSales) / comparisonKpis.totalSales) * 100;
  }, [comparisonKpis, currentKpis.totalSales]);

  return (
    <div className="space-y-5">
      <Card className="border-border/70 bg-card/80 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">Rango de análisis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-11 bg-background" />
            <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="h-11 bg-background" />
            <Select value={granularity} onValueChange={(value) => setGranularity(value as ReportsGranularity)}>
              <SelectTrigger className="h-11 bg-background"><SelectValue placeholder="Granularidad" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="hours">Horas</SelectItem>
                <SelectItem value="week">Semana</SelectItem>
                <SelectItem value="month">Mes</SelectItem>
                <SelectItem value="year">Año</SelectItem>
              </SelectContent>
            </Select>
            <Select value={compareWith} onValueChange={(value) => setCompareWith(value as ReportsComparisonMode)}>
              <SelectTrigger className="h-11 bg-background"><SelectValue placeholder="Comparar con" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Sin comparación</SelectItem>
                <SelectItem value="previous_period">Periodo anterior</SelectItem>
                <SelectItem value="previous_year">Mismo periodo año anterior</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              className="h-11"
              onClick={() => {
                const next = getMonthRange();
                setDateFrom(next.start);
                setDateTo(next.end);
              }}
            >
              Mes actual
            </Button>
          </div>
          {filterError ? <p className="text-sm text-destructive">{filterError}</p> : null}
        </CardContent>
      </Card>

      <Accordion type="single" collapsible>
        <AccordionItem value="advanced" className="rounded-xl border border-border/70 bg-card/70 px-4">
          <AccordionTrigger className="text-sm font-medium">Filtros avanzados</AccordionTrigger>
          <AccordionContent>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
              <MultiSelect title="Categorías" options={categories.map((c) => ({ id: String(c.id), label: c.name }))} selected={selectedCategories} onToggle={(id) => toggle(selectedCategories, setSelectedCategories, id)} />
              <MultiSelect title="Productos" options={products.map((p) => ({ id: String(p.id), label: p.name }))} selected={selectedProducts} onToggle={(id) => toggle(selectedProducts, setSelectedProducts, id)} />
              <MultiSelect title="Tipos de servicio" options={serviceTypeOptions} selected={selectedServiceTypes} onToggle={(id) => toggle(selectedServiceTypes, setSelectedServiceTypes, id)} />
              <MultiSelect title="Métodos de pago" options={paymentMethods} selected={selectedPaymentMethods} onToggle={(id) => toggle(selectedPaymentMethods, setSelectedPaymentMethods, id)} />
              <MultiSelect title="Modificadores" options={modifierOptions} selected={selectedModifiers} onToggle={(id) => toggle(selectedModifiers, setSelectedModifiers, id)} />
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="border-border/70 bg-card/80"><CardHeader><CardTitle className="text-sm text-muted-foreground">Total ventas</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{formatMoney(currentKpis.totalSales)}</CardContent></Card>
        <Card className="border-border/70 bg-card/80"><CardHeader><CardTitle className="text-sm text-muted-foreground">Transacciones</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{currentKpis.transactions}</CardContent></Card>
        <Card className="border-border/70 bg-card/80"><CardHeader><CardTitle className="text-sm text-muted-foreground">Ticket promedio</CardTitle></CardHeader><CardContent className="text-2xl font-bold">{formatMoney(currentKpis.avgTicket)}</CardContent></Card>
      </div>

      <Card className="border-border/70 bg-card/80 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-lg">Ventas por periodo</CardTitle>
          {comparisonDelta !== null ? (
            <Badge variant={comparisonDelta >= 0 ? "default" : "destructive"}>
              {comparisonDelta >= 0 ? "+" : ""}{comparisonDelta.toFixed(1)}%
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            {series?.points?.length ? (
              <AreaChart data={series.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="bucket" stroke="hsl(var(--muted-foreground))" />
                <YAxis tickFormatter={(value) => formatMoney(Number(value))} stroke="hsl(var(--muted-foreground))" />
                <Tooltip formatter={(value: number | string) => formatMoney(Number(value || 0))} />
                <Legend />
                <Area dataKey="currentTotal" name="Actual" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / 0.22)" strokeWidth={2} />
                <Line dataKey="comparisonTotal" name="Comparación" stroke="hsl(var(--muted-foreground))" strokeWidth={2} dot={false} />
              </AreaChart>
            ) : (
              <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
                {isLoading ? "Cargando datos..." : "Sin datos para el rango seleccionado"}
              </div>
            )}
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-card/80 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Horas trabajadas por empleado</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Empleado</TableHead>
                <TableHead className="text-right">Total trabajado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {hoursLoading ? <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">Cargando horas...</TableCell></TableRow> : null}
              {!hoursLoading && employeeHoursRows.map((row) => (
                <TableRow key={row.employeeId}>
                  <TableCell className="font-medium">{row.employeeName}</TableCell>
                  <TableCell className="text-right font-semibold text-primary">{formatHours(row.totalMinutes)}</TableCell>
                </TableRow>
              ))}
              {!hoursLoading && employeeHoursRows.length === 0 ? <TableRow><TableCell colSpan={2} className="text-center text-muted-foreground">No hay horas registradas en este rango.</TableCell></TableRow> : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-card/80">
        <CardHeader>
          <CardTitle>Desgloses</CardTitle>
          <Tabs value={breakdownTab} onValueChange={(value) => setBreakdownTab(value as SalesBreakdownDimension)}>
            <TabsList className="grid w-full grid-cols-2 gap-2 bg-muted/70 md:grid-cols-5">
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
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="label" hide />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip formatter={(value: number | string) => formatMoney(Number(value || 0))} />
                <Bar dataKey="total" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-auto rounded-lg border border-border/70">
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
