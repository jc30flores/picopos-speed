import { Navigation } from "@/components/Navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, Trash2, ShoppingCart } from "lucide-react";
import { cn } from "@/lib/utils";
import { calculateCartTotals, formatMoney, toNumber } from "@/lib/money";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createOrder,
  createPayment,
  getOrderById,
  createPrintJob,
  markPrintJobPrinted,
  getActiveTaxConfig,
  getCategories,
  getModifierGroups,
  getProducts,
  Category,
  ModifierGroup,
  Product,
  PaymentMethod,
  Order,
  PrintJob,
} from "@/lib/api";
import { toast } from "sonner";
import { PrintPreviewDialog } from "@/components/printing/PrintPreviewDialog";

interface CartItem {
  id: string;
  productId: number;
  name: string;
  price: number;
  quantity: number;
  modifiers: Array<{ name: string; price: number }>;
}

const POS = () => {
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [serviceType, setServiceType] = useState<"dine-in" | "takeout" | "delivery">("dine-in");
  const [showModifierDialog, setShowModifierDialog] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [taxRate, setTaxRate] = useState(0.13);
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [tipAmount, setTipAmount] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [receiptJob, setReceiptJob] = useState<PrintJob | null>(null);
  const [isReceiptPreviewOpen, setIsReceiptPreviewOpen] = useState(false);

  const loadMenuData = async () => {
    const [categoriesResponse, productsResponse, modifierGroupsResponse] = await Promise.all([
      getCategories(),
      getProducts(),
      getModifierGroups(),
    ]);
    setCategories(categoriesResponse);
    setProducts(productsResponse);
    setModifierGroups(modifierGroupsResponse);
  };

  useEffect(() => {
    loadMenuData().catch((error) => {
      console.error("Failed to load menu data", error);
    });
    getActiveTaxConfig()
      .then((config) => setTaxRate(config.rate))
      .catch((error) => {
        console.error("Failed to load tax config", error);
      });
  }, []);

  const filteredProducts = products.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch && product.available;
  });

  const handleProductClick = (product: Product) => {
    if (product.modifierGroups && product.modifierGroups.length > 0) {
      setSelectedProduct(product);
      setSelectedModifiers({});
      setShowModifierDialog(true);
    } else {
      addToCart(product, []);
    }
  };

  const addToCart = (product: Product, modifiers: Array<{ name: string; price: number }>) => {
    const modifierPrice = modifiers.reduce((sum, mod) => sum + mod.price, 0);
    const totalPrice = product.price + modifierPrice;

    const existingItemIndex = cart.findIndex(
      (item) =>
        item.productId === product.id &&
        JSON.stringify(item.modifiers) === JSON.stringify(modifiers)
    );

    if (existingItemIndex >= 0) {
      const newCart = [...cart];
      newCart[existingItemIndex].quantity += 1;
      setCart(newCart);
    } else {
      setCart([
        ...cart,
        {
          id: `${product.id}-${Date.now()}`,
          productId: product.id,
          name: product.name,
          price: totalPrice,
          quantity: 1,
          modifiers,
        },
      ]);
    }
    setShowModifierDialog(false);
  };

  const updateQuantity = (itemId: string, delta: number) => {
    setCart(
      cart
        .map((item) =>
          item.id === itemId ? { ...item, quantity: item.quantity + delta } : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeItem = (itemId: string) => {
    setCart(cart.filter((item) => item.id !== itemId));
  };

  const { subtotal, tax, total } = calculateCartTotals(cart, taxRate);
  const paymentTotal = cart.length > 0 ? total : toNumber(activeOrder?.total);

  const handleCheckout = async () => {
    if (cart.length === 0) return;
    setIsProcessingPayment(true);
    try {
      const order = await createOrder({
        serviceType,
        items: cart.map((item) => ({
          productId: item.productId,
          productName: item.name,
          price: item.price,
          quantity: item.quantity,
          modifiers: item.modifiers,
        })),
      });
      setActiveOrder(order);
      setCart([]);
      setPaymentAmount(order.remaining.toFixed(2));
      setTipAmount("0");
      setPaymentReference("");
      setIsPaymentOpen(true);
      toast.success(`Pedido #${order.orderNumber} creado · Total $${order.total.toFixed(2)}`);
    } catch (error) {
      console.error("Failed to create order", error);
      toast.error("No se pudo crear el pedido. Intenta de nuevo.");
    } finally {
      setIsProcessingPayment(false);
    }
  };

  const handleAddModifiers = () => {
    const selectedMods: Array<{ name: string; price: number }> = [];
    
    selectedProduct.modifierGroups.forEach((groupId: string) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (group && selectedModifiers[groupId]) {
        selectedModifiers[groupId].forEach((modId) => {
          const mod = group.modifiers.find((m) => String(m.id) === modId);
          if (mod) selectedMods.push({ name: mod.name, price: mod.price });
        });
      }
    });

    addToCart(selectedProduct, selectedMods);
  };

  const canAddToCart = () => {
    if (!selectedProduct?.modifierGroups) return true;
    
    return selectedProduct.modifierGroups.every((groupId: string) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (!group) return true;
      
      const selectedCount = selectedModifiers[groupId]?.length || 0;
      return selectedCount >= group.minSelection && selectedCount <= group.maxSelection;
    });
  };

  const handleSubmitPayment = async () => {
    if (!activeOrder) return;
    const amountValue = Number(paymentAmount);
    const tipValue = Number(tipAmount);
    const totalPayment = amountValue + tipValue;

    if (!amountValue || amountValue <= 0) {
      toast.error("Ingresa un monto válido");
      return;
    }
    if (tipValue < 0) {
      toast.error("La propina no puede ser negativa");
      return;
    }
    if (totalPayment > activeOrder.remaining) {
      toast.error("El pago supera el saldo pendiente");
      return;
    }

    try {
      setIsProcessingPayment(true);
      await createPayment({
        orderId: activeOrder.id,
        method: paymentMethod,
        amount: amountValue,
        tipAmount: tipValue,
        reference: paymentReference || undefined,
      });
      const refreshed = await getOrderById(activeOrder.id);
      setActiveOrder(refreshed);
      setPaymentAmount(refreshed.remaining.toFixed(2));
      setTipAmount("0");
      setPaymentReference("");
      if (refreshed.paymentStatus === "paid") {
        toast.success("Pago completado");
        setIsPaymentOpen(false);
      } else {
        toast.success("Pago registrado");
      }
    } catch (error) {
      console.error("Failed to create payment", error);
      toast.error("No se pudo registrar el pago");
    } finally {
      setIsProcessingPayment(false);
    }
  };

  const handlePrintReceipt = async () => {
    if (!activeOrder) return;
    try {
      const job = await createPrintJob({ orderId: activeOrder.id, type: "customer" });
      setReceiptJob(job);
      setIsReceiptPreviewOpen(true);
    } catch (error) {
      console.error("Failed to create print job", error);
      toast.error("No se pudo generar el ticket");
    }
  };

  const handleMarkPrinted = async () => {
    if (!receiptJob) return;
    try {
      const job = await markPrintJobPrinted(receiptJob.id);
      setReceiptJob(job);
      toast.success("Ticket marcado como impreso");
    } catch (error) {
      console.error("Failed to mark printed", error);
      toast.error("No se pudo actualizar el ticket");
    }
  };

  const handleReprint = async () => {
    if (!activeOrder) return;
    await handlePrintReceipt();
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <div className="pt-20 px-2 lg:px-4 pb-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:h-[calc(100vh-6rem)]">
          {/* Products Section */}
          <div className="lg:col-span-2 flex flex-col gap-4 h-auto lg:overflow-hidden">
            {/* Search & Filters */}
            <Card className="p-4">
              <div className="flex flex-col gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar productos..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                
                <div className="flex gap-2 flex-wrap">
                  {["Todos", ...categories.map((cat) => cat.name)].map((cat) => (
                    <Badge
                      key={cat}
                      variant={selectedCategory === cat ? "default" : "outline"}
                      className={cn(
                        "cursor-pointer transition-all hover:scale-105",
                        selectedCategory === cat && "bg-primary text-primary-foreground"
                      )}
                      onClick={() => setSelectedCategory(cat)}
                    >
                      {cat}
                    </Badge>
                  ))}
                </div>
              </div>
            </Card>

            {/* Products Grid */}
            <div className="lg:flex-1 lg:overflow-y-auto pb-4 lg:pb-0">
              <div className="grid grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-2">
                  {filteredProducts.map((product) => (
                    <Card
                      key={product.id}
                    className="p-3 cursor-pointer hover-lift"
                    onClick={() => handleProductClick(product)}
                  >
                    <h3 className="font-semibold text-sm mb-1 line-clamp-2">{product.name}</h3>
                    <p className="text-base font-bold text-secondary">${product.price.toFixed(2)}</p>
                    {product.modifierGroups && product.modifierGroups.length > 0 && (
                      <Badge variant="secondary" className="mt-1 text-xs">
                        <span className="md:hidden">Custom</span>
                        <span className="hidden md:inline">Customizable</span>
                      </Badge>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          </div>

          {/* Cart Section */}
          <Card className="flex flex-col overflow-hidden">
            <div className="p-4 border-b">
              <h2 className="text-xl font-bold mb-3">Pedido Actual</h2>
              
              <div className="flex gap-2">
                <Button
                  variant={serviceType === "dine-in" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("dine-in")}
                  className="flex-1"
                >
                  En Local
                </Button>
                <Button
                  variant={serviceType === "takeout" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("takeout")}
                  className="flex-1"
                >
                  Para Llevar
                </Button>
                <Button
                  variant={serviceType === "delivery" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("delivery")}
                  className="flex-1"
                >
                  Delivery
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {cart.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <ShoppingCart className="h-16 w-16 mb-3 opacity-50" />
                  <p>Carrito vacío</p>
                  <p className="text-sm">Agrega productos para empezar</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {cart.map((item) => (
                    <Card key={item.id} className="p-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h4 className="font-semibold text-sm">{item.name}</h4>
                          {item.modifiers.length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {item.modifiers.map((mod) => mod.name).join(", ")}
                            </div>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeItem(item.id)}
                          className="h-7 w-7 text-danger"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => updateQuantity(item.id, -1)}
                            className="h-7 w-7"
                          >
                            <Minus className="h-3 w-3" />
                          </Button>
                          <span className="w-8 text-center font-semibold">{item.quantity}</span>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => updateQuantity(item.id, 1)}
                            className="h-7 w-7"
                          >
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                        <span className="font-bold">${(item.price * item.quantity).toFixed(2)}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            <div className="p-4 border-t space-y-3">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span>{formatMoney(subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Impuesto ({(taxRate * 100).toFixed(0)}%)</span>
                  <span>{formatMoney(tax)}</span>
                </div>
                <div className="flex justify-between text-lg font-bold">
                  <span>Total</span>
                  <span className="text-secondary">{formatMoney(total)}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3">
                <Button
                  variant="default"
                  className="w-full font-bold"
                  size="lg"
                  disabled={cart.length === 0 || isProcessingPayment}
                  onClick={handleCheckout}
                >
                  Cobrar {formatMoney(total)}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setCart([])}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Payment Dialog */}
      <Dialog open={isPaymentOpen} onOpenChange={setIsPaymentOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Cobrar pedido</DialogTitle>
            <DialogDescription>Registra el pago del pedido en curso</DialogDescription>
          </DialogHeader>
          {activeOrder ? (
            <div className="space-y-4">
              <div className="rounded-md border p-3 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Pedido</span>
                  <span>#{activeOrder.orderNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total</span>
                  <span>{formatMoney(paymentTotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pagado</span>
                  <span>{formatMoney(toNumber(paymentAmount) + toNumber(tipAmount))}</span>
                </div>
                <div className="flex justify-between font-semibold">
                  <span>Pendiente</span>
                  <span>
                    {formatMoney(
                      Math.max(paymentTotal - toNumber(paymentAmount) - toNumber(tipAmount), 0)
                    )}
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Método</Label>
                <Select value={paymentMethod} onValueChange={(value: PaymentMethod) => setPaymentMethod(value)}>
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
                    value={paymentAmount}
                    onChange={(e) => setPaymentAmount(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Propina</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={tipAmount}
                    onChange={(e) => setTipAmount(e.target.value)}
                  />
                </div>
              </div>

              {(paymentMethod === "card" || paymentMethod === "transfer") && (
                <div className="space-y-2">
                  <Label>Referencia</Label>
                  <Input
                    value={paymentReference}
                    onChange={(e) => setPaymentReference(e.target.value)}
                    placeholder="Opcional"
                  />
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setIsPaymentOpen(false)}>
                  Cerrar
                </Button>
                <Button className="flex-1" onClick={handleSubmitPayment} disabled={isProcessingPayment}>
                  {isProcessingPayment ? "Procesando..." : "Registrar pago"}
                </Button>
              </div>

              {activeOrder.paymentStatus === "paid" && (
                <Button variant="outline" className="w-full" onClick={handlePrintReceipt}>
                  Imprimir recibo
                </Button>
              )}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No hay pedido activo.</div>
          )}
        </DialogContent>
      </Dialog>

      <PrintPreviewDialog
        open={isReceiptPreviewOpen}
        onOpenChange={setIsReceiptPreviewOpen}
        job={receiptJob}
        onMarkPrinted={handleMarkPrinted}
        onReprint={handleReprint}
      />

      {/* Modifier Dialog */}
      <Dialog open={showModifierDialog} onOpenChange={setShowModifierDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Personalizar {selectedProduct?.name}</DialogTitle>
            <DialogDescription>
              Selecciona tus opciones favoritas
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {selectedProduct?.modifierGroups?.map((groupId: number) => {
              const group = modifierGroups.find((g) => g.id === groupId);
              if (!group) return null;

              const selectedCount = selectedModifiers[groupId]?.length || 0;
              const isValid = selectedCount >= group.minSelection && selectedCount <= group.maxSelection;

              return (
                <div key={groupId} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">
                      {group.name}
                      {group.required && <span className="text-danger ml-1">*</span>}
                    </h3>
                    <Badge variant={isValid ? "default" : "destructive"}>
                      {selectedCount}/{group.maxSelection} seleccionados
                    </Badge>
                  </div>

                  {group.maxSelection === 1 ? (
                    <RadioGroup
                      value={selectedModifiers[groupId]?.[0] || ""}
                      onValueChange={(value) =>
                        setSelectedModifiers({ ...selectedModifiers, [groupId]: [value] })
                      }
                    >
                      {group.modifiers.map((mod) => (
                        <div key={mod.id} className="flex items-center space-x-2 p-2 rounded hover:bg-muted">
                          <RadioGroupItem value={String(mod.id)} id={String(mod.id)} />
                          <Label htmlFor={String(mod.id)} className="flex-1 cursor-pointer">
                            {mod.name}
                          </Label>
                          {mod.price > 0 && (
                            <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                          )}
                        </div>
                      ))}
                    </RadioGroup>
                  ) : (
                    <div className="space-y-2">
                      {group.modifiers.map((mod) => (
                        <div key={mod.id} className="flex items-center space-x-2 p-2 rounded hover:bg-muted">
                          <Checkbox
                            id={String(mod.id)}
                            checked={selectedModifiers[groupId]?.includes(String(mod.id)) || false}
                            onCheckedChange={(checked) => {
                              const current = selectedModifiers[groupId] || [];
                              if (checked && current.length < group.maxSelection) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: [...current, String(mod.id)],
                                });
                              } else if (!checked) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: current.filter((id) => id !== String(mod.id)),
                                });
                              }
                            }}
                            disabled={
                              !selectedModifiers[groupId]?.includes(String(mod.id)) &&
                              (selectedModifiers[groupId]?.length || 0) >= group.maxSelection
                            }
                          />
                          <Label htmlFor={String(mod.id)} className="flex-1 cursor-pointer">
                            {mod.name}
                          </Label>
                          {mod.price > 0 && (
                            <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <Button
            className="w-full"
            onClick={handleAddModifiers}
            disabled={!canAddToCart()}
          >
            Agregar al Pedido
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default POS;
