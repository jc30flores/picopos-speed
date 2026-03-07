import { useMemo, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ImageUploadField } from "@/components/ui/image-upload-field";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import {
  Category,
  Product,
  ProductSpecialPriceRule,
  ServiceType,
  createCategory,
  createProduct,
  createProductSpecialPrice,
  deleteProductSpecialPrice,
  getCategories,
  getServiceTypes,
  listProductSpecialPrices,
  updateProduct,
  updateProductSpecialPrice,
} from "@/lib/api";
import { toast } from "sonner";

interface ProductFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingProduct?: Product | null;
  categories: Category[];
  onSaved: () => Promise<void>;
}

const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

type RuleDraft = Omit<ProductSpecialPriceRule, "id" | "productId">;

const emptyRule = (): RuleDraft => ({
  name: "",
  isActive: true,
  priority: 0,
  discountType: "FIXED_PRICE",
  fixedPrice: null,
  percentOff: null,
  daysOfWeek: [],
  startTime: null,
  endTime: null,
  startDate: null,
  endDate: null,
  appliesToAllOrderTypes: true,
  orderTypeIds: [],
});

export const ProductFormDialog = ({
  open,
  onOpenChange,
  editingProduct,
  categories,
  onSaved,
}: ProductFormDialogProps) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [categoryOptions, setCategoryOptions] = useState<Category[]>(categories);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [isFetchingCategories, setIsFetchingCategories] = useState(false);
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [existingImageUrl, setExistingImageUrl] = useState<string | null>(null);
  const [localImageUrl, setLocalImageUrl] = useState<string | null>(null);
  const [available, setAvailable] = useState(true);
  const [requiresKitchen, setRequiresKitchen] = useState(false);
  const [disposableFee, setDisposableFee] = useState("0");
  const [disposableApplyTo, setDisposableApplyTo] = useState<string[]>([]);

  const [serviceTypes, setServiceTypes] = useState<ServiceType[]>([]);
  const [specialRules, setSpecialRules] = useState<ProductSpecialPriceRule[]>([]);
  const [ruleOpen, setRuleOpen] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>(emptyRule());

  useEffect(() => {
    if (editingProduct) {
      setName(editingProduct.name);
      setDescription(editingProduct.description);
      setPrice(editingProduct.price ? String(editingProduct.price) : "");
      setCategoryQuery(editingProduct.category);
      setSelectedCategoryId(editingProduct.categoryId);
      setImageFile(null);
      setExistingImageUrl(editingProduct.imageUrl ?? null);
      setAvailable(editingProduct.available);
      setRequiresKitchen(editingProduct.requiresKitchen);
      setDisposableFee(String(editingProduct.disposableFee ?? 0));
      setDisposableApplyTo(editingProduct.disposableApplyTo ?? []);
    } else {
      setName("");
      setDescription("");
      setPrice("");
      setCategoryQuery("");
      setSelectedCategoryId(null);
      setImageFile(null);
      setExistingImageUrl(null);
      setAvailable(true);
      setRequiresKitchen(false);
      setDisposableFee("0");
      setDisposableApplyTo([]);
    }
  }, [editingProduct, open]);

  useEffect(() => {
    if (!open) return;
    getServiceTypes()
      .then((data) => setServiceTypes((data || []).filter((item) => item.isActive !== false)))
      .catch(() => setServiceTypes([]));
  }, [open]);

  useEffect(() => {
    if (!open || !editingProduct) {
      setSpecialRules([]);
      return;
    }
    listProductSpecialPrices(editingProduct.id)
      .then(setSpecialRules)
      .catch(() => setSpecialRules([]));
  }, [open, editingProduct]);

  useEffect(() => {
    if (!imageFile) {
      setLocalImageUrl(null);
      return;
    }
    const previewUrl = URL.createObjectURL(imageFile);
    setLocalImageUrl(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [imageFile]);

  useEffect(() => {
    const handler = window.setTimeout(async () => {
      setIsFetchingCategories(true);
      try {
        const data = await getCategories(categoryQuery.trim() || undefined);
        setCategoryOptions(data);
      } finally {
        setIsFetchingCategories(false);
      }
    }, 300);
    return () => window.clearTimeout(handler);
  }, [categoryQuery]);

  useEffect(() => {
    if (!categoryQuery.trim()) {
      setCategoryOptions(categories);
    }
  }, [categories, categoryQuery]);

  const selectedCategoryName = useMemo(() => {
    if (selectedCategoryId) {
      return (
        categoryOptions.find((cat) => cat.id === selectedCategoryId)?.name ||
        categories.find((cat) => cat.id === selectedCategoryId)?.name ||
        ""
      );
    }
    return "";
  }, [categoryOptions, categories, selectedCategoryId]);

  const canCreateCategory = useMemo(() => {
    const normalized = categoryQuery.trim().toUpperCase();
    if (!normalized) return false;
    return !categoryOptions.some((cat) => cat.name.toUpperCase() === normalized);
  }, [categoryOptions, categoryQuery]);

  const isValid = () => {
    const parsed = price === "" ? NaN : Number(price);
    return name.trim() !== "" && selectedCategoryId !== null && Number.isFinite(parsed) && parsed > 0;
  };

  const previewUrl = localImageUrl ?? existingImageUrl;

  const handleSave = async () => {
    if (!isValid()) return;
    const parsedPrice = price === "" ? NaN : Number(price);
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) return;

    if (editingProduct) {
      await updateProduct(editingProduct.id, {
        name,
        description,
        price: parsedPrice,
        categoryId: selectedCategoryId ?? 0,
        image: imageFile,
        available,
        requiresKitchen,
        disposableFee: Number(disposableFee || 0),
        disposableApplyTo,
      });
    } else {
      await createProduct({
        name,
        description,
        price: parsedPrice,
        categoryId: selectedCategoryId ?? 0,
        image: imageFile,
        available,
        requiresKitchen,
        disposableFee: Number(disposableFee || 0),
        disposableApplyTo,
      });
    }
    await onSaved();
    onOpenChange(false);
  };

  const handleSelectCategory = (categoryItem: Category) => {
    setSelectedCategoryId(categoryItem.id);
    setCategoryQuery(categoryItem.name);
    setCategoryOpen(false);
  };

  const handleCreateCategory = async () => {
    const normalized = categoryQuery.trim().toUpperCase();
    if (!normalized || isCreatingCategory) return;
    setIsCreatingCategory(true);
    try {
      const created = await createCategory(normalized);
      setCategoryOptions((prev) => (prev.some((cat) => cat.id === created.id) ? prev : [...prev, created]));
      setSelectedCategoryId(created.id);
      setCategoryQuery(created.name);
      setCategoryOpen(false);
    } finally {
      setIsCreatingCategory(false);
    }
  };

  const openRuleEditor = (rule?: ProductSpecialPriceRule) => {
    if (rule) {
      setEditingRuleId(rule.id);
      setRuleDraft({
        name: rule.name ?? "",
        isActive: rule.isActive,
        priority: rule.priority,
        discountType: rule.discountType,
        fixedPrice: rule.fixedPrice ?? null,
        percentOff: rule.percentOff ?? null,
        daysOfWeek: rule.daysOfWeek ?? [],
        startTime: rule.startTime ?? null,
        endTime: rule.endTime ?? null,
        startDate: rule.startDate ?? null,
        endDate: rule.endDate ?? null,
        appliesToAllOrderTypes: rule.appliesToAllOrderTypes,
        orderTypeIds: rule.orderTypeIds ?? [],
      });
    } else {
      setEditingRuleId(null);
      setRuleDraft(emptyRule());
    }
    setRuleOpen(true);
  };

  const saveRule = async () => {
    if (!editingProduct) {
      toast.error("Guarda el producto primero para agregar reglas.");
      return;
    }
    if (ruleDraft.discountType === "FIXED_PRICE" && (ruleDraft.fixedPrice == null || Number(ruleDraft.fixedPrice) < 0)) {
      toast.error("Precio fijo inválido.");
      return;
    }
    if (ruleDraft.discountType === "PERCENT_OFF" && (ruleDraft.percentOff == null || Number(ruleDraft.percentOff) < 0 || Number(ruleDraft.percentOff) > 100)) {
      toast.error("Porcentaje debe estar entre 0 y 100.");
      return;
    }
    if (ruleDraft.startDate && ruleDraft.endDate && ruleDraft.startDate > ruleDraft.endDate) {
      toast.error("Rango de fechas inválido.");
      return;
    }

    if (editingRuleId) {
      await updateProductSpecialPrice(editingRuleId, ruleDraft);
    } else {
      await createProductSpecialPrice(editingProduct.id, ruleDraft);
    }
    setSpecialRules(await listProductSpecialPrices(editingProduct.id));
    setRuleOpen(false);
  };

  const removeRule = async (ruleId: number) => {
    if (!editingProduct) return;
    await deleteProductSpecialPrice(ruleId);
    setSpecialRules(await listProductSpecialPrices(editingProduct.id));
  };

  const formatRuleSummary = (rule: ProductSpecialPriceRule) => {
    const priceText = rule.discountType === "FIXED_PRICE" ? `Precio $${Number(rule.fixedPrice ?? 0).toFixed(2)}` : `${Number(rule.percentOff ?? 0)}% off`;
    const daysText = rule.daysOfWeek.length ? `Días: ${rule.daysOfWeek.map((d) => DAYS[d]).join(", ")}` : "Días: Todos";
    const orderTypesText = rule.appliesToAllOrderTypes
      ? "Tipos: Todos"
      : `Tipos: ${serviceTypes.filter((s) => rule.orderTypeIds.includes(s.id)).map((s) => s.label).join(", ") || "Ninguno"}`;
    return `${priceText} · ${daysText} · ${orderTypesText}`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[96vw] max-w-5xl max-h-[90vh] overflow-hidden p-0">
        <div className="flex h-[90vh] max-h-[90vh] flex-col overflow-hidden">
          <DialogHeader className="border-b px-4 py-3 sm:px-6">
            <DialogTitle>{editingProduct ? "Editar" : "Nuevo"} producto</DialogTitle>
            <DialogDescription>Configura la información del producto</DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <Label htmlFor="product-name">Nombre del producto</Label>
                <Input id="product-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="product-description">Descripción</Label>
                <Textarea id="product-description" value={description} onChange={(e) => setDescription(e.target.value)} className="mt-1" rows={3} />
              </div>
              <div>
                <Label htmlFor="product-price">Precio</Label>
                <Input id="product-price" inputMode="decimal" value={price} onChange={(e) => /^\d*\.?\d*$/.test(e.target.value) || e.target.value === "" ? setPrice(e.target.value) : null} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="product-category">Categoría</Label>
                <Popover open={categoryOpen} onOpenChange={setCategoryOpen}>
                  <PopoverTrigger asChild>
                    <Button variant="outline" role="combobox" className="mt-1 w-full justify-between">{selectedCategoryName || "Selecciona categoría"}</Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[320px] p-0" align="start">
                    <Command shouldFilter={false}>
                      <CommandInput value={categoryQuery} onValueChange={(value) => { setCategoryQuery(value.toUpperCase()); setSelectedCategoryId(null); }} />
                      <CommandList>
                        {isFetchingCategories && <CommandItem disabled>Buscando categorías...</CommandItem>}
                        {!isFetchingCategories && categoryOptions.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">Sin coincidencias</div>}
                        {categoryOptions.length > 0 && <CommandGroup heading="Categorías">{categoryOptions.map((cat) => <CommandItem key={cat.id} value={cat.name} onSelect={() => handleSelectCategory(cat)}>{cat.name}</CommandItem>)}</CommandGroup>}
                        {canCreateCategory && <><CommandSeparator /><CommandGroup heading="Crear"><CommandItem onSelect={handleCreateCategory}>{isCreatingCategory ? "Creando categoría..." : `Crear categoría: ${categoryQuery.trim().toUpperCase()}`}</CommandItem></CommandGroup></>}
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>

              <div className="md:col-span-2">
                <ImageUploadField id="product-image" label="Imagen del producto" file={imageFile} previewUrl={previewUrl} onChange={setImageFile} />
              </div>
              {previewUrl && (
                <div className="md:col-span-2">
                  <Label className="text-sm">Vista previa</Label>
                  <div className="mt-2 rounded-lg border p-2">
                    <div className="mx-auto aspect-square max-h-48 w-full max-w-48 overflow-hidden rounded-md bg-muted/30">
                      <img src={previewUrl} alt="Vista previa del producto" className="h-full w-full object-contain" />
                    </div>
                  </div>
                </div>
              )}

              <div>
                <Label htmlFor="disposable-fee">Desechables (por unidad)</Label>
                <Input id="disposable-fee" type="number" min="0" step="0.01" value={disposableFee} onChange={(e) => setDisposableFee(e.target.value)} className="mt-1" />
              </div>

              <div className="space-y-2 pt-1">
                <Label>Aplicar desechables en</Label>
                {[{ key: "MESA", label: "Mesa" }, { key: "PARA_LLEVAR", label: "Para llevar" }, { key: "PEDIDOS_YA", label: "Pedidos Ya" }].map((item) => (
                  <div key={item.key} className="flex items-center space-x-2">
                    <Checkbox id={`disposable-${item.key}`} checked={disposableApplyTo.includes(item.key)} onCheckedChange={(checked) => setDisposableApplyTo((prev) => checked ? [...new Set([...prev, item.key])] : prev.filter((value) => value !== item.key))} />
                    <Label htmlFor={`disposable-${item.key}`}>{item.label}</Label>
                  </div>
                ))}
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <Checkbox id="requires-kitchen" checked={requiresKitchen} onCheckedChange={(checked) => setRequiresKitchen(checked as boolean)} />
                <Label htmlFor="requires-kitchen" className="cursor-pointer">Va a cocina</Label>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <Checkbox id="available" checked={available} onCheckedChange={(checked) => setAvailable(checked as boolean)} />
                <Label htmlFor="available" className="cursor-pointer">Disponible</Label>
              </div>

              <div className="md:col-span-2 space-y-3 rounded-xl border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">Precios especiales</p>
                    <p className="text-xs text-muted-foreground">Reglas por día/hora/fecha y tipo de pedido</p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => openRuleEditor()} disabled={!editingProduct}>Nuevo precio especial</Button>
                </div>
                {!editingProduct ? (
                  <p className="text-sm text-muted-foreground">Guarda el producto para gestionar reglas especiales.</p>
                ) : specialRules.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sin reglas configuradas.</p>
                ) : (
                  <div className="space-y-2">
                    {specialRules.map((rule) => (
                      <div key={rule.id} className="rounded-lg border p-2">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold">{rule.name || `Regla #${rule.id}`}</p>
                            <p className="text-xs text-muted-foreground">{formatRuleSummary(rule)}</p>
                          </div>
                          <div className="flex gap-2">
                            <Button type="button" size="sm" variant="outline" onClick={() => openRuleEditor(rule)}>Editar</Button>
                            <Button type="button" size="sm" variant="destructive" onClick={() => removeRule(rule.id)}>Eliminar</Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="sticky bottom-0 border-t bg-background px-4 py-3 sm:px-6">
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">Cancelar</Button>
              <Button onClick={handleSave} disabled={!isValid()} className="flex-1 bg-secondary hover:bg-secondary/90">Guardar producto</Button>
            </div>
          </div>
        </div>
      </DialogContent>

      <Dialog open={ruleOpen} onOpenChange={setRuleOpen}>
        <DialogContent className="max-w-2xl p-0">
          <div className="flex max-h-[90vh] flex-col">
            <DialogHeader className="border-b px-6 py-4 pr-12">
              <DialogTitle>{editingRuleId ? "Editar" : "Nuevo"} precio especial</DialogTitle>
              <DialogDescription>
                Configura reglas por días, horas, fechas y tipos de pedido.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 overflow-y-auto overflow-x-visible px-6 py-4">
            <div>
              <Label>Nombre (opcional)</Label>
              <Input value={ruleDraft.name ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, name: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Tipo</Label>
                <select className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={ruleDraft.discountType} onChange={(e) => setRuleDraft((prev) => ({ ...prev, discountType: e.target.value as RuleDraft["discountType"] }))}>
                  <option value="FIXED_PRICE">Precio fijo</option>
                  <option value="PERCENT_OFF">% descuento</option>
                </select>
              </div>
              <div>
                {ruleDraft.discountType === "FIXED_PRICE" ? (
                  <>
                    <Label>Precio fijo</Label>
                    <Input type="number" step="0.01" min="0" value={ruleDraft.fixedPrice ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, fixedPrice: e.target.value === "" ? null : Number(e.target.value) }))} />
                  </>
                ) : (
                  <>
                    <Label>% descuento</Label>
                    <Input type="number" step="0.01" min="0" max="100" value={ruleDraft.percentOff ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, percentOff: e.target.value === "" ? null : Number(e.target.value) }))} />
                  </>
                )}
              </div>
            </div>
            <div>
              <Label>Días</Label>
              <div className="mt-1 flex flex-wrap gap-2">
                {DAYS.map((label, idx) => {
                  const active = ruleDraft.daysOfWeek.includes(idx);
                  return <Button key={label} type="button" size="sm" variant={active ? "default" : "outline"} onClick={() => setRuleDraft((prev) => ({ ...prev, daysOfWeek: active ? prev.daysOfWeek.filter((v) => v !== idx) : [...prev.daysOfWeek, idx] }))}>{label}</Button>;
                })}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label>Hora inicio</Label><Input type="time" value={ruleDraft.startTime ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, startTime: e.target.value || null }))} /></div>
              <div><Label>Hora fin</Label><Input type="time" value={ruleDraft.endTime ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, endTime: e.target.value || null }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label>Fecha inicio</Label><Input type="date" value={ruleDraft.startDate ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, startDate: e.target.value || null }))} /></div>
              <div><Label>Fecha fin</Label><Input type="date" value={ruleDraft.endDate ?? ""} onChange={(e) => setRuleDraft((prev) => ({ ...prev, endDate: e.target.value || null }))} /></div>
            </div>
            <div>
              <Label>Prioridad</Label>
              <Input type="number" value={ruleDraft.priority} onChange={(e) => setRuleDraft((prev) => ({ ...prev, priority: Number(e.target.value || 0) }))} />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox checked={ruleDraft.appliesToAllOrderTypes} onCheckedChange={(checked) => setRuleDraft((prev) => ({ ...prev, appliesToAllOrderTypes: Boolean(checked), orderTypeIds: Boolean(checked) ? [] : prev.orderTypeIds }))} id="rule-all-order-types" />
              <Label htmlFor="rule-all-order-types">Aplica a todos los tipos de pedido</Label>
            </div>
            {!ruleDraft.appliesToAllOrderTypes && (
              <div className="space-y-2">
                {serviceTypes.map((type) => (
                  <div key={type.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`rule-type-${type.id}`}
                      checked={ruleDraft.orderTypeIds.includes(type.id)}
                      onCheckedChange={(checked) => {
                        setRuleDraft((prev) => ({
                          ...prev,
                          orderTypeIds: checked ? [...new Set([...prev.orderTypeIds, type.id])] : prev.orderTypeIds.filter((id) => id !== type.id),
                        }));
                      }}
                    />
                    <Label htmlFor={`rule-type-${type.id}`}>{type.label}</Label>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2">
              <Checkbox checked={ruleDraft.isActive} onCheckedChange={(checked) => setRuleDraft((prev) => ({ ...prev, isActive: Boolean(checked) }))} id="rule-active" />
              <Label htmlFor="rule-active">Regla activa</Label>
            </div>
            <div className="flex gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setRuleOpen(false)} className="flex-1">Cancelar</Button>
              <Button type="button" onClick={saveRule} className="flex-1">Guardar regla</Button>
            </div>
          </div>
          </div>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
};
