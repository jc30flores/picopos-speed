import { useCallback, useEffect, useMemo, useState } from "react";
import { Search, Plus, Edit, Copy, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BxgyConfig, Discount } from "@/types/menu";
import { DiscountFormDialog } from "./DiscountFormDialog";
import { useServiceTypes } from "@/hooks/useServiceTypes";
import {
  getCategories,
  getDiscounts,
  deleteDiscount,
  Category,
  Discount as ApiDiscount,
} from "@/lib/api";
import { toast } from "sonner";

const DAYS_SHORT = ["D", "L", "M", "X", "J", "V", "S"];

export const DiscountsTab = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showFormDialog, setShowFormDialog] = useState(false);
  const [editingDiscount, setEditingDiscount] = useState<Discount | null>(null);
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const { serviceTypes } = useServiceTypes();

  const categoryMap = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories]
  );

  const mapDiscounts = (
    apiDiscounts: ApiDiscount[],
    mapCategories: Map<number, string>
  ) => {
    const mapped = apiDiscounts.map((discount) => ({
      id: String(discount.id),
      name: discount.name,
      description: discount.description,
      type: discount.type,
      value: discount.value,
      appliesTo: discount.appliesTo,
      targetCategories: (discount.targetCategoryIds ?? [])
        .map((id) => mapCategories.get(id))
        .filter(Boolean) as string[],
      targetProducts: [],
      targetProductIds: discount.targetProductIds ?? [],
      days: discount.daysOfWeek ?? [],
      startTime: discount.startTime ?? undefined,
      endTime: discount.endTime ?? undefined,
      serviceTypes: (discount.serviceTypes ?? []).filter(Boolean) as Discount["serviceTypes"],
      minAmount: discount.minAmount ?? 0,
      autoApply: discount.autoApply,
      active: discount.isActive,
      priority: discount.priority ?? 100,
      stackable: Boolean(discount.stackable),
      bxgyConfig: (discount.bxgyConfig as BxgyConfig | undefined) ?? undefined,
    }));
    setDiscounts(mapped);
  };

  const loadDiscountData = useCallback(async () => {
    const [categoriesResponse, discountsResponse] = await Promise.all([
      getCategories(),
      getDiscounts(),
    ]);
    setCategories(categoriesResponse);
    mapDiscounts(
      discountsResponse,
      new Map(categoriesResponse.map((category) => [category.id, category.name]))
    );
  }, []);

  useEffect(() => {
    loadDiscountData().catch((error) => {
      console.error("Failed to load discounts", error);
    });
  }, [loadDiscountData]);

  const filteredDiscounts = discounts.filter((discount) => {
    const matchesSearch = discount.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === "all" || discount.type === typeFilter;
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && discount.active) ||
      (statusFilter === "inactive" && !discount.active);
    return matchesSearch && matchesType && matchesStatus;
  });

  const getTypeLabel = (type: string) => {
    const types: Record<string, string> = {
      percent: "Porcentaje",
      fixed: "Monto fijo",
      bxgy: "Compra X / Lleva Y",
    };
    return types[type] || type;
  };

  const getAppliesLabel = (discount: Discount) => {
    if (discount.appliesTo === "order") return "Ticket completo";
    if (discount.appliesTo === "categories")
      return `Categorías: ${discount.targetCategories?.join(", ")}`;
    if (discount.appliesTo === "products")
      return `Productos específicos`;
    return "";
  };

  const getConditionSummary = (discount: Discount) => {
    const parts: string[] = [];
    
    // Days
    const dayNames = discount.days.map(d => DAYS_SHORT[d]).join(", ");
    if (dayNames) parts.push(dayNames);
    
    // Time
    if (discount.startTime && discount.endTime) {
      parts.push(`${discount.startTime}–${discount.endTime}`);
    }
    
    // Service types
    const serviceMap = new Map(serviceTypes.map((item) => [item.key, item.label]));
    const services = discount.serviceTypes.map((key) => serviceMap.get(key) ?? key).join(", ");
    if (services) parts.push(services);
    
    // Min amount
    if (discount.minAmount && discount.minAmount > 0) {
      parts.push(`Min $${discount.minAmount}`);
    }
    
    return parts.join(" · ");
  };

  const handleNew = () => {
    setEditingDiscount(null);
    setShowFormDialog(true);
  };

  const handleEdit = (discount: Discount) => {
    setEditingDiscount(discount);
    setShowFormDialog(true);
  };

  const handleDuplicate = (discount: Discount) => {
    setEditingDiscount({ ...discount, id: "", name: `${discount.name} (copia)` });
    setShowFormDialog(true);
  };

  const handleDelete = async (discount: Discount) => {
    const confirmed = window.confirm(`¿Eliminar descuento "${discount.name}"?`);
    if (!confirmed) return;
    try {
      await deleteDiscount(Number(discount.id));
      setDiscounts((prev) => prev.filter((row) => row.id !== discount.id));
      toast.success("Descuento eliminado");
    } catch (error) {
      console.error("Failed to delete discount", error);
      toast.error(error instanceof Error ? error.message : "No se pudo eliminar el descuento");
    }
  };

  return (
    <div className="space-y-4">
      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold">Descuentos</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Configura descuentos automáticos por día, hora y tipo de venta
            </p>
          </div>
          <Button
            variant="default"
            className="bg-secondary hover:bg-secondary/90"
            onClick={handleNew}
          >
            <Plus className="h-4 w-4 mr-2" />
            Nuevo descuento
          </Button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar descuentos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Tipo de descuento" />
              </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los tipos</SelectItem>
              <SelectItem value="percent">Porcentaje</SelectItem>
              <SelectItem value="fixed">Monto fijo</SelectItem>
              <SelectItem value="bxgy">Compra X / Lleva Y</SelectItem>
            </SelectContent>
          </Select>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="active">Activos</SelectItem>
                <SelectItem value="inactive">Inactivos</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-6 border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Aplica a</TableHead>
                <TableHead>Condiciones</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDiscounts.map((discount) => (
                <TableRow key={discount.id}>
                  <TableCell>
                    <div>
                      <div className="font-semibold">{discount.name}</div>
                      {discount.description && (
                        <div className="text-sm text-muted-foreground">
                          {discount.description}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <Badge variant="outline">{getTypeLabel(discount.type)}</Badge>
                      <div className="text-sm font-semibold text-secondary mt-1">
                        {discount.type === "percent" && `${discount.value}%`}
                        {discount.type === "fixed" && `$${discount.value}`}
                        {discount.type === "bxgy" && "BXGY"}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">{getAppliesLabel(discount)}</div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm text-muted-foreground max-w-xs">
                      {getConditionSummary(discount)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={discount.active ? "default" : "outline"}>
                      {discount.active ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEdit(discount)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDuplicate(discount)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => void handleDelete(discount)}>
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <DiscountFormDialog
        open={showFormDialog}
        onOpenChange={setShowFormDialog}
        editingDiscount={editingDiscount}
        categories={categories}
        serviceTypes={serviceTypes}
        onSaved={loadDiscountData}
      />
    </div>
  );
};
