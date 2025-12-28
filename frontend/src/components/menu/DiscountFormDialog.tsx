import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Discount } from "@/types/menu";
import { Category, ServiceType, createDiscount } from "@/lib/api";

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
  const [type, setType] = useState<"percentage" | "fixed" | "happy-hour" | "category">("percentage");
  const [value, setValue] = useState(0);
  const [appliesTo, setAppliesTo] = useState<"ticket" | "categories" | "products">("ticket");
  const [targetCategories, setTargetCategories] = useState<string[]>([]);
  const [days, setDays] = useState<number[]>([]);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [serviceTypes, setServiceTypes] = useState<("dine-in" | "takeout" | "delivery" | "kiosk")[]>([]);
  const [minAmount, setMinAmount] = useState(0);
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [autoApply, setAutoApply] = useState(true);

  useEffect(() => {
    if (editingDiscount) {
      setName(editingDiscount.name);
      setDescription(editingDiscount.description || "");
      setActive(editingDiscount.active);
      setType(editingDiscount.type);
      setValue(editingDiscount.value);
      setAppliesTo(editingDiscount.appliesTo);
      setTargetCategories(editingDiscount.targetCategories || []);
      setDays(editingDiscount.days);
      setStartTime(editingDiscount.startTime || "");
      setEndTime(editingDiscount.endTime || "");
      setServiceTypes(editingDiscount.serviceTypes);
      setMinAmount(editingDiscount.minAmount || 0);
      setRequiresApproval(editingDiscount.requiresApproval);
      setAutoApply(editingDiscount.autoApply);
    } else {
      // Reset form
      setName("");
      setDescription("");
      setActive(true);
      setType("percentage");
      setValue(0);
      setAppliesTo("ticket");
      setTargetCategories([]);
      setDays([]);
      setStartTime("");
      setEndTime("");
      setServiceTypes([]);
      setMinAmount(0);
      setRequiresApproval(false);
      setAutoApply(true);
    }
  }, [editingDiscount, open]);

  const toggleDay = (dayIndex: number) => {
    if (days.includes(dayIndex)) {
      setDays(days.filter((d) => d !== dayIndex));
    } else {
      setDays([...days, dayIndex]);
    }
  };

  const toggleServiceType = (service: "dine-in" | "takeout" | "delivery" | "kiosk") => {
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

  const getPreviewText = () => {
    const parts: string[] = [];
    
    // Value
    if (type === "percentage" || type === "happy-hour") {
      parts.push(`${value}% de descuento`);
    } else {
      parts.push(`$${value} de descuento`);
    }
    
    // Applies to
    if (appliesTo === "ticket") {
      parts.push("en el ticket completo");
    } else if (appliesTo === "categories" && targetCategories.length > 0) {
      parts.push(`en ${targetCategories.join(", ")}`);
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
    if (minAmount > 0) {
      parts.push(`cuando el ticket sea ≥ $${minAmount}`);
    }
    
    return `Este descuento aplicará ${parts.join(" ")}.`;
  };

  const isValid = () => {
    return (
      name.trim() !== "" &&
      value > 0 &&
      days.length > 0 &&
      serviceTypes.length > 0 &&
      (appliesTo !== "categories" || targetCategories.length > 0)
    );
  };

  const handleSave = async () => {
    if (!isValid()) return;
    const categoryIds = categories
      .filter((category) => targetCategories.includes(category.name))
      .map((category) => category.id);
    const serviceTypeIds = availableServiceTypes
      .filter((service) => serviceTypes.includes(service.key as any))
      .map((service) => service.id);

    await createDiscount({
      id: editingDiscount ? Number(editingDiscount.id) : 0,
      name,
      description,
      type,
      value,
      appliesTo,
      targetCategoryIds: categoryIds,
      targetProductIds: [],
      days,
      startTime: startTime || null,
      endTime: endTime || null,
      serviceTypeIds,
      minAmount,
      requiresApproval,
      autoApply,
      active,
    });
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
            <RadioGroup value={type} onValueChange={(v: any) => setType(v)}>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="percentage" id="type-percentage" />
                  <Label htmlFor="type-percentage" className="cursor-pointer">
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
                  <RadioGroupItem value="happy-hour" id="type-happy-hour" />
                  <Label htmlFor="type-happy-hour" className="cursor-pointer">
                    Happy Hour
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="category" id="type-category" />
                  <Label htmlFor="type-category" className="cursor-pointer">
                    Por categoría
                  </Label>
                </div>
              </div>
            </RadioGroup>
            <div className="mt-3">
              <Label htmlFor="discount-value">
                {type === "fixed" ? "Monto del descuento" : "Porcentaje de descuento"}
              </Label>
              <Input
                id="discount-value"
                type="number"
                min={0}
                max={type === "fixed" ? undefined : 100}
                step={type === "fixed" ? 0.01 : 1}
                value={value}
                onChange={(e) => setValue(parseFloat(e.target.value) || 0)}
                className="mt-1"
              />
            </div>
          </Card>

          {/* Section 3: Application */}
          <Card className="p-4">
            <h3 className="font-semibold mb-3">Aplicación</h3>
            <RadioGroup value={appliesTo} onValueChange={(v: any) => setAppliesTo(v)}>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="ticket" id="applies-ticket" />
                  <Label htmlFor="applies-ticket" className="cursor-pointer">
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
          </Card>

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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="start-time">Desde</Label>
                  <Input
                    id="start-time"
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="end-time">Hasta</Label>
                  <Input
                    id="end-time"
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>

              <div>
                <Label>Tipo de servicio</Label>
                <div className="flex gap-2 flex-wrap mt-2">
                  {availableServiceTypes.map((service) => (
                    <Badge
                      key={service.id}
                      variant={serviceTypes.includes(service.key as any) ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => toggleServiceType(service.key as any)}
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
                  onChange={(e) => setMinAmount(parseFloat(e.target.value) || 0)}
                  className="mt-1"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="requires-approval"
                    checked={requiresApproval}
                    onCheckedChange={(checked) => setRequiresApproval(checked as boolean)}
                  />
                  <Label htmlFor="requires-approval" className="cursor-pointer">
                    Requiere aprobación de supervisor
                  </Label>
                </div>
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
