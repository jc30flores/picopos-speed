import { useMemo, useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BxgyConfig, Discount } from "@/types/menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Category, Product, ServiceType, createDiscount, getProducts, updateDiscount } from "@/lib/api";
import { Clock, X } from "lucide-react";

interface DiscountFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingDiscount: Discount | null;
  categories: Category[];
  serviceTypes: ServiceType[];
  onSaved: () => Promise<void>;
}

const DAYS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const DAYS_SHORT = ["D", "L", "M", "X", "J", "V", "S"];

type DiscountType = "percent" | "fixed" | "bxgy";
type AppliesTo = "order" | "categories" | "products";
type ServiceTypeKey = "dine-in" | "takeout" | "delivery" | "kiosk";
type BxgyRewardType = "percent" | "fixed_amount" | "fixed_price";
type BxgyApplyTo = "cheapest" | "most_expensive";

const SERVICE_TYPE_KEYS: readonly ServiceTypeKey[] = ["dine-in", "takeout", "delivery", "kiosk"];
const BXGY_REWARD_TYPES: readonly BxgyRewardType[] = ["percent", "fixed_amount", "fixed_price"];
const BXGY_APPLY_TO: readonly BxgyApplyTo[] = ["cheapest", "most_expensive"];

const isServiceTypeKey = (value: string): value is ServiceTypeKey => SERVICE_TYPE_KEYS.includes(value as ServiceTypeKey);
const isDiscountType = (value: string): value is DiscountType => ["percent", "fixed", "bxgy"].includes(value);
const isAppliesTo = (value: string): value is AppliesTo => ["order", "categories", "products"].includes(value);
const isBxgyRewardType = (value: string): value is BxgyRewardType => BXGY_REWARD_TYPES.includes(value as BxgyRewardType);
const isBxgyApplyTo = (value: string): value is BxgyApplyTo => BXGY_APPLY_TO.includes(value as BxgyApplyTo);

export const DiscountFormDialog = ({
  open,
  onOpenChange,
  editingDiscount,
  categories,
  serviceTypes: availableServiceTypes,
  onSaved,
}: DiscountFormDialogProps) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [active, setActive] = useState(true);
  const [type, setType] = useState<DiscountType>("percent");
  const [value, setValue] = useState("");
  const [appliesTo, setAppliesTo] = useState<AppliesTo>("order");
  const [targetCategories, setTargetCategories] = useState<string[]>([]);
  const [days, setDays] = useState<number[]>([]);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [serviceTypes, setServiceTypes] = useState<ServiceTypeKey[]>([]);
  const [minAmount, setMinAmount] = useState("");
  const [autoApply, setAutoApply] = useState(true);

  const [priority, setPriority] = useState(100);
  const [stackable, setStackable] = useState(false);
  const [bxgyBuyQty, setBxgyBuyQty] = useState(2);
  const [bxgyGetQty, setBxgyGetQty] = useState(1);
  const [bxgyRewardType, setBxgyRewardType] = useState<BxgyRewardType>("percent");
  const [bxgyRewardValue, setBxgyRewardValue] = useState("100");
  const [bxgyApplyTo, setBxgyApplyTo] = useState<BxgyApplyTo>("cheapest");
  const [bxgyIncludeModifiers, setBxgyIncludeModifiers] = useState(false);
  const [bxgyMaxApplications, setBxgyMaxApplications] = useState(1);
  const [bxgyExcludeDisposables, setBxgyExcludeDisposables] = useState(true);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Record<number, Product>>({});
  const [productSearch, setProductSearch] = useState("");
  const [debouncedProductSearch, setDebouncedProductSearch] = useState("");
  const [productCategoryId, setProductCategoryId] = useState<string>("all");
  const [products, setProducts] = useState<Product[]>([]);
  const [productPage, setProductPage] = useState(1);
  const [hasMoreProducts, setHasMoreProducts] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const startTimeRef = useRef<HTMLInputElement>(null);
  const endTimeRef = useRef<HTMLInputElement>(null);

  const focusTimeInput = (ref: React.RefObject<HTMLInputElement>) => {
    const input = ref.current;
    if (!input) return;
    input.focus();
    if ("showPicker" in input) {
      (input as HTMLInputElement & { showPicker?: () => void }).showPicker?.();
    }
  };

  const parseNumber = (raw: string) => {
    const parsed = Number(raw);
    return Number.isNaN(parsed) ? 0 : parsed;
  };

  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedProductSearch(productSearch.trim());
    }, 300);
    return () => clearTimeout(handle);
  }, [productSearch]);

  useEffect(() => {
    if (!open || appliesTo !== "products") return;
    if (selectedProductIds.length === 0) return;
    const missingIds = selectedProductIds.filter((id) => !selectedProducts[id]);
    if (missingIds.length === 0) return;
    getProducts({ ids: missingIds })
      .then((results) => {
        setSelectedProducts((prev) => {
          const next = { ...prev };
          results.forEach((product) => {
            next[product.id] = product;
          });
          return next;
        });
      })
      .catch((error) => {
        console.error("Failed to load selected products", error);
      });
  }, [open, appliesTo, selectedProductIds, selectedProducts]);

  useEffect(() => {
    if (!open || appliesTo !== "products") return;
    setProductPage(1);
    setHasMoreProducts(true);
    setProducts([]);
  }, [open, appliesTo, debouncedProductSearch, productCategoryId]);

  useEffect(() => {
    if (!open || appliesTo !== "products") return;
    const loadProducts = async () => {
      setProductsLoading(true);
      setProductsError(null);
      try {
        const response = await getProducts({
          search: debouncedProductSearch,
          categoryId: productCategoryId === "all" ? undefined : Number(productCategoryId),
          page: productPage,
          limit: 20,
        });
        setProducts((prev) => (productPage === 1 ? response : [...prev, ...response]));
        setHasMoreProducts(response.length === 20);
        setSelectedProducts((prev) => {
          const next = { ...prev };
          response.forEach((product) => {
            if (selectedProductIds.includes(product.id)) {
              next[product.id] = product;
            }
          });
          return next;
        });
      } catch (error) {
        console.error("Failed to load products", error);
        setProductsError("No pudimos cargar los productos.");
      } finally {
        setProductsLoading(false);
      }
    };
    loadProducts();
  }, [open, appliesTo, debouncedProductSearch, productCategoryId, productPage, selectedProductIds]);

  useEffect(() => {
    if (editingDiscount) {
      setName(editingDiscount.name);
      setDescription(editingDiscount.description || "");
      setActive(editingDiscount.active);
      setType(editingDiscount.type);
      setValue(String(editingDiscount.value));
      setAppliesTo(editingDiscount.appliesTo);
      setTargetCategories(editingDiscount.targetCategories || []);
      setDays(editingDiscount.days);
      setStartTime(editingDiscount.startTime || "");
      setEndTime(editingDiscount.endTime || "");
      setServiceTypes(editingDiscount.serviceTypes);
      setMinAmount(editingDiscount.minAmount ? String(editingDiscount.minAmount) : "");
      setAutoApply(editingDiscount.autoApply);
      setPriority(editingDiscount.priority ?? 100);
      setStackable(Boolean(editingDiscount.stackable));
      const bx = editingDiscount.bxgyConfig as BxgyConfig | undefined;
      const firstRule = bx?.rules?.[0];
      setBxgyBuyQty(Number(firstRule?.buy?.qty ?? 2));
      setBxgyGetQty(Number(firstRule?.get?.qty ?? 1));
      setBxgyRewardType(isBxgyRewardType(firstRule?.get?.reward?.type ?? "") ? firstRule!.get.reward.type : "percent");
      setBxgyRewardValue(String(firstRule?.get?.reward?.value ?? 100));
      setBxgyApplyTo(isBxgyApplyTo(firstRule?.get?.apply_to ?? "") ? firstRule!.get.apply_to : "cheapest");
      setBxgyIncludeModifiers(Boolean(firstRule?.get?.include_paid_modifiers ?? firstRule?.get?.reward?.include_paid_modifiers));
      setBxgyMaxApplications(Number(firstRule?.limits?.max_applications_per_ticket ?? 1));
      setBxgyExcludeDisposables(Boolean(bx?.global?.exclude_disposables ?? true));
      setSelectedProductIds(editingDiscount.targetProductIds ?? []);
    } else {
      // Reset form
      setName("");
      setDescription("");
      setActive(true);
      setType("percent");
      setValue("");
      setAppliesTo("order");
      setTargetCategories([]);
      setDays([]);
      setStartTime("");
      setEndTime("");
      setServiceTypes([]);
      setMinAmount("");
      setAutoApply(true);
      setPriority(100);
      setStackable(false);
      setBxgyBuyQty(2);
      setBxgyGetQty(1);
      setBxgyRewardType("percent");
      setBxgyRewardValue("100");
      setBxgyApplyTo("cheapest");
      setBxgyIncludeModifiers(false);
      setBxgyMaxApplications(1);
      setBxgyExcludeDisposables(true);
      setSelectedProductIds([]);
    }
    setSelectedProducts({});
    setProductSearch("");
    setDebouncedProductSearch("");
    setProductCategoryId("all");
    setProducts([]);
    setProductPage(1);
    setHasMoreProducts(true);
    setProductsLoading(false);
    setProductsError(null);
  }, [editingDiscount, open]);

  const toggleDay = (dayIndex: number) => {
    if (days.includes(dayIndex)) {
      setDays(days.filter((d) => d !== dayIndex));
    } else {
      setDays([...days, dayIndex]);
    }
  };

  const toggleServiceType = (service: ServiceTypeKey) => {
    if (serviceTypes.includes(service)) {
      setServiceTypes(serviceTypes.filter((s) => s !== service));
    } else {
      setServiceTypes([...serviceTypes, service]);
    }
  };

  const toggleCategory = (category: string) => {
    if (targetCategories.includes(category)) {
      setTargetCategories(targetCategories.filter((c) => c !== category));
    } else {
      setTargetCategories([...targetCategories, category]);
    }
  };

  const selectedProductList = useMemo(
    () =>
      selectedProductIds.map((id) => ({
        id,
        name: selectedProducts[id]?.name ?? `Producto #${id}`,
      })),
    [selectedProductIds, selectedProducts]
  );

  const toggleProductSelection = (product: Product) => {
    setSelectedProductIds((prev) => {
      if (prev.includes(product.id)) {
        return prev.filter((id) => id !== product.id);
      }
      return [...prev, product.id];
    });
    setSelectedProducts((prev) => ({ ...prev, [product.id]: product }));
  };

  const removeSelectedProduct = (productId: number) => {
    setSelectedProductIds((prev) => prev.filter((id) => id !== productId));
  };

  const clearSelectedProducts = () => {
    setSelectedProductIds([]);
  };

  const getPreviewText = () => {
    const parts: string[] = [];
    const valueNumber = parseNumber(value);
    const minAmountNumber = parseNumber(minAmount);
    
    // Value
    if (type === "bxgy") {
      parts.push(`Compra ${bxgyBuyQty} y lleva ${bxgyGetQty}`);
    } else if (type === "percent") {
      parts.push(`${valueNumber}% de descuento`);
    } else {
      parts.push(`$${valueNumber} de descuento`);
    }
    
    // Applies to
    if (appliesTo === "order") {
      parts.push("en el ticket completo");
    } else if (appliesTo === "categories" && targetCategories.length > 0) {
      parts.push(`en ${targetCategories.join(", ")}`);
    } else if (appliesTo === "products" && selectedProductIds.length > 0) {
      parts.push("en productos seleccionados");
    }
    
    // Days
    const dayNames = days.map(d => DAYS[d]).join(", ");
    if (dayNames) parts.push(`los ${dayNames}`);
    
    // Time
    if (startTime && endTime) {
      parts.push(`de ${startTime} a ${endTime}`);
    }
    
    // Service types
    const services = serviceTypes.map(s => {
      if (s === "dine-in") return "En local";
      if (s === "takeout") return "Para llevar";
      if (s === "delivery") return "Delivery";
      if (s === "kiosk") return "Kiosk";
      return s;
    });
    if (services.length > 0) parts.push(`para ${services.join(", ")}`);
    
    // Min amount
    if (minAmountNumber > 0) {
      parts.push(`cuando el ticket sea ≥ $${minAmountNumber}`);
    }
    
    return `Este descuento aplicará ${parts.join(" ")}.`;
  };

  const isValid = () => {
    const valueNumber = parseNumber(value);
    return (
      name.trim() !== "" &&
      (type === "bxgy" || valueNumber > 0) &&
      days.length > 0 &&
      serviceTypes.length > 0 &&
      (appliesTo !== "categories" || targetCategories.length > 0) &&
      (appliesTo !== "products" || selectedProductIds.length > 0) &&
      (type !== "bxgy" || (bxgyBuyQty > 0 && bxgyGetQty > 0 && Number(bxgyRewardValue) >= 0 && bxgyMaxApplications > 0))
    );
  };

  const handleSave = async () => {
    if (!isValid()) return;
    const categoryIds = categories
      .filter((category) => targetCategories.includes(category.name))
      .map((category) => category.id);
    const serviceTypeKeys = availableServiceTypes
      .filter((service) => isServiceTypeKey(service.key) && serviceTypes.includes(service.key))
      .map((service) => service.key);
    const valueNumber = parseNumber(value);
    const minAmountNumber = parseNumber(minAmount);

    const bxgyConfig = type === "bxgy" ? {
      rules: [
        {
          id: "rule-1",
          buy: {
            qty: bxgyBuyQty,
            selector: {
              mode: appliesTo === "categories" ? "categories" : "products",
              product_ids: appliesTo === "products" ? selectedProductIds : [],
              category_ids: appliesTo === "categories" ? categoryIds : [],
            },
          },
          get: {
            qty: bxgyGetQty,
            selector: {
              mode: appliesTo === "categories" ? "categories" : "products",
              product_ids: appliesTo === "products" ? selectedProductIds : [],
              category_ids: appliesTo === "categories" ? categoryIds : [],
            },
            reward: {
              type: bxgyRewardType,
              value: Number(bxgyRewardValue || 0),
              include_paid_modifiers: bxgyIncludeModifiers,
            },
            apply_to: bxgyApplyTo,
            include_paid_modifiers: bxgyIncludeModifiers,
          },
          limits: {
            max_applications_per_ticket: bxgyMaxApplications,
          },
        },
      ],
      global: {
        exclude_disposables: bxgyExcludeDisposables,
        stacking: stackable ? "allow_with_stackables" : "none",
        overlap_buy_get: false,
      },
    } : undefined;

    const payload = {
      id: editingDiscount ? Number(editingDiscount.id) : 0,
      name,
      description,
      type,
      value: type === "bxgy" ? 0 : valueNumber,
      appliesTo,
      targetCategoryIds: categoryIds,
      targetProductIds: selectedProductIds,
      daysOfWeek: days,
      startTime: startTime || null,
      endTime: endTime || null,
      serviceTypes: serviceTypeKeys,
      minAmount: minAmountNumber,
      autoApply,
      isActive: active,
      priority,
      stackable,
      bxgyConfig,
    };
    if (editingDiscount && Number(editingDiscount.id) > 0) {
      await updateDiscount(Number(editingDiscount.id), payload);
    } else {
      await createDiscount(payload);
    }
    await onSaved();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editingDiscount ? "Editar" : "Nuevo"} descuento
          </DialogTitle>
          <DialogDescription>
            Configura las condiciones de aplicación del descuento
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Section 1: Basic Info */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">Información básica</h3>
            <div className="space-y-3">
              <div>
                <Label htmlFor="discount-name">Nombre del descuento</Label>
                <Input
                  id="discount-name"
                  placeholder="Ej: Happy Hour Tacos"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="discount-description">Descripción (opcional)</Label>
                <Textarea
                  id="discount-description"
                  placeholder="Breve descripción del descuento"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1"
                  rows={2}
                />
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="active"
                  checked={active}
                  onCheckedChange={(checked) => setActive(checked as boolean)}
                />
                <Label htmlFor="active" className="cursor-pointer">
                  Activo
                </Label>
              </div>
            </div>
          </Card>

          {/* Section 2: Discount Type */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">Tipo de descuento</h3>
            <RadioGroup value={type} onValueChange={(value) => { if (isDiscountType(value)) setType(value); }}>
              <div className="grid grid-cols-3 gap-3">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="percent" id="type-percent" />
                  <Label htmlFor="type-percent" className="cursor-pointer">
                    Porcentaje (%)
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="fixed" id="type-fixed" />
                  <Label htmlFor="type-fixed" className="cursor-pointer">
                    Monto fijo
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="bxgy" id="type-bxgy" />
                  <Label htmlFor="type-bxgy" className="cursor-pointer">
                    Compra X / Lleva Y
                  </Label>
                </div>
              </div>
            </RadioGroup>
            <div className="mt-3">
              <Label htmlFor="discount-value">
                {type === "fixed" ? "Monto del descuento" : type === "bxgy" ? "No aplica" : "Porcentaje de descuento"}
              </Label>
              <Input
                id="discount-value"
                type="number"
                min={0}
                max={type === "fixed" ? undefined : type === "bxgy" ? 0 : 100}
                step={type === "fixed" ? 0.01 : 1}
                value={type === "bxgy" ? "0" : value}
                onChange={(e) => setValue(e.target.value)}
                disabled={type === "bxgy"}
                placeholder="0"
                className="mt-1"
              />
            </div>
          </Card>

          {/* Section 3: Application */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">Aplicación</h3>
            <RadioGroup value={appliesTo} onValueChange={(value) => { if (isAppliesTo(value)) setAppliesTo(value); }}>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="order" id="applies-order" />
                  <Label htmlFor="applies-order" className="cursor-pointer">
                    Ticket completo
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="categories" id="applies-categories" />
                  <Label htmlFor="applies-categories" className="cursor-pointer">
                    Categorías específicas
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="products" id="applies-products" />
                  <Label htmlFor="applies-products" className="cursor-pointer">
                    Productos específicos
                  </Label>
                </div>
              </div>
            </RadioGroup>

            {appliesTo === "categories" && (
              <div className="mt-3">
                <Label>Selecciona categorías</Label>
                <div className="flex gap-2 flex-wrap mt-2">
                  {categories.map((category) => (
                    <Badge
                      key={category.id}
                      variant={targetCategories.includes(category.name) ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => toggleCategory(category.name)}
                    >
                      {category.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {appliesTo === "products" && (
              <div className="mt-4 space-y-4">
                <div>
                  <h4 className="font-semibold">Productos</h4>
                  <p className="text-sm text-muted-foreground">
                    Selecciona los productos a los que se aplicará el descuento.
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-[1fr_220px]">
                  <div>
                    <Label htmlFor="product-search">Buscar productos</Label>
                    <Input
                      id="product-search"
                      placeholder="Buscar productos…"
                      value={productSearch}
                      onChange={(e) => setProductSearch(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>Categoría</Label>
                    <Select value={productCategoryId} onValueChange={setProductCategoryId}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Todas las categorías" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Todas las categorías</SelectItem>
                        {categories.map((category) => (
                          <SelectItem key={category.id} value={String(category.id)}>
                            {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    {selectedProductIds.length} seleccionados
                  </span>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const newIds = products.map((product) => product.id);
                        setSelectedProductIds((prev) => {
                          const next = [...prev];
                          newIds.forEach((id) => {
                            if (!next.includes(id)) next.push(id);
                          });
                          return next;
                        });
                        setSelectedProducts((prev) => {
                          const next = { ...prev };
                          products.forEach((product) => {
                            next[product.id] = product;
                          });
                          return next;
                        });
                      }}
                      disabled={products.length === 0}
                    >
                      Seleccionar visibles
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={clearSelectedProducts}
                      disabled={selectedProductIds.length === 0}
                    >
                      Limpiar selección
                    </Button>
                  </div>
                </div>

                <div className="rounded-md border border-border">
                  <div className="max-h-64 overflow-y-auto divide-y divide-border">
                    {productsLoading && (
                      <div className="p-4 text-sm text-muted-foreground">Cargando productos…</div>
                    )}
                    {productsError && (
                      <div className="p-4 text-sm text-destructive">{productsError}</div>
                    )}
                    {!productsLoading && !productsError && products.length === 0 && (
                      <div className="p-4 text-sm text-muted-foreground">
                        No se encontraron productos.
                      </div>
                    )}
                    {!productsError &&
                      products.map((product) => (
                        <label
                          key={product.id}
                          className="flex items-start gap-3 p-3 text-sm hover:bg-muted/40"
                        >
                          <Checkbox
                            checked={selectedProductIds.includes(product.id)}
                            onCheckedChange={() => toggleProductSelection(product)}
                          />
                          <div>
                            <div className="font-medium">{product.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {product.categoryName ?? product.category}
                              {product.price ? ` · $${product.price.toFixed(2)}` : ""}
                            </div>
                          </div>
                        </label>
                      ))}
                  </div>
                  <div className="flex items-center justify-between border-t border-border p-2">
                    <span className="text-xs text-muted-foreground">
                      {products.length} resultados
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setProductPage((prev) => prev + 1)}
                      disabled={!hasMoreProducts || productsLoading}
                    >
                      {hasMoreProducts ? "Cargar más" : "Sin más resultados"}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Seleccionados ({selectedProductIds.length})</Label>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedProductList.length === 0 && (
                      <span className="text-sm text-muted-foreground">
                        Aún no has seleccionado productos.
                      </span>
                    )}
                    {selectedProductList.map((product) => (
                      <Badge
                        key={product.id}
                        variant="secondary"
                        className="flex items-center gap-1 pr-1"
                      >
                        <span>{product.name}</span>
                        <button
                          type="button"
                          className="rounded-full p-1 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={() => removeSelectedProduct(product.id)}
                          aria-label={`Quitar ${product.name}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                  {selectedProductIds.length === 0 && (
                    <p className="text-sm text-destructive">Selecciona al menos un producto.</p>
                  )}
                </div>
              </div>
            )}
          </Card>

          {type === "bxgy" && (
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Regla Compra X / Lleva Y</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Cantidad de compra (X)</Label>
                  <Input type="number" min={1} value={bxgyBuyQty} onChange={(e) => setBxgyBuyQty(Number(e.target.value) || 1)} className="mt-1" />
                </div>
                <div>
                  <Label>Cantidad de regalo (Y)</Label>
                  <Input type="number" min={1} value={bxgyGetQty} onChange={(e) => setBxgyGetQty(Number(e.target.value) || 1)} className="mt-1" />
                </div>
                <div>
                  <Label>Recompensa</Label>
                  <Select value={bxgyRewardType} onValueChange={(value) => { if (isBxgyRewardType(value)) setBxgyRewardType(value); }}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percent">Porcentaje</SelectItem>
                      <SelectItem value="fixed_amount">Monto fijo</SelectItem>
                      <SelectItem value="fixed_price">Precio fijo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Valor de recompensa</Label>
                  <Input type="number" min={0} value={bxgyRewardValue} onChange={(e) => setBxgyRewardValue(e.target.value)} className="mt-1" />
                </div>
                <div>
                  <Label>Aplicar al</Label>
                  <Select value={bxgyApplyTo} onValueChange={(value) => { if (isBxgyApplyTo(value)) setBxgyApplyTo(value); }}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cheapest">Más barato</SelectItem>
                      <SelectItem value="most_expensive">Más caro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Máx. aplicaciones por ticket</Label>
                  <Input type="number" min={1} value={bxgyMaxApplications} onChange={(e) => setBxgyMaxApplications(Number(e.target.value) || 1)} className="mt-1" />
                </div>
              </div>
              <div className="mt-3 space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox id="bxgy-mods" checked={bxgyIncludeModifiers} onCheckedChange={(c) => setBxgyIncludeModifiers(Boolean(c))} />
                  <Label htmlFor="bxgy-mods">Incluir modificadores de pago</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="bxgy-disposable" checked={bxgyExcludeDisposables} onCheckedChange={(c) => setBxgyExcludeDisposables(Boolean(c))} />
                  <Label htmlFor="bxgy-disposable">Excluir desechables del descuento</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="discount-stackable" checked={stackable} onCheckedChange={(c) => setStackable(Boolean(c))} />
                  <Label htmlFor="discount-stackable">Acumulable con otros descuentos</Label>
                </div>
                <div>
                  <Label>Prioridad</Label>
                  <Input type="number" value={priority} onChange={(e) => setPriority(Number(e.target.value) || 100)} className="mt-1 max-w-[180px]" />
                </div>
              </div>
            </Card>
          )}

          {/* Section 4: Conditions */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">Condiciones de activación</h3>
            <div className="space-y-4">
              <div>
                <Label>Días de la semana</Label>
                <div className="flex gap-2 mt-2">
                  {DAYS.map((day, index) => (
                    <Button
                      key={index}
                      variant={days.includes(index) ? "default" : "outline"}
                      size="sm"
                      onClick={() => toggleDay(index)}
                      className="w-12"
                    >
                      {DAYS_SHORT[index]}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label htmlFor="start-time">Desde</Label>
                  <div className="relative mt-1">
                    <Input
                      ref={startTimeRef}
                      id="start-time"
                      type="time"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="pr-12 time-input"
                    />
                    <button
                      type="button"
                      onClick={() => focusTimeInput(startTimeRef)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md border border-border bg-background/80 p-1 text-foreground shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label="Seleccionar hora de inicio"
                    >
                      <Clock className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div>
                  <Label htmlFor="end-time">Hasta</Label>
                  <div className="relative mt-1">
                    <Input
                      ref={endTimeRef}
                      id="end-time"
                      type="time"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      className="pr-12 time-input"
                    />
                    <button
                      type="button"
                      onClick={() => focusTimeInput(endTimeRef)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md border border-border bg-background/80 p-1 text-foreground shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label="Seleccionar hora de fin"
                    >
                      <Clock className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>

              <div>
                <Label>Tipo de servicio</Label>
                <div className="flex gap-2 flex-wrap mt-2">
                  {availableServiceTypes.map((service) => (
                    <Badge
                      key={service.id}
                      variant={isServiceTypeKey(service.key) && serviceTypes.includes(service.key) ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => { if (isServiceTypeKey(service.key)) toggleServiceType(service.key); }}
                    >
                      {service.label}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <Label htmlFor="min-amount">Monto mínimo de ticket (opcional)</Label>
                <Input
                  id="min-amount"
                  type="number"
                  min={0}
                  step={0.01}
                  value={minAmount}
                  onChange={(e) => setMinAmount(e.target.value)}
                  placeholder="0"
                  className="mt-1"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="auto-apply"
                    checked={autoApply}
                    onCheckedChange={(checked) => setAutoApply(checked as boolean)}
                  />
                  <Label htmlFor="auto-apply" className="cursor-pointer">
                    Aplicar automáticamente cuando se cumplan las condiciones
                  </Label>
                </div>
              </div>
            </div>
          </Card>

          {/* Section 5: Preview */}
          <Card className="p-4 bg-muted/50">
            <h3 className="font-semibold mb-2">Vista previa de aplicación</h3>
            <p className="text-sm text-muted-foreground">{getPreviewText()}</p>
          </Card>
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">
            Cancelar
          </Button>
          <Button
            onClick={handleSave}
            disabled={!isValid()}
            className="flex-1 bg-secondary hover:bg-secondary/90"
          >
            Guardar descuento
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
