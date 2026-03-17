import { Navigation } from "@/components/Navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, Trash2, ShoppingCart, Wallet, ChevronDown, ChevronUp } from "lucide-react";
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
  Customer,
  createPayment,
  getPaymentMethods,
  getOrderById,
  createPrintJob,
  markPrintJobPrinted,
  getActiveTaxConfig,
  getCategories,
  getModifierGroups,
  getProducts,
  getCurrentCashSession,
  getDefaultConsumerCustomer,
  listCustomers,
  openCashSession,
  closeCashSession,
  getCashTransactions,
  createCashPayout,
  Category,
  ModifierGroup,
  Product,
  PaymentMethod,
  PaymentMethodOption,
  CashSessionSnapshot,
  CashTransaction,
  Order,
  PrintJob,
} from "@/lib/api";
import { toast } from "sonner";
import { PrintPreviewDialog } from "@/components/printing/PrintPreviewDialog";
import { useServiceTypes } from "@/hooks/useServiceTypes";

interface CartItem {
  id: string;
  productId: number;
  name: string;
  basePrice: number;
  price: number;
  quantity: number;
  modifiers: Array<{ id?: number; name: string; price: number }>;
}

const getPaidExtrasLines = (item: CartItem) =>
  (item.modifiers || []).filter((modifier) => modifier.price > 0).map((modifier) => ({
    name: modifier.name,
    price: modifier.price,
  }));

const getOrderDisposableTotal = (
  items: CartItem[],
  products: Product[],
  serviceType: string
) =>
  items.reduce((sum, item) => {
    const product = products.find((candidate) => candidate.id === item.productId);
    if (!product) return sum;
    const applyTo = product.disposableApplyTo ?? [];
    const fee = product.disposableFee ?? 0;
    if (fee <= 0 || !applyTo.includes(serviceType)) return sum;
    return sum + fee * item.quantity;
  }, 0);

const DENOMINATION_CENTS = [500, 1000, 2000, 5000, 10000, 25, 50, 100];

const parseMoneyToCents = (value: string): number => {
  const normalized = value.replace(/[^\d.]/g, "");
  const amount = Number(normalized || 0);
  if (!Number.isFinite(amount) || amount < 0) return 0;
  return Math.round(amount * 100);
};

const centsToInput = (value: number): string => (Math.max(0, value) / 100).toFixed(2);


const POS = () => {
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [serviceType, setServiceType] = useState<string>("");
  const { activeServiceTypes: serviceTypes } = useServiceTypes();
  const [isExtrasOpen, setIsExtrasOpen] = useState(false);

  const [isCashDialogOpen, setIsCashDialogOpen] = useState(false);
  const [isPayoutDialogOpen, setIsPayoutDialogOpen] = useState(false);
  const [cashSnapshot, setCashSnapshot] = useState<CashSessionSnapshot>({ open: false });
  const [cashTransactions, setCashTransactions] = useState<CashTransaction[]>([]);
  const [openingCashInput, setOpeningCashInput] = useState("");
  const [closingCashInput, setClosingCashInput] = useState("");
  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutDescription, setPayoutDescription] = useState("");
  const [cashNotes, setCashNotes] = useState("");
  const [isSavingCashAction, setIsSavingCashAction] = useState(false);
  const [pendingProduct, setPendingProduct] = useState<Product | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [openModifierGroups, setOpenModifierGroups] = useState<Record<string, boolean>>({});
  const [modifierValidationErrors, setModifierValidationErrors] = useState<Record<string, string>>({});
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [taxRate, setTaxRate] = useState(0.13);
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>([]);
  const [selectedPaymentMethodCode, setSelectedPaymentMethodCode] = useState<string>("CASH");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [dteDocumentType, setDteDocumentType] = useState<"CF" | "CCF" | "SX">("CF");
  const [ivaExempt, setIvaExempt] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [tipAmount, setTipAmount] = useState("");
  const [activeTenderField, setActiveTenderField] = useState<"payment" | "tip" | null>(null);
  const [shouldResetTenderOnFirstTap, setShouldResetTenderOnFirstTap] = useState(true);
  const [paymentReference, setPaymentReference] = useState("");
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [createdOrderNumber, setCreatedOrderNumber] = useState<number | null>(null);
  const [receiptJob, setReceiptJob] = useState<PrintJob | null>(null);
  const [isReceiptPreviewOpen, setIsReceiptPreviewOpen] = useState(false);
  const [checkoutDraft, setCheckoutDraft] = useState<{
    items: CartItem[];
    subtotal: number;
    tax: number;
    total: number;
    taxRate: number;
    serviceType: typeof serviceType;
    createdAt: number;
  } | null>(null);

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

  useEffect(() => {
    if (!serviceTypes.length) return;
    if (!serviceType || !serviceTypes.some((item) => item.key === serviceType)) {
      setServiceType(serviceTypes[0].key);
    }
  }, [serviceTypes, serviceType]);

  const filteredProducts = products.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch && product.available;
  });

  const getPosModifierGroups = (product: Product | null) => {
    const visibleGroupIds = product?.modifierGroupsPos ?? product?.modifierGroups ?? [];
    if (!visibleGroupIds.length) return [] as ModifierGroup[];
    return visibleGroupIds
      .map((groupId) => modifierGroups.find((group) => group.id === groupId))
      .filter((group): group is ModifierGroup => Boolean(group));
  };

  const handleProductClick = (product: Product) => {
    const visibleGroups = getPosModifierGroups(product);
    if (!visibleGroups.length) {
      addToCart(product, []);
      return;
    }
    setPendingProduct(product);
    setSelectedModifiers({});
    setModifierValidationErrors({});
    const collapsed = visibleGroups.reduce<Record<string, boolean>>((acc, group) => {
      acc[String(group.id)] = false;
      return acc;
    }, {});
    setOpenModifierGroups(collapsed);
    setIsExtrasOpen(true);
  };

  const openCheckoutFromItems = (items: CartItem[]) => {
    if (items.length === 0) return;
    const draftItemsGross = calculateCartTotals(items, taxRate).total;
    const draftDisposable = getOrderDisposableTotal(items, products, serviceType);
    const draftTotal = draftItemsGross + draftDisposable;
    const draftTaxIncluded = draftTotal - draftTotal / (1 + taxRate);
    const draft = {
      items: [...items],
      subtotal: draftItemsGross,
      tax: draftTaxIncluded,
      total: draftTotal,
      taxRate,
      serviceType,
      createdAt: Date.now(),
    };
    setCheckoutDraft(draft);
    setPaymentAmount(toNumber(draft.total).toFixed(2));
    setTipAmount("0");
    setPaymentReference("");
    setIsPaymentOpen(true);
  };

  const addToCart = (product: Product, modifiers: Array<{ id?: number; name: string; price: number }>) => {
    const modifierPrice = modifiers.reduce((sum, mod) => sum + mod.price, 0);
    const totalPrice = product.price + modifierPrice;

    const existingItemIndex = cart.findIndex(
      (item) =>
        item.productId === product.id &&
        JSON.stringify(item.modifiers) === JSON.stringify(modifiers)
    );

    let nextCart: CartItem[];
    if (existingItemIndex >= 0) {
      nextCart = [...cart];
      nextCart[existingItemIndex].quantity += 1;
    } else {
      nextCart = [
        ...cart,
        {
          id: `${product.id}-${Date.now()}`,
          productId: product.id,
          name: product.name,
          basePrice: product.price,
          price: totalPrice,
          quantity: 1,
          modifiers,
        },
      ];
    }
    setCart(nextCart);
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

  const cartDisposableTotal = getOrderDisposableTotal(cart, products, serviceType);
  const itemsGross = calculateCartTotals(
    cart.map((item) => ({ ...item, price: item.price })),
    taxRate
  ).total;
  const total = itemsGross + cartDisposableTotal;
  const subtotal = itemsGross;
  const paymentTotal =
    (ivaExempt ? (checkoutDraft?.total ?? 0) / 1.13 : checkoutDraft?.total) ?? (cart.length > 0 ? total : toNumber(activeOrder?.total));
  const paymentStatus = activeOrder?.paymentStatus ?? "unpaid";
  const isPaid = paymentStatus === "paid";
  const paymentAmountValue = toNumber(paymentAmount);
  const tipAmountValue = toNumber(tipAmount);
  const checkoutTotal = ivaExempt ? (checkoutDraft?.total ?? 0) / 1.13 : (checkoutDraft?.total ?? 0);
  const checkoutTotalCents = Math.round(checkoutTotal * 100);
  const paymentAmountCents = parseMoneyToCents(paymentAmount);
  const tipAmountCents = parseMoneyToCents(tipAmount);
  const totalDueCents = checkoutTotalCents + tipAmountCents;
  const changeCents = paymentAmountCents - totalDueCents;
  const remainingTotal = Math.max(totalDueCents - paymentAmountCents, 0) / 100;
  const changeTotal = Math.max(changeCents, 0) / 100;
  const isExactPayment = Math.abs(changeCents) <= 1;
  const checkoutDisposableTotal = checkoutDraft
    ? getOrderDisposableTotal(checkoutDraft.items, products, checkoutDraft.serviceType)
    : 0;

  const handleCheckout = async () => {
    if (cart.length === 0) return;

    const draftItemsGross = calculateCartTotals(cart, taxRate).total;
    const draftDisposableTotal = getOrderDisposableTotal(cart, products, serviceType);
    const draftTotal = draftItemsGross + draftDisposableTotal;
    const draftTaxIncluded = draftTotal - draftTotal / (1 + taxRate);
    const draft = {
      items: [...cart],
      subtotal: draftItemsGross,
      tax: draftTaxIncluded,
      total: draftTotal,
      taxRate,
      serviceType,
      createdAt: Date.now(),
    };
    const hasSameDraft =
      checkoutDraft &&
      checkoutDraft.taxRate === draft.taxRate &&
      checkoutDraft.serviceType === draft.serviceType &&
      checkoutDraft.total === draft.total &&
      JSON.stringify(checkoutDraft.items) === JSON.stringify(draft.items);
    setCheckoutDraft(draft);
    if (!hasSameDraft) {
      setActiveOrder(null);
      setCreatedOrderId(null);
      setCreatedOrderNumber(null);
    }
    setPaymentAmount(toNumber(draft.total).toFixed(2));
    setTipAmount("0");
    setPaymentReference("");
    setIsPaymentOpen(true);
  };

  const handleAddPendingProductWithoutExtras = () => {
    if (!pendingProduct) return;
    addToCart(pendingProduct, []);
    setIsExtrasOpen(false);
    setPendingProduct(null);
    setSelectedModifiers({});
    setOpenModifierGroups({});
    setModifierValidationErrors({});
  };

  const handleAddPendingProductWithExtras = () => {
    if (!pendingProduct) return;
    const posGroups = getPosModifierGroups(pendingProduct);
    const nextErrors: Record<string, string> = {};
    const nextOpenState: Record<string, boolean> = { ...openModifierGroups };

    posGroups.forEach((group) => {
      const groupId = String(group.id);
      const selectedCount = (selectedModifiers[groupId] ?? []).length;
      if (group.required && selectedCount < Math.max(group.minSelection, 1)) {
        nextErrors[groupId] = `Este grupo es obligatorio (mínimo ${Math.max(group.minSelection, 1)}).`;
        nextOpenState[groupId] = true;
      }
    });

    if (Object.keys(nextErrors).length > 0) {
      setModifierValidationErrors(nextErrors);
      setOpenModifierGroups(nextOpenState);
      toast.error("Completa los modificadores obligatorios");
      return;
    }

    const selectedMods: Array<{ id?: number; name: string; price: number }> = [];
    posGroups.forEach((group) => {
      const groupId = String(group.id);
      (selectedModifiers[groupId] ?? []).forEach((modId) => {
        const mod = group.modifiers.find((candidate) => String(candidate.id) === modId);
        if (mod) selectedMods.push({ id: mod.id, name: mod.name, price: mod.price });
      });
    });
    addToCart(pendingProduct, selectedMods);
    setIsExtrasOpen(false);
    setPendingProduct(null);
    setSelectedModifiers({});
    setOpenModifierGroups({});
    setModifierValidationErrors({});
  };


  const loadCashData = async () => {
    try {
      const [snapshot, transactions] = await Promise.all([
        getCurrentCashSession(),
        getCashTransactions(),
      ]);
      setCashSnapshot(snapshot);
      setCashTransactions(transactions);
    } catch (error) {
      console.error("Failed to load cash data", error);
      toast.error("No se pudo cargar información de caja");
    }
  };

  useEffect(() => {
    getPaymentMethods().then((methods) => {
      setPaymentMethods(methods);
      const first = methods[0];
      if (first) {
        setSelectedPaymentMethodCode(first.code);
        const fallback = first.isCash ? "cash" : first.code === "CARD" ? "card" : "transfer";
        setPaymentMethod(fallback as PaymentMethod);
      }
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    listCustomers().then(setCustomers).catch(() => undefined);
    getDefaultConsumerCustomer().then((c) => {
      setSelectedCustomerId(String(c.id));
      setDteDocumentType(c.clientType ?? "CF");
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const selected = customers.find((c) => String(c.id) === selectedCustomerId);
    if (selected?.clientType) {
      setDteDocumentType(selected.clientType);
    }
  }, [selectedCustomerId, customers]);

  useEffect(() => {
    if (isPaymentOpen) {
      setPaymentAmount(toNumber(checkoutTotal).toFixed(2));
    }
  }, [checkoutTotal, isPaymentOpen]);

  const handleOpenCashSession = async () => {
    setIsSavingCashAction(true);
    try {
      await openCashSession(Number(openingCashInput || 0));
      await loadCashData();
      toast.success("Caja abierta");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo abrir caja");
    } finally {
      setIsSavingCashAction(false);
    }
  };

  const handleCloseCashSession = async () => {
    setIsSavingCashAction(true);
    try {
      const closeResp = await closeCashSession(Number(closingCashInput || 0), cashNotes);
      if (closeResp.ticketText) {
        toast.success("Caja cerrada. Ticket generado");
      }
      await loadCashData();
      
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo cerrar caja");
    } finally {
      setIsSavingCashAction(false);
    }
  };

  const handleCreatePayout = async () => {
    setIsSavingCashAction(true);
    try {
      await createCashPayout(Number(payoutAmount || 0), payoutDescription);
      setPayoutAmount("");
      setPayoutDescription("");
      setIsPayoutDialogOpen(false);
      await loadCashData();
      toast.success("Pago registrado");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo registrar pago");
    } finally {
      setIsSavingCashAction(false);
    }
  };

  const closeExtrasDialog = (open: boolean) => {
    setIsExtrasOpen(open);
    if (!open) {
      setPendingProduct(null);
      setSelectedModifiers({});
      setOpenModifierGroups({});
      setModifierValidationErrors({});
    }
  };

  const focusTenderField = (field: "payment" | "tip") => {
    setActiveTenderField(field);
    setShouldResetTenderOnFirstTap(true);
  };

  const applyTenderDenomination = (amountCents: number) => {
    if (!activeTenderField) return;
    const current = activeTenderField === "payment" ? parseMoneyToCents(paymentAmount) : parseMoneyToCents(tipAmount);
    const next = shouldResetTenderOnFirstTap ? amountCents : current + amountCents;
    const value = centsToInput(next);
    if (activeTenderField === "payment") setPaymentAmount(value);
    if (activeTenderField === "tip") setTipAmount(value);
    setShouldResetTenderOnFirstTap(false);
  };

  const clearTenderField = () => {
    if (!activeTenderField) return;
    if (activeTenderField === "payment") setPaymentAmount("");
    if (activeTenderField === "tip") setTipAmount("");
    setShouldResetTenderOnFirstTap(true);
  };

  const backspaceTenderField = () => {
    if (!activeTenderField) return;
    const currentRaw = activeTenderField === "payment" ? paymentAmount : tipAmount;
    const nextRaw = currentRaw.slice(0, -1);
    if (activeTenderField === "payment") setPaymentAmount(nextRaw);
    if (activeTenderField === "tip") setTipAmount(nextRaw);
    setShouldResetTenderOnFirstTap(false);
  };

  const setExactTenderAmount = () => {
    if (activeTenderField !== "payment") return;
    setPaymentAmount(centsToInput(totalDueCents));
    setShouldResetTenderOnFirstTap(false);
  };

  const handleSubmitPayment = async () => {
    if (!checkoutDraft || checkoutDraft.items.length === 0) {
      toast.error("No hay productos en el pedido");
      return;
    }
    const amountReceived = toNumber(paymentAmount);
    const tipValue = toNumber(tipAmount);
    const totalDue = totalDueCents / 100;

    if (!amountReceived || amountReceived <= 0) {
      toast.error("Ingresa un monto válido");
      return;
    }
    if (tipValue < 0) {
      toast.error("La propina no puede ser negativa");
      return;
    }
    if (amountReceived < totalDue) {
      toast.error("El monto recibido debe cubrir total + propina");
      return;
    }
    const selected = customers.find((c) => String(c.id) === selectedCustomerId);
    if (selected && selected.clientType && selected.clientType !== dteDocumentType) {
      toast.error(`El tipo DTE debe coincidir con el cliente (${selected.clientType})`);
      return;
    }

    try {
      setIsProcessingPayment(true);
      let order = activeOrder;
      if (!order) {
        if (createdOrderId) {
          order = await getOrderById(createdOrderId);
          setCreatedOrderNumber(order.orderNumber ?? null);
        } else {
          order = await createOrder({
            serviceType: checkoutDraft.serviceType,
            source: "pos",
            channel: "pos",
            customerId: selectedCustomerId ? Number(selectedCustomerId) : undefined,
            dteDocumentType,
            ivaExempt,
            items: checkoutDraft.items.map((item) => ({
              productId: item.productId,
              productName: item.name,
              price: item.basePrice,
              quantity: item.quantity,
              modifiers: item.modifiers,
            })),
          });
          const createdId =
            (order as Order | undefined)?.id ??
            (order as unknown as { order_id?: number }).order_id ??
            (order as unknown as { pk?: number }).pk;
          if (!createdId) {
            throw new Error("createOrder did not return an id");
          }
          setCreatedOrderId(createdId);
          setCreatedOrderNumber((order as Order | undefined)?.orderNumber ?? null);
        }
        setActiveOrder(order);
      }
      const orderId =
        (order as Order | undefined)?.id ??
        (order as unknown as { order_id?: number }).order_id ??
        (order as unknown as { pk?: number }).pk;
      if (!orderId) {
        throw new Error("createOrder did not return an id");
      }
      await createPayment({
        orderId,
        method: paymentMethod,
        amount: remaining,
        cashReceived: amountReceived,
        tipAmount: tipValue,
        reference: paymentReference || undefined,
        paymentMethodCode: selectedPaymentMethodCode,
      });
      const refreshed = await getOrderById(orderId);
      setActiveOrder(refreshed);
      setPaymentAmount(toNumber(refreshed.remaining).toFixed(2));
      setTipAmount("0");
      setPaymentReference("");
      if (refreshed.paymentStatus === "paid") {
        toast.success(refreshed.requiresKitchen ? "Pago y factura registrados. Enviado a cocina." : "Pago y factura registrados. Orden entregada.");
        setIsPaymentOpen(false);
        setCart([]);
        setCheckoutDraft(null);
        setCreatedOrderId(null);
        setCreatedOrderNumber(null);
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

  const selectedCustomer = customers.find((c) => String(c.id) === selectedCustomerId);

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
                
                <div className="flex gap-2.5 overflow-x-auto pb-1">
                  {["Todos", ...categories.filter((cat) => !cat.isHidden && !cat.name.toUpperCase().includes("SIN CATEGORÍA")).map((cat) => cat.name)].map((cat) => (
                    <Badge
                      key={cat}
                      variant={selectedCategory === cat ? "default" : "outline"}
                      className={cn(
                        "cursor-pointer transition-all whitespace-nowrap rounded-full px-4 py-2 text-sm min-h-10 inline-flex items-center",
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
                    <p className="text-base font-bold text-secondary">${(product.effectivePrice ?? product.price).toFixed(2)}</p>
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
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xl font-bold">Pedido Actual</h2>
                <Button variant="outline" size="sm" onClick={() => { setIsCashDialogOpen(true); loadCashData().catch(() => undefined); }}><Wallet className="mr-2 h-4 w-4" />Transacciones de Caja</Button>
              </div>
              
              <div className="flex gap-2 overflow-x-auto pb-1">
                {serviceTypes.length > 0 ? (
                  serviceTypes.map((type) => (
                    <Button
                      key={type.id}
                      variant={serviceType === type.key ? "default" : "outline"}
                      size="sm"
                      onClick={() => setServiceType(type.key)}
                      className="min-w-fit whitespace-nowrap"
                    >
                      {type.label}
                    </Button>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">
                    Configura tipos de pedido en Configuración.
                  </span>
                )}
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
                  <span>Subtotal (productos)</span>
                  <span>{formatMoney(subtotal)}</span>
                </div>
                {cartDisposableTotal > 0 && (
                  <div className="flex justify-between">
                    <span>Desechables</span>
                    <span>{formatMoney(cartDisposableTotal)}</span>
                  </div>
                )}
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


      <Dialog open={isCashDialogOpen} onOpenChange={setIsCashDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Transacciones de Caja</DialogTitle>
            <DialogDescription>Control de sesión, pagos y cierre de caja.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-md border p-3 text-sm">
              <div className="font-semibold">Estado: {cashSnapshot.open ? "Caja Abierta" : "Caja Cerrada"}</div>
              {cashSnapshot.open && cashSnapshot.summary && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-muted-foreground">
                  <div>Efectivo inicial: {formatMoney(cashSnapshot.summary.openingCash)}</div>
                  <div>Efectivo ventas: {formatMoney(cashSnapshot.summary.totalCashSales)}</div>
                  <div>Tarjeta: {formatMoney(cashSnapshot.summary.methods.card)}</div>
                  <div>Transferencia: {formatMoney(cashSnapshot.summary.methods.transfer)}</div>
                  <div>Pagos/gastos: -{formatMoney(cashSnapshot.summary.totalCashOut)}</div>
                  <div className="font-semibold text-foreground">Esperado en caja: {formatMoney(cashSnapshot.summary.expectedCashInDrawer)}</div>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Button className="h-14 text-base font-semibold" variant="outline" disabled title="Próximamente: apertura de cajón de dinero">ABRIR CAJA</Button>
              <Button className="h-14 text-base font-semibold" onClick={() => setIsPayoutDialogOpen(true)} disabled={!cashSnapshot.open}>PAGOS</Button>
            </div>

            {!cashSnapshot.open ? (
              <div className="space-y-2 rounded-md border p-3">
                <Label>Apertura de sesión (efectivo inicial)</Label>
                <Input type="number" min="0" step="0.01" value={openingCashInput} onChange={(e) => setOpeningCashInput(e.target.value)} />
                <Button onClick={handleOpenCashSession} disabled={isSavingCashAction}>Abrir Caja (Sesión)</Button>
              </div>
            ) : (
              <div className="space-y-2 rounded-md border p-3">
                <Label>Efectivo contado al cierre</Label>
                <Input type="number" min="0" step="0.01" value={closingCashInput} onChange={(e) => setClosingCashInput(e.target.value)} />
                <Label>Notas</Label>
                <Textarea rows={2} value={cashNotes} onChange={(e) => setCashNotes(e.target.value)} placeholder="Opcional" />
                <Button variant="destructive" onClick={handleCloseCashSession} disabled={isSavingCashAction || !closingCashInput}>Cerrar Caja</Button>
              </div>
            )}

            <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2 text-sm">
              {cashTransactions.length === 0 ? (
                <div className="text-muted-foreground">Sin pagos registrados.</div>
              ) : (
                cashTransactions.map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between rounded border px-2 py-1">
                    <div>
                      <div className="font-medium">{tx.description}</div>
                      <div className="text-xs text-muted-foreground">{new Date(tx.createdAt).toLocaleString()}</div>
                    </div>
                    <div className="font-semibold text-destructive">-{formatMoney(tx.amount)}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPayoutDialogOpen} onOpenChange={setIsPayoutDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Registrar Pago (Gasto)</DialogTitle>
            <DialogDescription>Este pago resta efectivo de caja.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Monto</Label>
              <Input type="number" min="0" step="0.01" value={payoutAmount} onChange={(e) => setPayoutAmount(e.target.value)} />
            </div>
            <div>
              <Label>Descripción</Label>
              <Textarea rows={3} value={payoutDescription} onChange={(e) => setPayoutDescription(e.target.value)} placeholder="Ej: Pago proveedor / compra insumos" />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setIsPayoutDialogOpen(false)}>Cancelar</Button>
              <Button className="flex-1" onClick={handleCreatePayout} disabled={isSavingCashAction || !payoutAmount || !payoutDescription.trim()}>Guardar pago</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Payment Dialog */}
      <Dialog open={isPaymentOpen} onOpenChange={setIsPaymentOpen}>
        <DialogContent className="w-[96vw] max-w-3xl p-0">
          <div className="flex max-h-[90vh] flex-col">
            <DialogHeader className="border-b px-4 py-3 sm:px-6">
              <DialogTitle>Cobrar pedido</DialogTitle>
              <DialogDescription>Confirma el pago y envía a cocina</DialogDescription>
            </DialogHeader>
            {checkoutDraft ? (
              <>
                <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6">
                  <div className="rounded-lg border bg-muted/30 p-4">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">Total a pagar</div>
                    <div className="mt-2 text-3xl font-bold text-secondary">{formatMoney(checkoutDraft.total)}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm font-semibold">
                      <span>Detalle</span>
                      <span className="text-xs text-muted-foreground">
                        {activeOrder?.orderNumber ? `Pedido #${activeOrder.orderNumber}` : createdOrderNumber ? `Pedido #${createdOrderNumber}` : "Pedido (pendiente)"}
                      </span>
                    </div>
                    <div className="rounded-md border">
                      <div className="max-h-40 divide-y divide-border overflow-y-auto text-sm">
                        {checkoutDraft.items.map((item) => (
                          <div key={item.id} className="grid grid-cols-[1fr_auto_auto] items-start gap-3 p-2">
                            <div className="min-w-0">
                              <div className="truncate font-medium">{item.name}</div>
                              <div className="text-xs text-muted-foreground">{formatMoney(toNumber(item.price))} c/u</div>
                            </div>
                            <div className="text-center text-xs text-muted-foreground">x{item.quantity}</div>
                            <div className="text-right font-semibold">{formatMoney(toNumber(item.price) * toNumber(item.quantity))}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-md border p-3 text-sm">
                    <div className="mb-2 font-semibold">Resumen</div>
                    <div className="space-y-1 text-muted-foreground">
                      <div className="flex justify-between"><span>Subtotal (productos)</span><span>{formatMoney(checkoutDraft.subtotal)}</span></div>
                      {checkoutDisposableTotal > 0 && <div className="flex justify-between"><span>Desechables</span><span>{formatMoney(checkoutDisposableTotal)}</span></div>}
                      <div className="flex justify-between font-semibold text-foreground"><span>Total</span><span>{formatMoney(checkoutDraft.total)}</span></div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Cliente</Label>
                    <div className="flex gap-2">
                      <Select value={selectedCustomerId} onValueChange={setSelectedCustomerId}>
                        <SelectTrigger><SelectValue placeholder="Selecciona cliente" /></SelectTrigger>
                        <SelectContent>{customers.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.fullName} ({c.clientType})</SelectItem>)}</SelectContent>
                      </Select>
                      <Button variant="outline" onClick={() => window.open('/clientes', '_blank')}>Administrar clientes</Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Tipo DTE</Label>
                    <div className="flex gap-2">
                      <Button type="button" variant={dteDocumentType === "CF" ? "default" : "outline"} onClick={() => setDteDocumentType("CF")}>CF</Button>
                      <Button type="button" variant={dteDocumentType === "CCF" ? "default" : "outline"} onClick={() => setDteDocumentType("CCF")}>CCF</Button>
                      <Button type="button" variant={dteDocumentType === "SX" ? "default" : "outline"} onClick={() => setDteDocumentType("SX")}>SX</Button>
                    </div>
                  </div>
                  {selectedCustomer && selectedCustomer.clientType !== dteDocumentType && <p className="text-xs text-destructive">Tipo DTE no coincide con cliente seleccionado ({selectedCustomer.clientType}).</p>}
                  <div className="flex items-center justify-between rounded-md border p-2 text-sm"><span>Exento IVA</span><Checkbox checked={ivaExempt} onCheckedChange={(v) => setIvaExempt(v === true)} /></div>
                </div>

                <div className="shrink-0 space-y-3 border-t bg-background px-4 py-4 sm:px-6">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Método</Label>
                      <Select value={selectedPaymentMethodCode} onValueChange={(value: string) => { setSelectedPaymentMethodCode(value); const selected = paymentMethods.find((m) => m.code === value); const fallback = selected?.isCash ? "cash" : value === "CARD" ? "card" : "transfer"; setPaymentMethod(fallback as PaymentMethod); }}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{paymentMethods.map((m) => <SelectItem key={m.id} value={m.code}>{m.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    {(paymentMethod === "card" || paymentMethod === "transfer") && (
                      <div className="space-y-2">
                        <Label>Referencia</Label>
                        <Input value={paymentReference} onChange={(e) => setPaymentReference(e.target.value)} placeholder="Opcional" />
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>Monto recibido</Label>
                      <Input value={paymentAmount} onFocus={() => focusTenderField("payment")} onClick={() => focusTenderField("payment")} onChange={(e) => setPaymentAmount(e.target.value)} inputMode="decimal" />
                    </div>
                    <div className="space-y-2">
                      <Label>Propina</Label>
                      <Input value={tipAmount} onFocus={() => focusTenderField("tip")} onClick={() => focusTenderField("tip")} onChange={(e) => setTipAmount(e.target.value)} inputMode="decimal" />
                    </div>
                  </div>

                  <div className="rounded-lg border p-3 text-center text-lg font-semibold">
                    {changeCents < -1 && <span className="text-destructive">Faltan {formatMoney(Math.abs(changeCents) / 100)}</span>}
                    {isExactPayment && <span className="text-secondary">Pago exacto</span>}
                    {changeCents > 1 && <span className="text-emerald-500">Cambio: {formatMoney(changeCents / 100)}</span>}
                  </div>

                  <div className="grid grid-cols-4 gap-2">
                    {DENOMINATION_CENTS.map((value) => (
                      <Button key={value} type="button" variant="outline" onClick={() => applyTenderDenomination(value)}>
                        {formatMoney(value / 100)}
                      </Button>
                    ))}
                    <Button type="button" variant="outline" onClick={clearTenderField}>Borrar</Button>
                    <Button type="button" variant="outline" onClick={backspaceTenderField}>←</Button>
                    <Button type="button" variant="outline" className="col-span-2" onClick={setExactTenderAmount}>Exacto</Button>
                  </div>

                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1" onClick={() => setIsPaymentOpen(false)}>Cerrar</Button>
                    <Button className="flex-1" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || paymentAmountValue <= 0}>
                      {isProcessingPayment ? "Procesando..." : "Registrar pago"}
                    </Button>
                  </div>
                  {isPaid && <Button variant="outline" className="w-full" onClick={handlePrintReceipt}>Imprimir recibo</Button>}
                </div>
              </>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">No hay pedido activo.</div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <PrintPreviewDialog
        open={isReceiptPreviewOpen}
        onOpenChange={setIsReceiptPreviewOpen}
        job={receiptJob}
        onMarkPrinted={handleMarkPrinted}
        onReprint={handleReprint}
      />

      <Dialog open={isExtrasOpen} onOpenChange={closeExtrasDialog}>
        <DialogContent className="w-[92vw] max-w-[520px] rounded-2xl border border-border/70 p-6">
          <DialogHeader>
            <DialogTitle>Extras (opcional)</DialogTitle>
            <DialogDescription>
              {pendingProduct ? `Selecciona extras de pago para ${pendingProduct.name}.` : "Selecciona extras de pago."}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[52vh] space-y-4 overflow-y-auto pr-1">
            {getPosModifierGroups(pendingProduct).map((group) => {
              const groupId = String(group.id);
              const selectedValues = selectedModifiers[groupId] ?? [];
              const isOpen = openModifierGroups[groupId] ?? false;
              const groupError = modifierValidationErrors[groupId];
              return (
                <div key={group.id} className={cn("rounded-xl border border-border/70", groupError && "border-destructive/60")}> 
                  <button
                    type="button"
                    className="flex min-h-14 w-full items-center justify-between px-4 py-3 text-left"
                    onClick={() => setOpenModifierGroups((prev) => ({ ...prev, [groupId]: !isOpen }))}
                    aria-expanded={isOpen}
                  >
                    <div>
                      <Label className="block cursor-pointer text-base font-semibold">{group.name}</Label>
                      <p className="text-xs text-muted-foreground">
                        {group.required ? "Obligatorio" : "Opcional"} · Min {group.minSelection} · Max {group.maxSelection}
                      </p>
                    </div>
                    {isOpen ? <ChevronUp className="h-5 w-5 text-muted-foreground" /> : <ChevronDown className="h-5 w-5 text-muted-foreground" />}
                  </button>
                  {groupError && <p className="px-4 pb-2 text-xs text-destructive">{groupError}</p>}
                  {isOpen && (
                    <div className="space-y-2 px-3 pb-3">
                      {group.maxSelection === 1 ? (
                        <RadioGroup
                          value={selectedValues[0] || ""}
                          onValueChange={(value) => {
                            setSelectedModifiers((prev) => ({ ...prev, [groupId]: value ? [value] : [] }));
                            setModifierValidationErrors((prev) => {
                              const next = { ...prev };
                              delete next[groupId];
                              return next;
                            });
                          }}
                        >
                          {group.modifiers
                            .filter((mod) => mod.price > 0)
                            .map((mod) => (
                              <Label
                                key={mod.id}
                                htmlFor={`pending-${group.id}-${mod.id}`}
                                className="flex min-h-14 cursor-pointer items-center gap-3 rounded-lg border border-border/60 px-3 py-3 text-base hover:bg-muted/40"
                              >
                                <RadioGroupItem id={`pending-${group.id}-${mod.id}`} value={String(mod.id)} />
                                <span className="flex-1 font-medium">{mod.name}</span>
                                <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                              </Label>
                            ))}
                        </RadioGroup>
                      ) : (
                        <div className="space-y-1">
                          {group.modifiers
                            .filter((mod) => mod.price > 0)
                            .map((mod) => (
                              <Label
                                key={mod.id}
                                htmlFor={`pending-${group.id}-${mod.id}`}
                                className="flex min-h-14 cursor-pointer items-center gap-3 rounded-lg border border-border/60 px-3 py-3 text-base hover:bg-muted/40"
                              >
                                <Checkbox
                                  id={`pending-${group.id}-${mod.id}`}
                                  checked={selectedValues.includes(String(mod.id))}
                                  onCheckedChange={(checked) => {
                                    const current = selectedValues;
                                    if (checked && current.length >= group.maxSelection) return;
                                    setSelectedModifiers((prev) => ({
                                      ...prev,
                                      [groupId]: checked
                                        ? [...current, String(mod.id)]
                                        : current.filter((id) => id !== String(mod.id)),
                                    }));
                                    setModifierValidationErrors((prev) => {
                                      const next = { ...prev };
                                      delete next[groupId];
                                      return next;
                                    });
                                  }}
                                />
                                <span className="flex-1 font-medium">{mod.name}</span>
                                <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                              </Label>
                            ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <Button variant="outline" className="h-12" onClick={handleAddPendingProductWithoutExtras}>
              Sin extras
            </Button>
            <Button className="h-12" onClick={handleAddPendingProductWithExtras}>
              Agregar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default POS;
