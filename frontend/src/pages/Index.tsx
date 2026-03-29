import { Navigation } from "@/components/Navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, Trash2, ShoppingCart, Wallet, ChevronDown, ChevronUp, Delete, PencilLine } from "lucide-react";
import { cn } from "@/lib/utils";
import { calculateCartTotals, formatMoney, toNumber } from "@/lib/money";
import { formatDateTimeSV } from "@/lib/datetime";
import { SplitPanel } from "@/components/pos/SplitPanel";
import { SplitPart, splitEvenly, validateParts } from "@/lib/splitPayments";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
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
  openCashDrawer,
  validateOrderPricePin,
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
  productId: number | null;
  name: string;
  basePrice: number;
  originalBasePrice?: number;
  price: number;
  quantity: number;
  isCustom?: boolean;
  customCode?: string;
  assignedName?: string;
  unitPriceOverride?: number | null;
  appliedSpecialPriceRuleName?: string | null;
  modifiers: Array<{ id?: number; name: string; price: number }>;
}

const getItemModifierTotal = (item: CartItem) => (item.modifiers || []).reduce((sum, mod) => sum + Number(mod.price || 0), 0);
const getItemBaseEffective = (item: CartItem) => (item.unitPriceOverride != null ? Number(item.unitPriceOverride) : Number(item.basePrice));
const getItemUnitTotal = (item: CartItem) => getItemBaseEffective(item) + getItemModifierTotal(item);

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

const DrawerIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 11h18" />
    <rect x="8" y="13" width="8" height="4" rx="1" />
  </svg>
);


const POS = () => {
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [serviceType, setServiceType] = useState<string>("");
  const { activeServiceTypes: serviceTypes } = useServiceTypes();
  const [isExtrasOpen, setIsExtrasOpen] = useState(false);

  const [isCashDialogOpen, setIsCashDialogOpen] = useState(false);
  const [isPayoutDialogOpen, setIsPayoutDialogOpen] = useState(false);
  const [isOpenSessionModalOpen, setIsOpenSessionModalOpen] = useState(false);
  const [cashSnapshot, setCashSnapshot] = useState<CashSessionSnapshot>({ open: false });
  const [cashTransactions, setCashTransactions] = useState<CashTransaction[]>([]);
  const [openSessionAmount, setOpenSessionAmount] = useState("0.00");
  const [closingCashInput, setClosingCashInput] = useState("");
  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutDescription, setPayoutDescription] = useState("");
  const [cashNotes, setCashNotes] = useState("");
  const [isSavingCashAction, setIsSavingCashAction] = useState(false);
  const [isOpeningDrawer, setIsOpeningDrawer] = useState(false);
  const openSessionInputRef = useRef<HTMLInputElement | null>(null);
  const postOpenSessionActionRef = useRef<(() => void) | null>(null);
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
  const cashInputsContainerRef = useRef<HTMLDivElement | null>(null);
  const keypadRef = useRef<HTMLDivElement | null>(null);
  const [paymentReference, setPaymentReference] = useState("");
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [splitEnabled, setSplitEnabled] = useState(false);
  const [parts, setParts] = useState<SplitPart[]>([]);
  const [activePartId, setActivePartId] = useState<string | null>(null);
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
  const [isManualProductOpen, setIsManualProductOpen] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualQty, setManualQty] = useState("1");
  const [manualPrice, setManualPrice] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [priceEditorItemId, setPriceEditorItemId] = useState<string | null>(null);
  const [isPinModalOpen, setIsPinModalOpen] = useState(false);
  const [isPriceModalOpen, setIsPriceModalOpen] = useState(false);
  const [pinInput, setPinInput] = useState("");
  const [validatedPin, setValidatedPin] = useState<string>("");
  const [newPriceInput, setNewPriceInput] = useState("");

  const loadMenuData = async (orderTypeId?: number) => {
    const [categoriesResponse, productsResponse, modifierGroupsResponse] = await Promise.all([
      getCategories(),
      getProducts(orderTypeId ? { orderTypeId } : undefined),
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

  useEffect(() => {
    const selectedServiceType = serviceTypes.find((item) => item.key === serviceType);
    getProducts(selectedServiceType ? { orderTypeId: selectedServiceType.id } : undefined)
      .then(setProducts)
      .catch((error) => {
        console.error("Failed to refresh products for service type", error);
      });
  }, [serviceType, serviceTypes]);

  useEffect(() => {
    if (paymentMethod !== "cash") {
      setActiveTenderField(null);
    }
  }, [paymentMethod]);

  useEffect(() => {
    if (!activeTenderField) return;
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (cashInputsContainerRef.current?.contains(target)) return;
      if (keypadRef.current?.contains(target)) return;
      setActiveTenderField(null);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [activeTenderField]);

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
    const draftItemsGross = calculateCartTotals(
      items.map((item) => ({ ...item, price: getItemUnitTotal(item) })),
      taxRate
    ).total;
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
    setSplitEnabled(false);
    const initialParts = splitEvenly(Math.round(draft.total * 100), 1);
    setParts(initialParts);
    setActivePartId(initialParts[0]?.id ?? null);
    setIsPaymentOpen(true);
  };

  const addToCart = (product: Product, modifiers: Array<{ id?: number; name: string; price: number }>) => {
    const effectiveBasePrice = product.effectivePrice ?? product.price;
    const modifierPrice = modifiers.reduce((sum, mod) => sum + mod.price, 0);
    const totalPrice = effectiveBasePrice + modifierPrice;

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
          basePrice: effectiveBasePrice,
          originalBasePrice: product.isSpecialPriceActiveNow ? product.price : undefined,
          price: totalPrice,
          quantity: 1,
          isCustom: false,
          appliedSpecialPriceRuleName: product.appliedSpecialPriceRuleName,
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

  const openItemPriceEditor = (itemId: string) => {
    setPriceEditorItemId(itemId);
    setPinInput("");
    setValidatedPin("");
    setIsPinModalOpen(true);
  };

  const applyPriceOverride = () => {
    const parsed = Number(newPriceInput);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      toast.error("Precio inválido");
      return;
    }
    if (!priceEditorItemId) return;
    setCart((prev) =>
      prev.map((item) =>
        item.id === priceEditorItemId
          ? {
              ...item,
              unitPriceOverride: parsed,
              price: parsed + getItemModifierTotal(item),
            }
          : item
      )
    );
    setIsPriceModalOpen(false);
    toast.success("Precio ajustado para esta venta");
  };

  const handleAddManualProduct = () => {
    const quantity = Math.max(1, Math.floor(Number(manualQty || 1)));
    const price = Number(manualPrice);
    if (!manualName.trim()) {
      toast.error("Nombre es requerido");
      return;
    }
    if (!Number.isFinite(price) || price <= 0) {
      toast.error("Precio unitario inválido");
      return;
    }
    const code = `MANUAL-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
    setCart((prev) => [
      ...prev,
      {
        id: `manual-${Date.now()}`,
        productId: null,
        name: manualName.trim(),
        basePrice: price,
        price,
        quantity,
        isCustom: true,
        customCode: code,
        assignedName: manualNote.trim() || undefined,
        unitPriceOverride: null,
        modifiers: [],
      },
    ]);
    setManualName("");
    setManualQty("1");
    setManualPrice("");
    setManualNote("");
    setIsManualProductOpen(false);
  };

  const cartDisposableTotal = getOrderDisposableTotal(cart, products, serviceType);
  const itemsGross = calculateCartTotals(
    cart.map((item) => ({ ...item, price: getItemUnitTotal(item) })),
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
  const splitValidation = validateParts(checkoutTotalCents, parts);
  const activeSplitPart = parts.find((part) => part.id === activePartId) ?? parts.find((part) => !part.isPaid) ?? parts[0];
  const expectedPaymentCents = splitEnabled ? (activeSplitPart?.amountCents ?? checkoutTotalCents) : checkoutTotalCents;
  const paymentAmountCents = parseMoneyToCents(paymentAmount);
  const tipAmountCents = parseMoneyToCents(tipAmount);
  const totalDueCents = expectedPaymentCents + tipAmountCents;
  const changeCents = paymentAmountCents - totalDueCents;
  const remainingTotal = Math.max(totalDueCents - paymentAmountCents, 0) / 100;
  const changeTotal = Math.max(changeCents, 0) / 100;
  const isExactPayment = Math.abs(changeCents) <= 1;
  const checkoutDisposableTotal = checkoutDraft
    ? getOrderDisposableTotal(checkoutDraft.items, products, checkoutDraft.serviceType)
    : 0;

  const proceedToCheckout = () => {
    if (cart.length === 0) return;

    const draftItemsGross = calculateCartTotals(
      cart.map((item) => ({ ...item, price: getItemUnitTotal(item) })),
      taxRate
    ).total;
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
    setSplitEnabled(false);
    const initialParts = splitEvenly(Math.round(draft.total * 100), 1);
    setParts(initialParts);
    setActivePartId(initialParts[0]?.id ?? null);
    setIsPaymentOpen(true);
  };

  const requestOpenSession = (postAction?: () => void) => {
    postOpenSessionActionRef.current = postAction ?? null;
    setOpenSessionAmount("0.00");
    setIsOpenSessionModalOpen(true);
    setTimeout(() => openSessionInputRef.current?.select(), 0);
  };

  const ensureCashSessionOpen = async (postAction: () => void) => {
    try {
      const current = await getCurrentCashSession();
      setCashSnapshot(current);
      if (current.open) {
        postAction();
        return;
      }
      requestOpenSession(postAction);
    } catch {
      requestOpenSession(postAction);
    }
  };

  const handleCheckout = async () => {
    if (cart.length === 0) return;
    await ensureCashSessionOpen(proceedToCheckout);
  };

  const getPendingSelectionValidation = () => {
    if (!pendingProduct) return { errors: {} as Record<string, string>, selectedMods: [] as Array<{ id?: number; name: string; price: number }> };
    const posGroups = getPosModifierGroups(pendingProduct);
    const nextErrors: Record<string, string> = {};
    const selectedMods: Array<{ id?: number; name: string; price: number }> = [];

    posGroups.forEach((group) => {
      const groupId = String(group.id);
      const selectedCount = (selectedModifiers[groupId] ?? []).length;
      if (group.required && selectedCount < Math.max(group.minSelection, 1)) {
        nextErrors[groupId] = `Selecciona al menos ${Math.max(group.minSelection, 1)}.`;
      }
      (selectedModifiers[groupId] ?? []).forEach((modId) => {
        const mod = group.modifiers.find((candidate) => String(candidate.id) === modId);
        if (mod) selectedMods.push({ id: mod.id, name: mod.name, price: mod.price });
      });
    });
    return { errors: nextErrors, selectedMods };
  };

  const pendingSelectionValidation = getPendingSelectionValidation();
  const selectedExtrasCount = pendingSelectionValidation.selectedMods.length;
  const canAddPendingProduct = Object.keys(pendingSelectionValidation.errors).length === 0;

  const handleAddPendingProduct = () => {
    if (!pendingProduct) return;
    if (!canAddPendingProduct) {
      setModifierValidationErrors(pendingSelectionValidation.errors);
      const nextOpenState: Record<string, boolean> = { ...openModifierGroups };
      Object.keys(pendingSelectionValidation.errors).forEach((groupId) => {
        nextOpenState[groupId] = true;
      });
      setOpenModifierGroups(nextOpenState);
      toast.error("Completa los modificadores obligatorios");
      return;
    }
    addToCart(pendingProduct, pendingSelectionValidation.selectedMods);
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
      if (splitEnabled) {
        const targetAmount = (activeSplitPart?.amountCents ?? checkoutTotalCents) / 100;
        setPaymentAmount(toNumber(targetAmount).toFixed(2));
      } else {
        setPaymentAmount(toNumber(checkoutTotal).toFixed(2));
      }
    }
  }, [checkoutTotal, checkoutTotalCents, isPaymentOpen, splitEnabled, activeSplitPart]);

  useEffect(() => {
    if (!isPaymentOpen || !checkoutDraft) return;
    if (parts.length === 0) {
      const initialParts = splitEvenly(checkoutTotalCents, 1);
      setParts(initialParts);
      setActivePartId(initialParts[0]?.id ?? null);
    }
  }, [checkoutTotalCents, isPaymentOpen, checkoutDraft, parts.length]);

  const handleOpenCashSession = async () => {
    setIsSavingCashAction(true);
    try {
      await openCashSession(Number(openSessionAmount || 0));
      await loadCashData();
      toast.success("Caja aperturada");
      setIsOpenSessionModalOpen(false);
      const action = postOpenSessionActionRef.current;
      postOpenSessionActionRef.current = null;
      action?.();
    } catch (error) {
      toast.error(`No se pudo aperturar la caja: ${error instanceof Error ? error.message : "Error desconocido"}`);
    } finally {
      setIsSavingCashAction(false);
    }
  };

  const handleCloseCashSession = async () => {
    setIsSavingCashAction(true);
    try {
      const closeResp = await closeCashSession(Number(closingCashInput || 0), cashNotes);
      if (closeResp.printed) {
        toast.success("Caja cerrada. Ticket impreso");
      } else {
        toast.success(`Caja cerrada, pero no se pudo imprimir: ${closeResp.printError || "Error desconocido"}`);
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

  const handleOpenDrawer = async () => {
    setIsOpeningDrawer(true);
    try {
      await openCashDrawer();
      toast.success("ABRIENDO CAJON DE DINERO.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo abrir el cajón");
    } finally {
      setIsOpeningDrawer(false);
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
    if (isProcessingPayment) return;
    if (!checkoutDraft || checkoutDraft.items.length === 0) {
      toast.error("No hay productos en el pedido");
      return;
    }
    const amountReceived = toNumber(paymentAmount);
    const tipValue = toNumber(tipAmount);
    const totalDue = totalDueCents / 100;
    const remainingOrderAmount = Math.max(0, toNumber(activeOrder?.remaining) || checkoutTotal);
    const paymentAmountForApi = splitEnabled ? expectedPaymentCents / 100 : remainingOrderAmount;

    if (!amountReceived || amountReceived <= 0) {
      toast.error("Ingresa un monto válido");
      return;
    }
    if (tipValue < 0) {
      toast.error("La propina no puede ser negativa");
      return;
    }
    if (splitEnabled && !splitValidation.isValid) {
      toast.error(splitValidation.error || "Los montos de partes no cuadran");
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
            priceChangePin: checkoutDraft.items.some((item) => item.unitPriceOverride != null) ? validatedPin : undefined,
            customerId: selectedCustomerId ? Number(selectedCustomerId) : undefined,
            dteDocumentType,
            ivaExempt,
            items: checkoutDraft.items.map((item) => ({
              type: item.isCustom ? "manual" : "menu",
              productId: item.productId,
              productName: item.name,
              price: item.basePrice,
              unitPriceOverride: item.unitPriceOverride ?? null,
              quantity: item.quantity,
              isCustom: Boolean(item.isCustom),
              customCode: item.customCode,
              assignedName: item.assignedName,
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
      const latestOrder = await getOrderById(Number(orderId));
      setActiveOrder(latestOrder);
      const latestRemaining = Math.max(0, toNumber(latestOrder.remaining));
      const amountForApi =
        splitEnabled
          ? paymentAmountForApi
          : paymentMethod === "cash"
            ? latestRemaining
            : Math.min(paymentAmountForApi, latestRemaining);

      const paymentResult = await createPayment({
        orderId,
        method: paymentMethod,
        amount: amountForApi,
        cashReceived: amountReceived,
        tipAmount: tipValue,
        reference: paymentReference || undefined,
        paymentMethodCode: selectedPaymentMethodCode,
      });
      if (paymentResult.printed) {
        toast.success("Ticket impreso");
      } else if (paymentResult.printError) {
        toast.warning(`Venta registrada, pero no se pudo imprimir: ${paymentResult.printError}`);
      }
      const refreshed = await getOrderById(orderId);
      setActiveOrder(refreshed);
      if (splitEnabled) {
        const paidPartId = activeSplitPart?.id;
        const nextParts = parts.map((part) => (part.id === paidPartId ? { ...part, isPaid: true, locked: true } : part));
        setParts(nextParts);
        const nextUnpaid = nextParts.find((part) => !part.isPaid);
        setActivePartId(nextUnpaid?.id ?? nextParts[0]?.id ?? null);
      }
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
        setSplitEnabled(false);
        setParts([]);
        setActivePartId(null);
      } else {
        toast.success("Pago registrado");
      }
    } catch (error) {
      console.error("Failed to create payment", error);
      toast.error(error instanceof Error ? error.message : "No se pudo registrar el pago");
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
                    {product.isSpecialPriceActiveNow && (
                      <Badge className="mb-1 bg-emerald-600 text-white">OFERTA</Badge>
                    )}
                    <div className="space-y-0.5">
                      {product.isSpecialPriceActiveNow && (
                        <p className="text-xs text-muted-foreground line-through">${product.price.toFixed(2)}</p>
                      )}
                      <p className="text-base font-bold text-secondary">${(product.effectivePrice ?? product.price).toFixed(2)}</p>
                    </div>
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
              <div className="mb-3 space-y-2">
                <h2 className="text-xl font-bold text-center">Pedido Actual</h2>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <TooltipProvider delayDuration={120}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-11 rounded-full border-emerald-500/60 px-3"
                          onClick={() => setIsManualProductOpen(true)}
                        >
                          <Plus className="h-4 w-4 mr-1" />
                          Producto manual
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Agregar ítem manual para esta venta</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <Button variant="outline" size="sm" className="h-11" onClick={() => { setIsCashDialogOpen(true); loadCashData().catch(() => undefined); }}><Wallet className="mr-2 h-4 w-4" />Transacciones de Caja</Button>
                </div>
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
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-sm">{item.name}</h4>
                            {item.isCustom && <Badge variant="secondary" className="text-[10px] uppercase">Manual</Badge>}
                          </div>
                          {item.originalBasePrice != null && item.originalBasePrice !== item.basePrice && (
                            <p className="text-xs text-muted-foreground">
                              <span className="line-through mr-1">{formatMoney(item.originalBasePrice)}</span>
                              <span className="text-emerald-600 font-medium">Oferta aplicada</span>
                            </p>
                          )}
                          {item.appliedSpecialPriceRuleName && (
                            <p className="text-[11px] text-emerald-600/90">{item.appliedSpecialPriceRuleName}</p>
                          )}
                          {item.unitPriceOverride != null && (
                            <Badge variant="outline" className="mt-1 border-amber-500/60 text-amber-400">Precio ajustado</Badge>
                          )}
                          {item.modifiers.length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {item.modifiers.map((mod) => mod.name).join(", ")}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          {!item.isCustom && (
                            <Button variant="ghost" size="icon" onClick={() => openItemPriceEditor(item.id)} className="h-8 w-8" title="Cambiar precio para esta venta">
                              <PencilLine className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => removeItem(item.id)}
                            className="h-7 w-7 text-danger"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
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
                        <span className="font-bold">${(getItemUnitTotal(item) * item.quantity).toFixed(2)}</span>
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
            <div className="flex items-center justify-between gap-2">
              <div>
                <DialogTitle>Transacciones de Caja</DialogTitle>
                <DialogDescription>Control de sesión, pagos y cierre de caja.</DialogDescription>
              </div>
            </div>
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
            <div className="grid grid-cols-3 gap-3">
              <Button className="h-14 text-base font-semibold" onClick={() => requestOpenSession()} disabled={cashSnapshot.open}>
                {cashSnapshot.open ? "CAJA APERTURADA" : "APERTURAR CAJA"}
              </Button>
              <Button className="h-14 text-base font-semibold" onClick={() => setIsPayoutDialogOpen(true)} disabled={!cashSnapshot.open}>PAGOS</Button>
              <TooltipProvider delayDuration={120}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={handleOpenDrawer}
                      disabled={isOpeningDrawer}
                      className="h-14 w-full"
                      aria-label="Abrir cajón"
                      title="Abrir cajón"
                    >
                      <DrawerIcon className="h-6 w-6" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Abrir cajón</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            {cashSnapshot.open ? (
              <div className="space-y-2 rounded-md border p-3">
                <Label>Efectivo contado al cierre</Label>
                <Input type="number" min="0" step="0.01" value={closingCashInput} onChange={(e) => setClosingCashInput(e.target.value)} />
                <Label>Notas</Label>
                <Textarea rows={2} value={cashNotes} onChange={(e) => setCashNotes(e.target.value)} placeholder="Opcional" />
                <Button variant="destructive" onClick={handleCloseCashSession} disabled={isSavingCashAction || !closingCashInput}>Cerrar Caja</Button>
              </div>
            ) : null}

            <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2 text-sm">
              {cashTransactions.length === 0 ? (
                <div className="text-muted-foreground">Sin pagos registrados.</div>
              ) : (
                cashTransactions.map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between rounded border px-2 py-1">
                    <div>
                      <div className="font-medium">{tx.description}</div>
                      <div className="text-xs text-muted-foreground">{formatDateTimeSV(tx.createdAt)}</div>
                    </div>
                    <div className="font-semibold text-destructive">-{formatMoney(tx.amount)}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isOpenSessionModalOpen} onOpenChange={setIsOpenSessionModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Aperturar caja</DialogTitle>
            <DialogDescription>Ingresa el efectivo inicial para abrir la sesión.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>Efectivo inicial</Label>
            <Input
              ref={openSessionInputRef}
              value={openSessionAmount}
              onFocus={(event) => event.currentTarget.select()}
              onChange={(event) => setOpenSessionAmount(event.target.value)}
              inputMode="decimal"
            />
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setIsOpenSessionModalOpen(false)}>Cancelar</Button>
              <Button className="flex-1" onClick={handleOpenCashSession} disabled={isSavingCashAction}>
                {isSavingCashAction ? "Aperturando..." : "Aperturar"}
              </Button>
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
        <DialogContent className="flex h-[92vh] w-[96vw] max-h-[92vh] max-w-3xl flex-col overflow-hidden p-0">
          <div className="flex min-h-0 flex-1 flex-col">
            <DialogHeader className="border-b px-4 py-3 sm:px-6">
              <DialogTitle>Cobrar pedido</DialogTitle>
              <DialogDescription>Confirma el pago y envía a cocina</DialogDescription>
            </DialogHeader>
            {checkoutDraft ? (
              <>
                <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6 min-h-0">
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
                      <div className="max-h-72 divide-y divide-border overflow-y-auto text-sm">
                        {checkoutDraft.items.map((item) => (
                          <div key={item.id} className="grid grid-cols-[1fr_auto_auto] items-start gap-3 p-2">
                            <div className="min-w-0">
                              <div className="truncate font-medium">{item.name}</div>
                              <div className="text-xs text-muted-foreground">
                                {item.originalBasePrice != null && item.originalBasePrice !== item.basePrice && (
                                  <span className="line-through mr-1">{formatMoney(item.originalBasePrice)}</span>
                                )}
                                {formatMoney(toNumber(getItemUnitTotal(item)))} c/u
                              </div>
                              {item.appliedSpecialPriceRuleName && (
                                <div className="text-[11px] text-emerald-600">Oferta aplicada</div>
                              )}
                            </div>
                            <div className="text-center text-xs text-muted-foreground">x{item.quantity}</div>
                            <div className="text-right font-semibold">{formatMoney(toNumber(getItemUnitTotal(item)) * toNumber(item.quantity))}</div>
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
                  <SplitPanel
                    enabled={splitEnabled}
                    onEnabledChange={setSplitEnabled}
                    totalCents={checkoutTotalCents}
                    parts={parts}
                    onPartsChange={setParts}
                    activePartId={activePartId}
                    onActivePartIdChange={setActivePartId}
                  />

                  {splitEnabled && activeSplitPart && (
                    <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium">
                      Cobrando Parte {parts.findIndex((part) => part.id === activeSplitPart.id) + 1}: {formatMoney(activeSplitPart.amountCents / 100)}
                    </div>
                  )}
                </div>

                <div className="sticky bottom-0 z-30 shrink-0 space-y-3 border-t bg-background px-4 py-4 sm:px-6">
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

                  <div ref={cashInputsContainerRef} className="grid grid-cols-2 gap-3">
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

                  {activeTenderField && (
                    <div ref={keypadRef} className="grid grid-cols-4 gap-2">
                      {DENOMINATION_CENTS.map((value) => (
                        <Button key={value} type="button" variant="outline" onClick={() => applyTenderDenomination(value)}>
                          {formatMoney(value / 100)}
                        </Button>
                      ))}
                      <Button type="button" variant="outline" onClick={clearTenderField}>Borrar</Button>
                      <Button type="button" variant="outline" onClick={backspaceTenderField}>←</Button>
                      <Button type="button" variant="outline" className="col-span-2" onClick={setExactTenderAmount}>Exacto</Button>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1" onClick={() => setIsPaymentOpen(false)}>Cerrar</Button>
                    <Button className="flex-1" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || paymentAmountValue <= 0 || (splitEnabled && !splitValidation.isValid)}>
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

          <div className="pt-2">
            <Button className="h-12 w-full" onClick={handleAddPendingProduct} disabled={!canAddPendingProduct}>
              {selectedExtrasCount > 0 ? `Agregar (${selectedExtrasCount} extras)` : "Agregar"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isManualProductOpen} onOpenChange={setIsManualProductOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Agregar producto manual</DialogTitle>
            <DialogDescription>Este producto solo existe en esta venta.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Nombre *</Label>
              <Input value={manualName} onChange={(e) => setManualName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Cantidad *</Label>
                <Input type="number" min={1} step={1} value={manualQty} onChange={(e) => setManualQty(e.target.value)} />
              </div>
              <div>
                <Label>Precio unitario *</Label>
                <Input type="number" min={0.01} step={0.01} value={manualPrice} onChange={(e) => setManualPrice(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Nota</Label>
              <Input value={manualNote} onChange={(e) => setManualNote(e.target.value)} />
            </div>
            <Button className="w-full" onClick={handleAddManualProduct}>Agregar al carrito</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPinModalOpen} onOpenChange={setIsPinModalOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Código de acceso</DialogTitle>
            <DialogDescription>Ingresa el PIN de 4 dígitos para autorizar cambio de precio.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-center text-2xl tracking-[0.4em]">{Array.from({ length: 4 }).map((_, i) => (pinInput[i] ? "●" : "○")).join(" ")}</div>
            <div className="grid grid-cols-3 gap-2">
              {[1,2,3,4,5,6,7,8,9].map((n) => (
                <Button key={n} variant="outline" className="h-12" onClick={async () => {
                  const next = `${pinInput}${n}`.slice(0, 4);
                  setPinInput(next);
                  if (next.length === 4) {
                    try {
                      await validateOrderPricePin(next);
                      setValidatedPin(next);
                      const activeItem = cart.find((item) => item.id === priceEditorItemId);
                      setNewPriceInput((activeItem ? getItemBaseEffective(activeItem) : 0).toFixed(2));
                      setIsPinModalOpen(false);
                      setIsPriceModalOpen(true);
                    } catch (error) {
                      toast.error(error instanceof Error ? error.message : "Código incorrecto");
                      setPinInput("");
                    }
                  }
                }}>{n}</Button>
              ))}
              <Button variant="outline" className="h-12" onClick={() => setPinInput("")}>Limpiar</Button>
              <Button variant="outline" className="h-12" onClick={async () => {
                const next = `${pinInput}0`.slice(0, 4);
                setPinInput(next);
                if (next.length === 4) {
                  try {
                    await validateOrderPricePin(next);
                    setValidatedPin(next);
                    const activeItem = cart.find((item) => item.id === priceEditorItemId);
                    setNewPriceInput((activeItem ? getItemBaseEffective(activeItem) : 0).toFixed(2));
                    setIsPinModalOpen(false);
                    setIsPriceModalOpen(true);
                  } catch (error) {
                    toast.error(error instanceof Error ? error.message : "Código incorrecto");
                    setPinInput("");
                  }
                }
              }}>0</Button>
              <Button variant="outline" className="h-12" onClick={() => setPinInput((prev) => prev.slice(0, -1))}><Delete className="h-4 w-4" /></Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPriceModalOpen} onOpenChange={setIsPriceModalOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Nuevo precio (solo esta venta)</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input inputMode="decimal" value={newPriceInput} onChange={(e) => setNewPriceInput(e.target.value.replace(/[^\d.]/g, ""))} />
            <Button className="w-full" onClick={applyPriceOverride} disabled={!validatedPin}>Aplicar</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default POS;
