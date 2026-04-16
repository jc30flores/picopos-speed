import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, Trash2, ShoppingCart, Wallet, ChevronDown, ChevronUp, Delete, PencilLine, BadgePercent, LayoutGrid, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney, toCents, toNumber } from "@/lib/money";
import { resolveEffectiveUnitPrice } from "@/lib/pricing";
import { formatDateTimeSV } from "@/lib/datetime";
import { calculatePosPricing } from "@/lib/posPricing";
import { SplitPanel } from "@/components/pos/SplitPanel";
import { SplitPart, splitEvenly, validateParts } from "@/lib/splitPayments";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
  setOrderSendToKitchen,
  getPaymentMethods,
  getOrderById,
  updateOrderCustomerDte,
  createPrintJob,
  markPrintJobPrinted,
  getActiveTaxConfig,
  getCategories,
  getModifierGroups,
  getProducts,
  getCurrentCashSession,
  getDefaultConsumerCustomer,
  listCustomers,
  createCustomer,
  listDepartments,
  listMunicipalities,
  listActivities,
  openCashSession,
  closeCashSession,
  getCashTransactions,
  createCashPayout,
  openCashDrawer,
  downloadCashSessionTicketPdf,
  downloadPaymentTicketPdf,
  validateOrderPricePin,
  getActiveDiscounts,
  getPendingOrders,
  setOrderPending,
  printPaymentTicket,
  getPrintingStatus,
  Category,
  Discount,
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
import { usePrivilegedActionGuard } from "@/hooks/usePrivilegedActionGuard";
import { PrivilegePinModal } from "@/components/pos/PrivilegePinModal";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { ClockSV } from "@/components/ClockSV";

interface CartItem {
  id: string;
  sourceOrderItemId?: number;
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
  requiresKitchen?: boolean;
  modifiers: Array<{ id?: number; name: string; price: number }>;
}

const DEFAULT_CUSTOMER_EMAIL = "facturasPDG23@gmail.com";
const digitsOnly = (value: string) => value.replace(/\D+/g, "");
const formatPhone = (raw: string) => {
  const digits = digitsOnly(raw).slice(0, 8);
  if (!digits) return "";
  if (digits.length <= 4) return digits;
  return `${digits.slice(0, 4)}-${digits.slice(4)}`;
};

const getItemModifierTotal = (item: CartItem) => (item.modifiers || []).reduce((sum, mod) => sum + Number(mod.price || 0), 0);
const getItemBaseEffective = (item: CartItem) => (item.unitPriceOverride != null ? Number(item.unitPriceOverride) : Number(item.basePrice));
const getItemUnitTotal = (item: CartItem) => getItemBaseEffective(item) + getItemModifierTotal(item);

const getPaidExtrasLines = (item: CartItem) =>
  (item.modifiers || []).filter((modifier) => modifier.price > 0).map((modifier) => ({
    name: modifier.name,
    price: modifier.price,
  }));

const mapOrderItemToCartItem = (item: Order["items"][number]): CartItem => {
  const basePrice = Number(item.unitPriceFinal ?? item.price ?? 0);
  const modifiers = Array.isArray(item.modifiers)
    ? item.modifiers.map((name) => ({ name, price: 0 }))
    : [];
  return {
    id: `order-item-${item.id}`,
    sourceOrderItemId: item.id,
    productId: item.productId ?? null,
    name: item.assignedName || item.productName,
    basePrice,
    originalBasePrice: item.unitPriceBeforeDiscount ?? basePrice,
    price: basePrice,
    quantity: item.quantity,
    isCustom: Boolean(item.isCustom),
    customCode: item.code,
    assignedName: item.assignedName,
    unitPriceOverride: item.unitPriceOverride ?? null,
    modifiers,
  };
};

const DENOMINATION_CENTS = [500, 1000, 2000, 5000, 10000, 25, 50, 100];

const parseMoneyToCents = (value: string): number => Math.max(0, toCents(value));

const centsToInput = (value: number): string => (Math.max(0, value) / 100).toFixed(2);
const normalizeServiceTypeKey = (value: string, available: Array<{ key: string }>) => {
  const normalized = String(value || "").trim().toUpperCase();
  if (!normalized) return "";
  const exact = available.find((item) => item.key === normalized);
  if (exact) return exact.key;
  const insensitive = available.find((item) => String(item.key || "").trim().toUpperCase() === normalized);
  return insensitive?.key ?? "";
};

const DrawerIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 11h18" />
    <rect x="8" y="13" width="8" height="4" rx="1" />
  </svg>
);


const POS = () => {
type CashCloseFlowState = "idle" | "closingInProgress" | "pendingUserAck";
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [serviceType, setServiceType] = useState<string>("");
  const { activeServiceTypes: serviceTypes } = useServiceTypes();
  const [isExtrasOpen, setIsExtrasOpen] = useState(false);

  const [isCashDialogOpen, setIsCashDialogOpen] = useState(false);
  const [isPayoutDialogOpen, setIsPayoutDialogOpen] = useState(false);
  const [isOpenSessionModalOpen, setIsOpenSessionModalOpen] = useState(false);
  const [pendingOrdersCount, setPendingOrdersCount] = useState(0);
  const [isPendingChoiceOpen, setIsPendingChoiceOpen] = useState(false);
  const [cashSnapshot, setCashSnapshot] = useState<CashSessionSnapshot>({ open: false });
  const [isCashGateLoading, setIsCashGateLoading] = useState(true);
  const [cashTransactions, setCashTransactions] = useState<CashTransaction[]>([]);
  const [openSessionAmount, setOpenSessionAmount] = useState("0.00");
  const [closeBillsInput, setCloseBillsInput] = useState("");
  const [closeCoinsInput, setCloseCoinsInput] = useState("");
  const [closePosCardsInput, setClosePosCardsInput] = useState("");
  const [closePedidosYaInput, setClosePedidosYaInput] = useState("");
  const [closeCashStep, setCloseCashStep] = useState<"idle" | "bills" | "coins" | "posCards" | "pedidosYa" | "confirm">("idle");
  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutDescription, setPayoutDescription] = useState("");
  const [cashNotes, setCashNotes] = useState("");
  const [isSavingCashAction, setIsSavingCashAction] = useState(false);
  const [isOpeningDrawer, setIsOpeningDrawer] = useState(false);
  const lastDrawerOpenAtRef = useRef<number>(0);
  const openSessionInputRef = useRef<HTMLInputElement | null>(null);
  const postOpenSessionActionRef = useRef<(() => Promise<void>) | null>(null);
  const openSessionResolverRef = useRef<((opened: boolean) => void) | null>(null);
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
  const [isPaymentMethodOpen, setIsPaymentMethodOpen] = useState(false);
  const [isCustomerDteOpen, setIsCustomerDteOpen] = useState(false);
  const [isSplitConfigOpen, setIsSplitConfigOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [cardType, setCardType] = useState<"debit" | "credit" | null>(null);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>([]);
  const [selectedPaymentMethodCode, setSelectedPaymentMethodCode] = useState<string>("cash");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [defaultConsumerCustomer, setDefaultConsumerCustomer] = useState<Customer | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [isCustomerPickerOpen, setIsCustomerPickerOpen] = useState(false);
  const [customerSearch, setCustomerSearch] = useState("");
  const [isCustomerCreateOpen, setIsCustomerCreateOpen] = useState(false);
  const [isSavingCustomer, setIsSavingCustomer] = useState(false);
  const [customerFormErrors, setCustomerFormErrors] = useState<Record<string, string>>({});
  const [customerServerErrors, setCustomerServerErrors] = useState<Record<string, string>>({});
  const [departments, setDepartments] = useState<Array<{ code: string; name: string }>>([]);
  const [municipalities, setMunicipalities] = useState<Array<{ code: string; department_code: string; name: string }>>([]);
  const [activities, setActivities] = useState<Array<{ code: string; description: string }>>([]);
  const [activitySearch, setActivitySearch] = useState("");
  const [customerForm, setCustomerForm] = useState({
    fullName: "",
    clientType: "CF" as "CF" | "CCF" | "SX",
    companyName: "",
    dui: "",
    nit: "",
    nrc: "",
    phone: "",
    email: "",
    direccion: "",
    departmentCode: "",
    municipalityCode: "",
    activityCode: "",
    activityDescription: "",
  });
  const [dteDocumentType, setDteDocumentType] = useState<"CF" | "CCF" | "SX">("CF");
  const [ivaExempt, setIvaExempt] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [tipAmount, setTipAmount] = useState("");
  const [activeTenderField, setActiveTenderField] = useState<"payment" | "tip" | null>(null);
  const [shouldResetTenderOnFirstTap, setShouldResetTenderOnFirstTap] = useState(true);
  const cashInputsContainerRef = useRef<HTMLDivElement | null>(null);
  const keypadRef = useRef<HTMLDivElement | null>(null);
  const cartItemsScrollRef = useRef<HTMLDivElement | null>(null);
  const cartEndRef = useRef<HTMLDivElement | null>(null);
  const previousCartLengthRef = useRef(0);
  const [paymentReference, setPaymentReference] = useState("");
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [isSendingToPending, setIsSendingToPending] = useState(false);
  const [isPendingReferenceDialogOpen, setIsPendingReferenceDialogOpen] = useState(false);
  const [pendingReferenceDraft, setPendingReferenceDraft] = useState("");
  const [pendingEditAuthorizationPin, setPendingEditAuthorizationPin] = useState("");
  const [isKitchenPromptOpen, setIsKitchenPromptOpen] = useState(false);
  const [kitchenPromptOrderId, setKitchenPromptOrderId] = useState<number | null>(null);
  const [isSubmittingKitchenChoice, setIsSubmittingKitchenChoice] = useState(false);
  const [postSaleKitchenChoice, setPostSaleKitchenChoice] = useState(true);
  const [postSalePrintChoice, setPostSalePrintChoice] = useState(true);
  const [printerAvailable, setPrinterAvailable] = useState(true);
  const [fallbackPdfModal, setFallbackPdfModal] = useState<{
    open: boolean;
    title: string;
    message: string;
    onDownload: null | (() => Promise<void>);
    shouldHardReloadAfterClose: boolean;
  }>({
    open: false,
    title: "",
    message: "",
    onDownload: null,
    shouldHardReloadAfterClose: false,
  });
  const [cashCloseFlowState, setCashCloseFlowState] = useState<CashCloseFlowState>("idle");
  const [lastPaymentId, setLastPaymentId] = useState<number | null>(null);
  const [splitEnabled, setSplitEnabled] = useState(false);
  const [parts, setParts] = useState<SplitPart[]>([]);
  const [activePartId, setActivePartId] = useState<string | null>(null);
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [createdOrderNumber, setCreatedOrderNumber] = useState<number | null>(null);
  const [receiptJob, setReceiptJob] = useState<PrintJob | null>(null);
  const [isReceiptPreviewOpen, setIsReceiptPreviewOpen] = useState(false);
  const hardReloadTriggeredRef = useRef(false);
  const hydratedPendingOrderIdRef = useRef<number | null>(null);
  const consumedNavSourceRef = useRef(false);
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
  const [isDiscountDialogOpen, setIsDiscountDialogOpen] = useState(false);
  const [discountSearch, setDiscountSearch] = useState("");
  const canManageCashOperations = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "cashier");
  const canManageCashPayouts = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canCloseCash = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canViewSensitiveCash = Boolean(user?.isSuperuser || user?.role === "admin");
  const [availableDiscounts, setAvailableDiscounts] = useState<Discount[]>([]);
  const [selectedDiscount, setSelectedDiscount] = useState<Discount | null>(null);
  const [isLoadingDiscounts, setIsLoadingDiscounts] = useState(false);
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
  const privilegedGuard = usePrivilegedActionGuard();
  const draftRestoreDoneRef = useRef(false);
  const draftPersistTimeoutRef = useRef<number | null>(null);
  const selectedBranchId = Number(localStorage.getItem("selected_branch_id") || "0") || 0;
  const posDraftStorageKey = useMemo(
    () => `pos_draft_${selectedBranchId}_${user?.id ?? "anon"}`,
    [selectedBranchId, user?.id]
  );

  const cartPricing = useMemo(
    () =>
      calculatePosPricing({
        items: cart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
        products,
        serviceType,
        serviceTypes,
        selectedDiscount,
        availableDiscounts,
      }),
    [availableDiscounts, cart, products, selectedDiscount, serviceType, serviceTypes]
  );
  const { itemsGross, subtotal, discountTotal: discountAmount, disposableTotal: cartDisposableTotal, total } = cartPricing;

  const loadMenuData = async () => {
    const [categoriesResponse, modifierGroupsResponse] = await Promise.all([
      getCategories(),
      getModifierGroups(),
    ]);
    setCategories(categoriesResponse);
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
    const pendingOrderId = Number(searchParams.get("pending_order_id") || "0");
    const mode = String(searchParams.get("mode") || "").trim().toLowerCase();
    const cameFromPendingParams = pendingOrderId > 0 && Number.isFinite(pendingOrderId);
    const cameFromOpenOrdersNavigation = Boolean((location.state as { fromOpenOrders?: boolean } | null)?.fromOpenOrders);
    const shouldSuppressPendingChoice = cameFromPendingParams || mode === "edit" || mode === "pay" || cameFromOpenOrdersNavigation;
    getPendingOrders({ branchId: selectedBranchId || undefined })
      .then((res) => {
        setPendingOrdersCount(res.count);
        if (!shouldSuppressPendingChoice) {
          setIsPendingChoiceOpen(res.count > 0);
        } else {
          setIsPendingChoiceOpen(false);
        }
      })
      .catch(() => {
        setPendingOrdersCount(0);
      });
  }, [location.state, searchParams, selectedBranchId]);

  useEffect(() => {
    const cameFromOpenOrdersNavigation = Boolean((location.state as { fromOpenOrders?: boolean } | null)?.fromOpenOrders);
    if (!cameFromOpenOrdersNavigation || consumedNavSourceRef.current) return;
    consumedNavSourceRef.current = true;
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    const pendingOrderId = Number(searchParams.get("pending_order_id") || "0");
    const mode = String(searchParams.get("mode") || "").trim().toLowerCase();
    if (!pendingOrderId || !Number.isFinite(pendingOrderId)) return;
    if (hydratedPendingOrderIdRef.current === pendingOrderId) return;
    hydratedPendingOrderIdRef.current = pendingOrderId;
    setCart([]);
    setCheckoutDraft(null);
    setSelectedDiscount(null);
    setActiveOrder(null);
    console.info("open_order.pos_loader.source", { order_id: pendingOrderId, mode, total_db: null, items: 0 });
    getOrderById(pendingOrderId)
      .then((order) => {
        const restoredCart = (order.items || []).map((item) => mapOrderItemToCartItem(item));
        const hydratedPricing = calculatePosPricing({
          items: restoredCart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
          products,
          serviceType: order.serviceType || serviceType,
          serviceTypes,
          selectedDiscount: null,
          availableDiscounts: [],
        });
        console.info("open_order.pos_loader.source", {
          order_id: order.id,
          mode,
          total_db: order.totalPayable ?? order.total,
          items: restoredCart.length,
        });
        console.info("open_order.pos_loader.recomputed_totals", {
          order_id: order.id,
          subtotal: hydratedPricing.subtotal,
          discounts: hydratedPricing.discountTotal,
          fees: hydratedPricing.disposableTotal,
          total: hydratedPricing.total,
          items: restoredCart.length,
        });
        setActiveOrder(order);
        setCreatedOrderId(order.id);
        setCreatedOrderNumber(order.orderNumber);
        setPendingReferenceDraft(order.pendingReference || "");
        setPendingEditAuthorizationPin("");
        setSelectedDiscount(null);
        setSelectedCustomerId(order.customerId ? String(order.customerId) : "");
        setCart(restoredCart);
        setCheckoutDraft({
          items: restoredCart,
          subtotal: hydratedPricing.subtotal,
          tax: order.taxTotal ?? 0,
          total: hydratedPricing.total,
          taxRate,
          serviceType: order.serviceType || serviceType,
          createdAt: Date.now(),
        });
        setServiceType(order.serviceType || serviceType);
        if (mode === "pay") {
          console.info("open_order.pay.load", {
            order_id: order.id,
            total_db: order.totalPayable ?? order.total,
            total_rebuilt: hydratedPricing.total,
          });
          setIsPaymentOpen(true);
        } else {
          setIsPaymentOpen(false);
          setIsPaymentMethodOpen(false);
        }
        navigate("/pos", { replace: true, state: { fromOpenOrders: true } });
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "No se pudo retomar la orden pendiente."));
  }, [navigate, searchParams, serviceType, taxRate, products, serviceTypes]);

  useEffect(() => {
    if (!serviceTypes.length) return;
    const normalizedServiceType = normalizeServiceTypeKey(serviceType, serviceTypes);
    if (!normalizedServiceType) {
      setServiceType(serviceTypes[0].key);
      return;
    }
    if (normalizedServiceType !== serviceType) {
      setServiceType(normalizedServiceType);
    }
  }, [serviceTypes, serviceType]);

  useEffect(() => {
    if (!serviceTypes.length || draftRestoreDoneRef.current) return;
    const raw = localStorage.getItem(posDraftStorageKey);
    draftRestoreDoneRef.current = true;
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as {
        cart?: CartItem[];
        serviceType?: string;
        selectedCustomerId?: string;
        selectedDiscount?: Discount | null;
        dteDocumentType?: "CF" | "CCF" | "SX";
        ivaExempt?: boolean;
      };
      const restoredCart = Array.isArray(parsed.cart) ? parsed.cart : [];
      if (restoredCart.length > 0) {
        setCart(restoredCart);
      }
      const restoredServiceType = normalizeServiceTypeKey(parsed.serviceType || "", serviceTypes);
      if (restoredServiceType) setServiceType(restoredServiceType);
      if (parsed.selectedCustomerId) setSelectedCustomerId(parsed.selectedCustomerId);
      if (restoredCart.length > 0 && parsed.selectedDiscount) setSelectedDiscount(parsed.selectedDiscount);
      if (parsed.dteDocumentType) setDteDocumentType(parsed.dteDocumentType);
      if (typeof parsed.ivaExempt === "boolean") setIvaExempt(parsed.ivaExempt);
    } catch (error) {
      console.error("Failed to restore POS draft", error);
    }
  }, [posDraftStorageKey, serviceTypes]);

  useEffect(() => {
    if (!draftRestoreDoneRef.current) return;
    if (draftPersistTimeoutRef.current) window.clearTimeout(draftPersistTimeoutRef.current);
    draftPersistTimeoutRef.current = window.setTimeout(() => {
      if (cart.length === 0 && !selectedDiscount && !selectedCustomerId) {
        localStorage.removeItem(posDraftStorageKey);
        return;
      }
      localStorage.setItem(
        posDraftStorageKey,
        JSON.stringify({
          cart,
          serviceType,
          selectedCustomerId,
          selectedDiscount: cart.length > 0 ? selectedDiscount : null,
          dteDocumentType,
          ivaExempt,
        })
      );
    }, 250);
    return () => {
      if (draftPersistTimeoutRef.current) window.clearTimeout(draftPersistTimeoutRef.current);
    };
  }, [cart, dteDocumentType, ivaExempt, posDraftStorageKey, selectedCustomerId, selectedDiscount, serviceType]);

  useEffect(() => {
    if (!serviceTypes.length || !serviceType) return;
    const selectedServiceType = serviceTypes.find((item) => item.key === serviceType);
    if (!selectedServiceType) return;
    let cancelled = false;
    getProducts({ orderTypeId: selectedServiceType.id })
      .then((rows) => {
        if (cancelled) return;
        setProducts(rows);
      })
      .catch((error) => {
        if (cancelled) return;
        console.error("Failed to refresh products for service type", error);
      });
    return () => {
      cancelled = true;
    };
  }, [serviceType, serviceTypes]);

  useEffect(() => {
    if (!products.length) return;
    setCart((prev) =>
      prev.map((item) => {
        if (!item.productId || item.unitPriceOverride != null || item.isCustom) return item;
        const latestProduct = products.find((candidate) => candidate.id === item.productId);
        if (!latestProduct) return item;
        const pricing = resolveEffectiveUnitPrice(latestProduct, serviceType, new Date(), Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
        return {
          ...item,
          basePrice: pricing.effectivePrice,
          originalBasePrice: pricing.display.showOfferBadge ? pricing.basePrice : undefined,
          appliedSpecialPriceRuleName: pricing.appliedRule?.name ?? null,
          price: pricing.effectivePrice + getItemModifierTotal(item),
        };
      })
    );
  }, [products, serviceType]);

  const loadActiveDiscounts = async () => {
    try {
      setIsLoadingDiscounts(true);
      const discounts = await getActiveDiscounts({ serviceType, subtotal: itemsGross });
      setAvailableDiscounts(discounts);
    } catch (error) {
      console.error("Failed to load active discounts", error);
      toast.error("No se pudieron cargar los descuentos");
    } finally {
      setIsLoadingDiscounts(false);
    }
  };

  useEffect(() => {
    if (!serviceType) return;
    void loadActiveDiscounts();
  }, [serviceType, itemsGross]);

  useEffect(() => {
    if (cart.length > 0 || activeOrder) return;
    if (!selectedDiscount) return;
    setSelectedDiscount(null);
  }, [activeOrder, cart.length, selectedDiscount]);

  useEffect(() => {
    if (paymentMethod !== "cash") {
      setActiveTenderField(null);
    }
  }, [paymentMethod]);
  useEffect(() => {
    if (dteDocumentType !== "CCF" && ivaExempt) {
      setIvaExempt(false);
    }
  }, [dteDocumentType, ivaExempt]);

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

  useLayoutEffect(() => {
    if (cart.length > previousCartLengthRef.current) {
      cartEndRef.current?.scrollIntoView({ block: "end" });
    }
    previousCartLengthRef.current = cart.length;
  }, [cart]);

  useEffect(() => {
    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, []);

  useEffect(() => {
    if (!isKitchenPromptOpen) return;
    getPrintingStatus()
      .then((status) => setPrinterAvailable(status.available))
      .catch(() => setPrinterAvailable(false));
  }, [isKitchenPromptOpen]);

  const openCheckoutFromItems = (items: CartItem[]) => {
    if (items.length === 0) return;
    const draftPricing = calculatePosPricing({
      items: items.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
      products,
      serviceType,
      serviceTypes,
      selectedDiscount,
      availableDiscounts,
    });
    const draftTotal = draftPricing.total;
    const draftTaxIncluded = draftTotal - draftTotal / (1 + taxRate);
    const draft = {
      items: [...items],
      subtotal: draftPricing.subtotal,
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
    setIsPaymentMethodOpen(false);
  };

  const addToCart = (product: Product, modifiers: Array<{ id?: number; name: string; price: number }>) => {
    const pricing = resolveEffectiveUnitPrice(product, serviceType, new Date(), Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
    const effectiveBasePrice = pricing.effectivePrice;
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
          originalBasePrice: pricing.display.showOfferBadge ? pricing.basePrice : undefined,
          price: totalPrice,
          quantity: 1,
          isCustom: false,
          appliedSpecialPriceRuleName: pricing.appliedRule?.name ?? null,
          requiresKitchen: Boolean(product.requiresKitchen),
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
    if (activeOrder?.isPending && (activeOrder.sendToKitchen || ["preparing", "ready", "delivered"].includes(String(activeOrder.status || "")))) {
      toast.error("No se pueden eliminar productos: la orden ya fue enviada a cocina.");
      return;
    }
    const isPrivileged = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
    const requiresPinForPendingEdit = Boolean(activeOrder?.isPending && !isPrivileged);
    if (requiresPinForPendingEdit && !pendingEditAuthorizationPin) {
      privilegedGuard.requirePrivilege("removePendingItem", () => {
        setCart((prev) => prev.filter((item) => item.id !== itemId));
      });
      return;
    }
    setCart(cart.filter((item) => item.id !== itemId));
  };

  const openItemPriceEditor = (itemId: string) => {
    setPriceEditorItemId(itemId);
    setPinInput("");
    setValidatedPin("");
    const isPrivileged = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
    const activeItem = cart.find((item) => item.id === itemId);
    setNewPriceInput((activeItem ? getItemBaseEffective(activeItem) : 0).toFixed(2));
    if (isPrivileged) {
      setValidatedPin("BYPASS");
      setIsPriceModalOpen(true);
      return;
    }
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
        requiresKitchen: false,
        modifiers: [],
      },
    ]);
    setManualName("");
    setManualQty("1");
    setManualPrice("");
    setManualNote("");
    setIsManualProductOpen(false);
  };

  const canonicalDueCents = activeOrder
    ? (() => {
      const hasItems = activeOrder.items.length > 0;
      const remainingFromCents = Number.isFinite(activeOrder.remainingCents) ? Math.max(activeOrder.remainingCents ?? 0, 0) : 0;
      const remainingFromDecimal = Math.max(toCents(activeOrder.remaining), 0);
      const payableFallback = Math.max(toCents(activeOrder.totalPayable ?? activeOrder.total), 0);
      if (remainingFromCents > 0) return remainingFromCents;
      if (remainingFromDecimal > 0) return remainingFromDecimal;
      if (hasItems && activeOrder.paymentStatus !== "paid") return payableFallback;
      return 0;
    })()
    : toCents(checkoutDraft?.total ?? 0);
  const paymentTotal = canonicalDueCents / 100;
  const paymentStatus = activeOrder?.paymentStatus ?? "unpaid";
  const isPaid = paymentStatus === "paid";
  const paymentAmountValue = toNumber(paymentAmount);
  const tipAmountValue = toNumber(tipAmount);
  const checkoutTotal = paymentTotal;
  const checkoutTotalCents = canonicalDueCents;
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
  const checkoutDraftPricing = useMemo(
    () =>
      checkoutDraft
        ? calculatePosPricing({
            items: checkoutDraft.items.map((item) => ({
              productId: item.productId,
              quantity: item.quantity,
              unitTotal: getItemUnitTotal(item),
            })),
            products,
            serviceType: checkoutDraft.serviceType,
            serviceTypes,
            selectedDiscount,
            availableDiscounts,
          })
        : null,
    [availableDiscounts, checkoutDraft, products, selectedDiscount, serviceTypes]
  );
  const checkoutDisposableTotal = checkoutDraftPricing?.disposableTotal ?? 0;
  const checkoutSummarySubtotalBefore = checkoutDraftPricing?.subtotal ?? activeOrder?.subtotalBeforeDiscounts ?? checkoutDraft?.subtotal ?? subtotal;
  const checkoutSummaryDiscount = checkoutDraftPricing?.discountTotal ?? (activeOrder ? Math.max((activeOrder.subtotalBeforeDiscounts ?? activeOrder.total) - (activeOrder.totalPayable ?? activeOrder.total), 0) : discountAmount);
  const checkoutSummaryTotal = checkoutDraftPricing?.total ?? activeOrder?.totalPayable ?? paymentTotal;
  const checkoutDiscountLines = checkoutDraftPricing?.discountLines ?? cartPricing.discountLines;
  const filteredDiscounts = availableDiscounts.filter((discount) =>
    discount.name.toLowerCase().includes(discountSearch.toLowerCase().trim())
  );

  useEffect(() => {
    if (!isPaymentOpen) return;
    console.info("open_order.pay.modal_totals", {
      order_id: activeOrder?.id ?? null,
      subtotal: checkoutSummarySubtotalBefore,
      discounts: checkoutSummaryDiscount,
      fees: checkoutDisposableTotal,
      total: checkoutSummaryTotal,
    });
  }, [activeOrder?.id, activeOrder?.isPending, checkoutDisposableTotal, checkoutSummaryDiscount, checkoutSummarySubtotalBefore, checkoutSummaryTotal, isPaymentOpen]);

  const proceedToCheckout = async () => {
    if (cart.length === 0) return;

    const draftPricing = calculatePosPricing({
      items: cart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
      products,
      serviceType,
      serviceTypes,
      selectedDiscount,
      availableDiscounts,
    });
    const draftTotal = draftPricing.total;
    const draftTaxIncluded = draftTotal - draftTotal / (1 + taxRate);
    const draft = {
      items: [...cart],
      subtotal: draftPricing.subtotal,
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
    let order = activeOrder;
    if (order?.isPending) {
      order = await syncExistingOpenOrder(order);
      order = await getOrderById(order.id);
      setActiveOrder(order);
    } else if (!hasSameDraft || !order) {
      order = await createOrder({
        serviceType: draft.serviceType,
        source: "pos",
        channel: "pos",
        sendToKitchen: draft.serviceType === "KIOSK",
        priceChangePin: draft.items.some((item) => item.unitPriceOverride != null) ? validatedPin : undefined,
        customerId: selectedCustomerId ? Number(selectedCustomerId) : undefined,
        dteDocumentType,
        ivaExempt,
        discountId: selectedDiscount?.id,
        discountMode: selectedDiscount ? "manual" : undefined,
        items: draft.items.map((item) => ({
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
      setActiveOrder(order);
      setCreatedOrderId(order.id);
      setCreatedOrderNumber(order.orderNumber ?? null);
      console.info("open_order.save.start", { id: order.id, is_update: false });
    } else {
      order = await getOrderById(order.id);
      setActiveOrder(order);
    }
    const dueCents = typeof order.remainingCents === "number" ? order.remainingCents : Math.round(toNumber(order.remaining) * 100);
    setPaymentAmount(centsToInput(dueCents));
    setTipAmount("0");
    setPaymentReference("");
    setSplitEnabled(false);
    const initialParts = splitEvenly(dueCents, 1);
    setParts(initialParts);
    setActivePartId(initialParts[0]?.id ?? null);
    setIsPaymentOpen(true);
  };

  const requestOpenSession = (postAction?: () => Promise<void>, resolver?: (opened: boolean) => void) => {
    postOpenSessionActionRef.current = postAction ?? null;
    openSessionResolverRef.current = resolver ?? null;
    setOpenSessionAmount("0.00");
    setIsOpenSessionModalOpen(true);
    setTimeout(() => openSessionInputRef.current?.select(), 0);
  };

  const ensureCashSessionOpen = async (postAction: () => Promise<void>) => {
    try {
      const current = await getCurrentCashSession();
      setCashSnapshot(current);
      if (current.open) {
        await postAction();
        return true;
      }
      return await new Promise<boolean>((resolve) => {
        requestOpenSession(postAction, resolve);
      });
    } catch {
      return await new Promise<boolean>((resolve) => {
        requestOpenSession(postAction, resolve);
      });
    }
  };

  const handleCheckout = async () => {
    if (cart.length === 0) return;
    if (isOpenSessionModalOpen && !cashSnapshot.open) return;
    try {
      await ensureCashSessionOpen(async () => {
        await proceedToCheckout();
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (/caja no aperturada|cash session|required/i.test(message)) {
        try {
          const current = await getCurrentCashSession();
          setCashSnapshot(current);
          if (!current.open) {
            requestOpenSession();
            return;
          }
          toast.error(message || "Conflicto al crear orden");
        } catch {
          requestOpenSession();
        }
        return;
      }
      toast.error(message || "No se pudo continuar al cobro");
    }
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
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.info("[cash-debug] current-session", { open: snapshot.open, sessionId: snapshot.session?.id ?? null });
      }
      setCashSnapshot(snapshot);
      setCashTransactions(transactions);
      const shouldDelayOpenGate = cashCloseFlowState === "pendingUserAck" || cashCloseFlowState === "closingInProgress";
      if (!snapshot.open && !shouldDelayOpenGate) {
        setIsOpenSessionModalOpen(true);
      } else {
        setIsOpenSessionModalOpen(false);
      }
    } catch (error) {
      console.error("Failed to load cash data", error);
      toast.error("No se pudo cargar información de caja");
      setIsOpenSessionModalOpen(true);
      setCashSnapshot({ open: false });
    } finally {
      setIsCashGateLoading(false);
    }
  };

  useEffect(() => {
    loadCashData().catch(() => undefined);
    const forceCashGate = () => {
      setCashSnapshot((previous) => ({ ...previous, open: false }));
      if (cashCloseFlowState === "pendingUserAck" || cashCloseFlowState === "closingInProgress") {
        return;
      }
      setIsOpenSessionModalOpen(true);
    };
    window.addEventListener("cash:required", forceCashGate as EventListener);
    return () => {
      window.removeEventListener("cash:required", forceCashGate as EventListener);
    };
  }, [cashCloseFlowState]);

  useEffect(() => {
    getPaymentMethods().then((methods) => {
      setPaymentMethods(methods);
      const first = methods.find((method) => String(method.code || "").toLowerCase() === "cash") || methods[0];
      if (first) {
        setSelectedPaymentMethodCode(first.code);
        const code = (first.code || "").toLowerCase();
        const fallback = first.isCash ? "cash" : code.startsWith("card") ? "card" : "transfer";
        setPaymentMethod(fallback as PaymentMethod);
      }
    }).catch(() => undefined);
  }, []);

  const refreshCustomers = async (search = "") => {
    const next = await listCustomers(search);
    setCustomers(next);
    return next;
  };

  useEffect(() => {
    refreshCustomers().catch(() => undefined);
    Promise.all([listDepartments(), listActivities(""), getDefaultConsumerCustomer()])
      .then(([deptRows, activityRows, consumerFinal]) => {
        setDepartments(deptRows);
        setActivities(activityRows);
        setDefaultConsumerCustomer(consumerFinal);
        setSelectedCustomerId(String(consumerFinal.id));
        setDteDocumentType("CF");
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const departmentCode = customerForm.departmentCode;
    if (!departmentCode) return;
    listMunicipalities(departmentCode)
      .then((rows) => {
        setMunicipalities(rows);
        if (!rows.some((row) => row.code === customerForm.municipalityCode)) {
          setCustomerForm((prev) => ({ ...prev, municipalityCode: rows[0]?.code ?? "" }));
        }
      })
      .catch(() => undefined);
  }, [customerForm.departmentCode, customerForm.municipalityCode]);

  useEffect(() => {
    const selected = customers.find((c) => String(c.id) === selectedCustomerId);
    if (selected?.clientType) {
      setDteDocumentType(selected.clientType);
    }
  }, [selectedCustomerId, customers]);

  useEffect(() => {
    const selected = customers.find((c) => String(c.id) === selectedCustomerId);
    if (selected && selected.clientType !== dteDocumentType) {
      setSelectedCustomerId("");
      toast.warning("Selecciona un cliente compatible con el tipo DTE");
    }
    if (dteDocumentType === "CF" && !selectedCustomerId && defaultConsumerCustomer) {
      setSelectedCustomerId(String(defaultConsumerCustomer.id));
    }
  }, [dteDocumentType, customers, selectedCustomerId, defaultConsumerCustomer]);

  const paymentMethodButtons = useMemo(() => {
    const byCode = new Map(paymentMethods.map((method) => [String(method.code || "").toLowerCase(), method]));
    const desiredCodes = ["cash", "card", "transfer", "pedidos_ya", "paypal"] as const;
    return desiredCodes
      .map((code) => {
        const method = byCode.get(code);
        if (!method) return null;
        return {
          code,
          label: method.name || (code === "card" ? "Tarjeta" : code),
          method: code === "cash" ? ("cash" as PaymentMethod) : code === "card" ? ("card" as PaymentMethod) : ("transfer" as PaymentMethod),
        };
      })
      .filter((item): item is { code: "cash" | "card" | "transfer" | "pedidos_ya" | "paypal"; label: string; method: PaymentMethod } => Boolean(item));
  }, [paymentMethods]);

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
    const normalizedMethod = normalizePaymentMethodForOrderType(serviceType, selectedPaymentMethodCode);
    if (normalizedMethod === "pedidos_ya") {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.info("[pos-debug] auto_payment_method", { serviceType, method: "pedidos_ya" });
      }
      setPaymentMethod("transfer");
      if (selectedPaymentMethodCode !== "pedidos_ya") {
        setSelectedPaymentMethodCode("pedidos_ya");
      }
      setCardType(null);
      if (isPaymentMethodOpen) {
        setPaymentAmount(toNumber(expectedPaymentCents / 100).toFixed(2));
      }
      return;
    }
    if (normalizedMethod === "cash" && selectedPaymentMethodCode === "pedidos_ya") {
      setPaymentMethod("cash");
      setSelectedPaymentMethodCode("cash");
      setCardType(null);
    }
  }, [expectedPaymentCents, isPaymentMethodOpen, selectedPaymentMethodCode, serviceType]);

  useEffect(() => {
    if (!isPaymentOpen || !checkoutDraft) return;
    if (parts.length === 0) {
      const initialParts = splitEvenly(checkoutTotalCents, 1);
      setParts(initialParts);
      setActivePartId(initialParts[0]?.id ?? null);
    }
  }, [checkoutTotalCents, isPaymentOpen, checkoutDraft, parts.length]);

  const handleOpenCashSession = async () => {
    if (isSavingCashAction) return;
    setIsSavingCashAction(true);
    try {
      await openCashSession(Number(openSessionAmount || 0));
      const current = await getCurrentCashSession();
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.info("[cash-debug] open-session-refetch", { open: current.open, sessionId: current.session?.id ?? null });
      }
      setCashSnapshot(current);
      if (!current.open) {
        toast.error("No se pudo confirmar apertura de caja.");
        openSessionResolverRef.current?.(false);
        return;
      }
      await loadCashData();
      const action = postOpenSessionActionRef.current;
      postOpenSessionActionRef.current = null;
      setIsOpenSessionModalOpen(false);
      if (action) {
        try {
          await action();
        } catch (actionError) {
          const message = actionError instanceof Error ? actionError.message : "Error en checkout";
          toast.error(message);
        }
      }
      openSessionResolverRef.current?.(true);
      toast.success("Caja aperturada");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error desconocido";
      if (message.includes("409") || message.toLowerCase().includes("abierta")) {
        try {
          const current = await getCurrentCashSession();
          setCashSnapshot(current);
          if (current.open) {
            setIsOpenSessionModalOpen(false);
            const action = postOpenSessionActionRef.current;
            postOpenSessionActionRef.current = null;
            if (action) {
              try {
                await action();
              } catch (actionError) {
                const actionMessage = actionError instanceof Error ? actionError.message : "Error en checkout";
                toast.error(actionMessage);
              }
            }
            openSessionResolverRef.current?.(true);
            toast.success("Caja ya estaba aperturada");
            return;
          }
        } catch {
          // fallback to generic error below
        }
      }
      openSessionResolverRef.current?.(false);
      toast.error(`No se pudo aperturar la caja: ${message}`);
    } finally {
      openSessionResolverRef.current = null;
      setIsSavingCashAction(false);
    }
  };

  const handleCloseCashSession = async () => {
    if (!canCloseCash) {
      toast.error("No tienes permisos para cerrar caja.");
      return;
    }
    if (pendingOrdersCount > 0) {
      toast.error(`You cannot close the register because there are ${pendingOrdersCount} open orders.`);
      return;
    }
    const totalBills = Number(closeBillsInput || 0);
    const totalCoins = Number(closeCoinsInput || 0);
    const totalPosCards = Number(closePosCardsInput || 0);
    const totalPedidosYa = Number(closePedidosYaInput || 0);
    const countedTotal = totalBills + totalCoins;
    if (
      !Number.isFinite(totalBills) || totalBills < 0
      || !Number.isFinite(totalCoins) || totalCoins < 0
      || !Number.isFinite(totalPosCards) || totalPosCards < 0
      || !Number.isFinite(totalPedidosYa) || totalPedidosYa < 0
    ) {
      toast.error("Ingresa montos válidos para el cierre.");
      return;
    }
    setCashCloseFlowState("closingInProgress");
    setIsSavingCashAction(true);
    try {
      const closeResp = await closeCashSession(
        countedTotal,
        cashNotes,
        { bills: totalBills, coins: totalCoins, posCards: totalPosCards, pedidosYa: totalPedidosYa },
        { sessionId: cashSnapshot.session?.id }
      );
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.info("[cash-close-flow] close_success", { sessionId: closeResp.sessionId ?? null, printed: closeResp.printed, printError: closeResp.printError ?? null });
      }
      if (closeResp.printed) {
        setCashCloseFlowState("idle");
        toast.success("Caja cerrada. Ticket impreso");
        setIsCashDialogOpen(false);
        setIsOpenSessionModalOpen(false);
        navigate("/");
      } else {
        setCashCloseFlowState("pendingUserAck");
        if (import.meta.env.DEV) {
          // eslint-disable-next-line no-console
          console.info("[cash-close-flow] fallback_modal_opened");
        }
        setFallbackPdfModal({
          open: true,
          title: "Caja cerrada",
          message: "No se pudo imprimir. Puedes descargar el PDF del cierre.",
          onDownload: async () => {
            if (!closeResp.sessionId) throw new Error("No se encontró la sesión cerrada.");
            await downloadCashSessionTicketPdf(closeResp.sessionId);
            if (import.meta.env.DEV) {
              // eslint-disable-next-line no-console
              console.info("[cash-close-flow] user_ack_download");
            }
            setFallbackPdfModal((prev) => ({ ...prev, open: false }));
            setCashCloseFlowState("idle");
            setIsCashDialogOpen(false);
            setIsOpenSessionModalOpen(false);
            navigate("/");
          },
          shouldHardReloadAfterClose: false,
        });
        toast.warning(`Caja cerrada, pero no se pudo imprimir: ${closeResp.printError || "Error desconocido"}`);
      }
      await loadCashData();
      setCloseCashStep("idle");
      setCloseBillsInput("");
      setCloseCoinsInput("");
      setClosePosCardsInput("");
      setClosePedidosYaInput("");
      
    } catch (error) {
      setCashCloseFlowState("idle");
      toast.error(error instanceof Error ? error.message : "No se pudo cerrar caja");
    } finally {
      setIsSavingCashAction(false);
    }
  };

  const buildPendingPayloadItems = (items: CartItem[]) =>
    items.map((item) => ({
      sourceOrderItemId: item.sourceOrderItemId,
      productId: item.productId,
      productName: item.name,
      price: getItemBaseEffective(item),
      quantity: item.quantity,
      isCustom: Boolean(item.isCustom),
      unitPriceOverride: item.unitPriceOverride ?? null,
      customCode: item.customCode,
      assignedName: item.assignedName,
      modifiers: item.modifiers.map((mod) => ({ id: mod.id, name: mod.name, price: mod.price })),
    }));

  const syncExistingOpenOrder = async (order: Order) => {
    const pricing = calculatePosPricing({
      items: cart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
      products,
      serviceType,
      serviceTypes,
      selectedDiscount: null,
      availableDiscounts,
    });
    console.info("open_order.update.request", { order_id: order.id, is_update: true });
    console.info("open_order.save.payload", {
      id: order.id,
      total_front: pricing.total,
      items: cart.length,
      subtotal_front: pricing.subtotal,
      discount_front: pricing.discountTotal,
      fees_front: pricing.disposableTotal,
    });
    const saved = await setOrderPending(order.id, {
      isPending: true,
      pendingState: order.paymentStatus === "paid" ? "paid_pending_delivery" : "pending_payment",
      pendingReference: pendingReferenceDraft.trim() || order.pendingReference || "",
      authorizationPin: pendingEditAuthorizationPin,
      items: buildPendingPayloadItems(cart),
    });
    console.info("open_order.save.done", {
      id: saved.id,
      total_saved: saved.totalPayable,
      subtotal_saved: saved.subtotalBeforeDiscounts,
      discount_saved: saved.discountTotal,
      fees_saved: saved.disposableTotal,
    });
    return saved;
  };

  const handleSendOrderToPending = async () => {
    if (isSendingToPending) return;
    if (!pendingReferenceDraft.trim()) {
      setIsPendingReferenceDialogOpen(true);
      return;
    }
    setIsSendingToPending(true);
    try {
      let order = activeOrder;
      if (!order) {
        order = await createOrder({
          serviceType,
          customerName: selectedCustomer?.fullName || selectedCustomer?.name || "CONSUMIDOR FINAL",
          customerId: selectedCustomer ? Number(selectedCustomer.id) : undefined,
          dteDocumentType,
          ivaExempt,
          source: "pos",
          channel: "pos",
          items: cart.map((item) => ({
            productId: item.productId,
            productName: item.name,
            price: getItemBaseEffective(item),
            quantity: item.quantity,
            isCustom: Boolean(item.isCustom),
            type: item.isCustom ? "manual" : "menu",
            unitPriceOverride: item.unitPriceOverride ?? null,
            customCode: item.customCode,
            assignedName: item.assignedName,
            modifiers: item.modifiers.map((mod) => ({ id: mod.id, name: mod.name, price: mod.price })),
          })),
        });
      }
      const pendingState = order.paymentStatus === "paid" ? "paid_pending_delivery" : "pending_payment";
      const saved = activeOrder?.isPending
        ? await syncExistingOpenOrder(order)
        : await setOrderPending(order.id, {
            isPending: true,
            pendingState,
            pendingReference: pendingReferenceDraft.trim(),
            authorizationPin: pendingEditAuthorizationPin,
            items: buildPendingPayloadItems(cart),
          });
      if (!activeOrder?.isPending) {
        console.info("open_order.save.start", { id: saved.id, is_update: false });
      }
      if (!saved.isPending) {
        throw new Error("Order was not persisted as Open Order.");
      }
      toast.success("Orden guardada en Open Orders");
      const latestPending = await getPendingOrders({ branchId: selectedBranchId || undefined });
      setPendingOrdersCount(latestPending.count);
      setCart([]);
      setActiveOrder(null);
      setCheckoutDraft(null);
      setCreatedOrderId(null);
      setCreatedOrderNumber(null);
      setPendingReferenceDraft("");
      setPendingEditAuthorizationPin("");
      setIsPendingReferenceDialogOpen(false);
      clearPersistedDraft();
      navigate("/open-orders");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar la orden en Open Orders.");
    } finally {
      setIsSendingToPending(false);
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
    if (!cashSnapshot.open) return;
    const now = Date.now();
    if (now - lastDrawerOpenAtRef.current < 500) return;
    lastDrawerOpenAtRef.current = now;
    setIsOpeningDrawer(true);
    try {
      await triggerDrawerOpen({ showSuccessToast: true });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo abrir el cajón");
    } finally {
      setIsOpeningDrawer(false);
    }
  };

  const isCashPaymentSelected = (method: PaymentMethod, methodCode?: string): boolean => {
    if (method === "cash") return true;
    const normalizedCode = String(methodCode || "").trim().toLowerCase();
    return ["cash", "efectivo"].some((token) => normalizedCode.includes(token));
  };

  const triggerDrawerOpen = async ({ showSuccessToast }: { showSuccessToast: boolean }): Promise<boolean> => {
    const result = await openCashDrawer();
    if (result.ok) {
      if (showSuccessToast) toast.success("Gaveta abierta");
      return true;
    }
    toast.error(`No se pudo abrir la gaveta: ${result.message}`);
    return false;
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

  const clearPersistedDraft = () => {
    localStorage.removeItem(posDraftStorageKey);
  };

  const finalizePaidSale = () => {
    setIsPaymentOpen(false);
    setIsPaymentMethodOpen(false);
    setActiveOrder(null);
    setCart([]);
    setSelectedDiscount(null);
    setCheckoutDraft(null);
    setCreatedOrderId(null);
    setCreatedOrderNumber(null);
    setSplitEnabled(false);
    setParts([]);
    setActivePartId(null);
    setKitchenPromptOrderId(null);
    setDteDocumentType("CF");
    if (defaultConsumerCustomer) {
      setSelectedCustomerId(String(defaultConsumerCustomer.id));
    } else {
      setSelectedCustomerId("");
    }
    hydratedPendingOrderIdRef.current = null;
    clearPersistedDraft();
    navigate("/pos", { replace: true, state: { fromOpenOrders: true } });
  };

  const scheduleReload = () => {
    window.setTimeout(() => {
      loadCashData().catch(() => undefined);
    }, 250);
  };

  const hardReloadPos = useCallback((reason: string) => {
    if (hardReloadTriggeredRef.current) return;
    hardReloadTriggeredRef.current = true;
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.info("[pos-debug] hard_reload", { reason });
    }
    window.location.reload();
  }, []);

  const normalizeOrderTypeKey = (value: string | null | undefined) =>
    String(value || "")
      .trim()
      .toUpperCase()
      .replace(/\s+/g, "_");

  const ORDER_TYPE_PEDIDOS_YA = "PEDIDOS_YA";

  const isPedidosYaOrderType = (value: string | null | undefined) => {
    const normalized = normalizeOrderTypeKey(value);
    return normalized === ORDER_TYPE_PEDIDOS_YA || normalized === "PEDIDOSYA" || normalized === "DELIVERY";
  };

  const normalizePaymentMethodForOrderType = (orderTypeCode: string | null | undefined, currentMethodCode: string) => {
    if (isPedidosYaOrderType(orderTypeCode)) {
      return "pedidos_ya";
    }
    if (String(currentMethodCode || "").toLowerCase() === "pedidos_ya") {
      return "cash";
    }
    return currentMethodCode;
  };

  const scheduleHardReload = (reason: string) => {
    if (hardReloadTriggeredRef.current) return;
    window.setTimeout(() => hardReloadPos(reason), 400);
  };

  const triggerPdfDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 500);
  };

  const handleKitchenChoice = async (shouldSend: boolean) => {
    if (!kitchenPromptOrderId || isSubmittingKitchenChoice) return;
    try {
      setIsSubmittingKitchenChoice(true);
      if (shouldSend) {
        try {
          await setOrderSendToKitchen(kitchenPromptOrderId, true);
        } catch (error) {
          await setOrderSendToKitchen(kitchenPromptOrderId, true);
          if (import.meta.env.DEV) {
            console.debug("Kitchen send retry succeeded", error);
          }
        }
        toast.success("Venta enviada a cocina");
      } else {
        toast.success("Venta completada sin envío a cocina");
      }
      if (lastPaymentId && postSalePrintChoice) {
        const printResult = await printPaymentTicket(lastPaymentId);
        if (printResult.pdfBlob) {
        setFallbackPdfModal({
          open: true,
          title: "Ticket de venta",
          message: "No se pudo imprimir. Puedes descargar el PDF del ticket.",
          onDownload: async () => {
            triggerPdfDownload(printResult.pdfBlob as Blob, printResult.pdfFilename || `ticket_pago_${lastPaymentId}.pdf`);
          },
          shouldHardReloadAfterClose: true,
        });
          toast.warning("Impresora no detectada.");
        } else if (!printResult.printed && printResult.receiptPdfUrl) {
        setFallbackPdfModal({
          open: true,
          title: "Ticket de venta",
          message: "No se pudo imprimir. Puedes descargar el PDF del ticket.",
          onDownload: async () => {
            await downloadPaymentTicketPdf(lastPaymentId);
          },
          shouldHardReloadAfterClose: true,
        });
          toast.warning("Impresora no detectada.");
        } else if (!printResult.printed && printResult.printError) {
        setFallbackPdfModal({
          open: true,
          title: "Ticket de venta",
          message: "No se pudo imprimir. Puedes descargar el PDF del ticket.",
          onDownload: async () => {
            await downloadPaymentTicketPdf(lastPaymentId);
          },
          shouldHardReloadAfterClose: true,
        });
          toast.warning(`Pago registrado, pero no se pudo imprimir: ${printResult.printError}`);
        }
        if (printResult.drawerError) {
          toast.warning(printResult.drawerError);
        }
      }
      setIsKitchenPromptOpen(false);
      finalizePaidSale();
      scheduleReload();
    } catch (error) {
      console.error("Failed to update send_to_kitchen", error);
      toast.error("No se pudo enviar a cocina. La venta se guardó. Puedes reenviar luego.");
      setIsKitchenPromptOpen(false);
      finalizePaidSale();
      scheduleReload();
    } finally {
      setIsSubmittingKitchenChoice(false);
    }
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
    const splitPartAmount = splitEnabled ? (activeSplitPart?.amountCents ?? expectedPaymentCents) / 100 : null;
    const paymentAmountForApi = splitEnabled ? (splitPartAmount ?? expectedPaymentCents / 100) : remainingOrderAmount;

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
      if (!order && createdOrderId) {
        order = await getOrderById(createdOrderId);
        setCreatedOrderNumber(order.orderNumber ?? null);
        setActiveOrder(order);
      }
      if (!order) throw new Error("No active order for checkout");
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
          ? Math.min(paymentAmountForApi, latestRemaining)
          : paymentMethod === "cash"
            ? latestRemaining
            : Math.min(paymentAmountForApi, latestRemaining);

      const paymentResult = await createPayment({
        orderId,
        method: paymentMethod,
        cardType: paymentMethod === "card" ? "credit" : undefined,
        amount: amountForApi,
        amountApplied: amountForApi,
        cashReceived: amountReceived,
        tipAmount: tipValue,
        reference: paymentReference || undefined,
        paymentMethodCode: selectedPaymentMethodCode,
        splitPart: splitEnabled && activeSplitPart ? (parts.findIndex((part) => part.id === activeSplitPart.id) + 1) : undefined,
      });
      setLastPaymentId(paymentResult.id);
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
        if (refreshed.isPending) {
          try {
            const finalizedOrder = await setOrderPending(refreshed.id, {
              isPending: false,
              removalReason: "Pagada en POS",
              completionType: "paid",
            });
            console.info("open_order.finalize_paid", {
              id: finalizedOrder.id,
              subtotal: finalizedOrder.subtotalBeforeDiscounts,
              discount_total: finalizedOrder.discountTotal,
              fees_total: finalizedOrder.disposableTotal,
              total: finalizedOrder.totalPayable,
            });
            setActiveOrder(finalizedOrder);
          } catch (pendingError) {
            console.error("Failed to finalize open order state after payment", pendingError);
          }
        }
        const isKiosk = String(refreshed.serviceType || "").toUpperCase() === "KIOSK";
        if (isKiosk) {
          toast.success("Pago y factura registrados. Enviado a cocina.");
          finalizePaidSale();
        } else {
          const hasKitchenItems = Boolean(refreshed.requiresKitchen);
          toast.success("Pago y factura registrados.");
          setKitchenPromptOrderId(orderId);
          setPostSaleKitchenChoice(hasKitchenItems);
          setPostSalePrintChoice(true);
          setIsKitchenPromptOpen(true);
        }
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
  const normalizedCustomerSearch = customerSearch.trim().toLowerCase();
  const customersByDte = customers.filter((customer) => customer.clientType === dteDocumentType);
  const filteredCustomers = useMemo(() => {
    if (!normalizedCustomerSearch) return customersByDte;
    return customersByDte.filter((customer) => {
      const haystack = [
        customer.fullName,
        customer.email ?? "",
        customer.phone ?? "",
        customer.dui ?? "",
        customer.nit ?? "",
        customer.numDocumento ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedCustomerSearch);
    });
  }, [customersByDte, normalizedCustomerSearch]);
  const visibleCustomers = filteredCustomers.slice(0, 4);
  const handleAcceptCustomerDte = async () => {
    if (!selectedCustomerId) {
      toast.error("Selecciona un cliente");
      return;
    }
    if (activeOrder) {
      try {
        const updatedOrder = await updateOrderCustomerDte(activeOrder.id, {
          customerId: Number(selectedCustomerId),
          dteDocumentType,
          ivaExempt,
        });
        setActiveOrder((previousOrder) => {
          if (!previousOrder || previousOrder.id !== updatedOrder.id) return updatedOrder;
          const fallbackRemaining = previousOrder.remaining > 0 ? previousOrder.remaining : 0;
          const fallbackRemainingCents = previousOrder.remainingCents > 0 ? previousOrder.remainingCents : toCents(fallbackRemaining);
          const nextRemaining = updatedOrder.remaining > 0 ? updatedOrder.remaining : fallbackRemaining;
          const nextRemainingCents =
            updatedOrder.remainingCents > 0 || nextRemaining <= 0
              ? updatedOrder.remainingCents
              : fallbackRemainingCents;
          return {
            ...previousOrder,
            ...updatedOrder,
            remaining: nextRemaining,
            remainingCents: nextRemainingCents,
            total: updatedOrder.total > 0 ? updatedOrder.total : previousOrder.total,
            subtotalBeforeDiscounts:
              (updatedOrder.subtotalBeforeDiscounts ?? 0) > 0
                ? updatedOrder.subtotalBeforeDiscounts
                : previousOrder.subtotalBeforeDiscounts,
            totalPayable:
              (updatedOrder.totalPayable ?? 0) > 0
                ? updatedOrder.totalPayable
                : previousOrder.totalPayable,
          };
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "No se pudo actualizar cliente en la orden");
        return;
      }
    }
    setIsCustomerDteOpen(false);
  };
  const filteredActivities = useMemo(() => {
    const term = activitySearch.trim().toLowerCase();
    if (!term) return activities.slice(0, 30);
    return activities
      .filter((activity) => `${activity.code} ${activity.description}`.toLowerCase().includes(term))
      .slice(0, 30);
  }, [activities, activitySearch]);

  const validateCustomerForm = () => {
    const errors: Record<string, string> = {};
    const fullName = customerForm.fullName.trim();
    if (!fullName) errors.fullName = "Nombre requerido";
    if (!customerForm.departmentCode) errors.departmentCode = "Departamento requerido";
    if (!customerForm.municipalityCode) errors.municipalityCode = "Municipio requerido";
    if (customerForm.clientType === "CCF") {
      if (!customerForm.companyName.trim()) errors.companyName = "Empresa requerida";
      if (customerForm.nit.replace(/\D/g, "").length !== 14) errors.nit = "NIT de 14 dígitos";
      if (!customerForm.nrc.trim()) errors.nrc = "NRC requerido";
      if (customerForm.phone.replace(/\D/g, "").length !== 8) errors.phone = "Teléfono de 8 dígitos";
      const email = customerForm.email.trim();
      if (!email || !email.includes("@") || !email.includes(".")) errors.email = "Email válido requerido";
      if (!customerForm.direccion.trim()) errors.direccion = "Dirección requerida";
      if (!customerForm.activityCode.trim() && !customerForm.activityDescription.trim()) errors.activityCode = "Actividad económica requerida";
    }
    if (customerForm.clientType === "SX") {
      if (!customerForm.dui.trim() && !customerForm.nit.trim()) errors.dui = "Documento requerido";
      if (!customerForm.direccion.trim()) errors.direccion = "Dirección requerida";
    }
    setCustomerFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const preloadCustomerFormFromDTE = async (targetType: "CF" | "CCF" | "SX") => {
    if (targetType === "CF") {
      const base = defaultConsumerCustomer ?? (await getDefaultConsumerCustomer());
      if (!defaultConsumerCustomer) setDefaultConsumerCustomer(base);
      const deptCode = base.departmentCode || "12";
      const muniRows = await listMunicipalities(deptCode);
      setMunicipalities(muniRows);
      setCustomerForm((prev) => ({
        ...prev,
        clientType: "CF",
        companyName: "",
        nit: "",
        nrc: "",
        activityCode: "",
        activityDescription: "",
        phone: base.phone || "0000-0000",
        email: base.email || DEFAULT_CUSTOMER_EMAIL,
        direccion: base.direccion || "SAN MIGUEL",
        departmentCode: deptCode,
        municipalityCode: base.municipalityCode || muniRows[0]?.code || "",
      }));
      return;
    }
    const deptCode = departments[0]?.code || "12";
    const muniRows = await listMunicipalities(deptCode);
    setMunicipalities(muniRows);
    setCustomerForm((prev) => ({
      ...prev,
      clientType: targetType,
      departmentCode: prev.departmentCode || deptCode,
      municipalityCode: prev.municipalityCode || muniRows[0]?.code || "",
    }));
  };

  const handleCreateCustomerFromPOS = async () => {
    if (!validateCustomerForm()) {
      toast.error("Revisa los campos requeridos");
      return;
    }
    try {
      setIsSavingCustomer(true);
      setCustomerServerErrors({});
      const created = await createCustomer({
        fullName: customerForm.fullName.trim(),
        clientType: customerForm.clientType,
        companyName: customerForm.companyName.trim(),
        dui: customerForm.dui.trim(),
        nit: customerForm.nit.trim(),
        nrc: customerForm.nrc.trim(),
        phone: formatPhone(customerForm.phone.trim()),
        email: customerForm.email.trim() || undefined,
        direccion: customerForm.direccion.trim(),
        departmentCode: customerForm.departmentCode,
        municipalityCode: customerForm.municipalityCode,
        activityCode: customerForm.activityCode.trim(),
        activityDescription: customerForm.activityDescription.trim(),
      });
      await refreshCustomers();
      setSelectedCustomerId(String(created.id));
      setIsCustomerCreateOpen(false);
      setIsCustomerPickerOpen(false);
      setCustomerSearch("");
      setCustomerFormErrors({});
      setCustomerForm({
        fullName: "",
        clientType: "CF",
        companyName: "",
        dui: "",
        nit: "",
        nrc: "",
        phone: "",
        email: "",
        direccion: "",
        departmentCode: "",
        municipalityCode: "",
        activityCode: "",
        activityDescription: "",
      });
      toast.success("Cliente creado");
    } catch (error) {
      if (error instanceof Error) {
        try {
          const parsed = JSON.parse(error.message) as Record<string, string[] | string>;
          const mapped: Record<string, string> = {};
          Object.entries(parsed).forEach(([key, value]) => {
            mapped[key] = Array.isArray(value) ? String(value[0]) : String(value);
          });
          setCustomerServerErrors(mapped);
        } catch {
          toast.error(error.message || "No se pudo crear el cliente");
        }
      } else {
        toast.error("No se pudo crear el cliente");
      }
    } finally {
      setIsSavingCustomer(false);
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

  if (isCashGateLoading) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Verificando estado de caja...</div>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] overflow-x-hidden overflow-y-hidden bg-background">
      <div className="h-full min-h-0 px-2 pb-4 pt-4 lg:px-4">
        <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[60%_40%]">
          {/* Products Section */}
          <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
            {/* Search & Filters */}
            <Card className="p-4">
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    className="h-12 w-12 shrink-0 rounded-full"
                    onClick={() => navigate("/")}
                    aria-label="Menú principal"
                    title="Menú principal"
                  >
                    <LayoutGrid className="h-5 w-5" />
                  </Button>
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar productos..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-12 pl-10 text-base"
                  />
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-2.5 pb-1">
                  {["Todos", ...categories.filter((cat) => !cat.isHidden && !cat.name.toUpperCase().includes("SIN CATEGORÍA")).map((cat) => cat.name)].map((cat) => (
                    <Badge
                      key={cat}
                      variant={selectedCategory === cat ? "default" : "outline"}
                      className={cn(
                        "inline-flex min-h-14 cursor-pointer items-center whitespace-nowrap rounded-full px-5 py-2 text-base transition-all",
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
            <div className="flex-1 overflow-y-auto pb-4">
                <div className="grid items-start grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                  {filteredProducts.map((product) => {
                    const productPricing = resolveEffectiveUnitPrice(
                      product,
                      serviceType,
                      new Date(),
                      Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
                    );
                    return (
                    <Card
                      key={product.id}
                    className="cursor-pointer p-4 hover-lift"
                    onClick={() => handleProductClick(product)}
                  >
                    <h3 className="font-semibold text-sm mb-1 line-clamp-2">{product.name}</h3>
                    {productPricing.display.showOfferBadge && (
                      <Badge className="mb-1 max-w-full truncate bg-emerald-600 text-white">
                        {productPricing.appliedRule?.name?.trim() || "OFERTA"}
                      </Badge>
                    )}
                    <div className="space-y-0.5">
                      {productPricing.display.showOfferBadge && (
                        <p className="text-xs text-muted-foreground line-through">${product.price.toFixed(2)}</p>
                      )}
                      <p className="text-base font-bold text-secondary">${productPricing.effectivePrice.toFixed(2)}</p>
                    </div>
                  </Card>
                );
                })}
              </div>
            </div>
          </div>

          {/* Cart Section */}
          <Card className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden lg:min-w-[360px]">
            <div className="flex-none border-b p-4">
              <div className="mb-3 space-y-2">
                <div className="grid grid-cols-[auto_1fr_auto] items-center gap-2">
                  <ClockSV className="px-3 py-2" timeClassName="text-base sm:text-lg" />
                  <h2 className="text-xl font-bold text-center">Pedido Actual</h2>
                  <div className="flex items-center justify-end gap-2">
                    <TooltipProvider delayDuration={120}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            title="Producto manual"
                            aria-label="Producto manual"
                            className="h-11 w-11 rounded-xl border-emerald-500/60"
                            onClick={() =>
                              privilegedGuard.requirePrivilege("manualProduct", () => setIsManualProductOpen(true))
                            }
                          >
                            <Plus className="h-5 w-5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Producto manual</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider delayDuration={120}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="icon"
                            title="Descuentos"
                            aria-label="Descuentos"
                            className="h-11 w-11 rounded-xl"
                            onClick={() =>
                              privilegedGuard.requirePrivilege("discounts", () => setIsDiscountDialogOpen(true))
                            }
                          >
                            <BadgePercent className="h-5 w-5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Descuentos</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider delayDuration={120}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="icon"
                            title="Transacciones de caja"
                            aria-label="Transacciones de caja"
                            className="h-11 w-11 rounded-xl"
                            onClick={() =>
                              privilegedGuard.requirePrivilege("cashTransactions", () => {
                                setIsCashDialogOpen(true);
                                loadCashData().catch(() => undefined);
                              })
                            }
                          >
                            <Wallet className="h-5 w-5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Transacciones de caja</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider delayDuration={120}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="icon"
                            title="Refrescar"
                            aria-label="Refrescar"
                            className="h-11 w-11 rounded-xl"
                            onClick={() => hardReloadPos("toolbar_refresh")}
                          >
                            <RefreshCw className="h-5 w-5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Refrescar</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              </div>

            </div>

            <div className="flex-none border-b px-4 py-3">
              <div className="flex flex-wrap gap-2">
                {serviceTypes.length > 0 ? (
                  serviceTypes.map((type) => (
                    <Button
                      key={type.id}
                      variant={serviceType === type.key ? "default" : "outline"}
                      size="sm"
                      onClick={() => setServiceType(type.key)}
                      className="min-h-14 min-w-fit whitespace-nowrap px-4 text-base"
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

            <div ref={cartItemsScrollRef} className="min-h-0 flex-1 overflow-y-auto p-4">
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
                          {!item.appliedSpecialPriceRuleName && item.originalBasePrice != null && item.originalBasePrice !== item.basePrice && (
                            <p className="text-[11px] text-emerald-600/90">OFERTA</p>
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
                            <Button variant="ghost" size="icon" onClick={() => openItemPriceEditor(item.id)} className="h-10 w-10" title="Cambiar precio para esta venta">
                              <PencilLine className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => removeItem(item.id)}
                            className="h-10 w-10 text-danger"
                            disabled={Boolean(activeOrder?.isPending && (activeOrder.sendToKitchen || ["preparing", "ready", "delivered"].includes(String(activeOrder.status || ""))))}
                            title={activeOrder?.isPending && (activeOrder.sendToKitchen || ["preparing", "ready", "delivered"].includes(String(activeOrder.status || ""))) ? "Orden enviada a cocina: no se puede eliminar." : "Eliminar producto"}
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
                            className="h-10 w-10"
                          >
                            <Minus className="h-3 w-3" />
                          </Button>
                          <span className="w-8 text-center font-semibold">{item.quantity}</span>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => updateQuantity(item.id, 1)}
                            className="h-10 w-10"
                          >
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                        <span className="font-bold">${(getItemUnitTotal(item) * item.quantity).toFixed(2)}</span>
                      </div>
                    </Card>
                  ))}
                  <div ref={cartEndRef} />
                </div>
              )}
            </div>

            <div className="z-10 flex-none border-t bg-background p-4 space-y-3">
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
                {cartPricing.discountLines.map((line) => (
                  <div key={`${line.source}-${line.id}`} className="flex justify-between text-emerald-600">
                    <span>Descuento ({line.name})</span>
                    <span>-{formatMoney(line.amount)}</span>
                  </div>
                ))}
                <div className="flex justify-between text-lg font-bold">
                  <span>Total</span>
                  <span className="text-secondary">{formatMoney(total)}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3">
                <Button
                  variant="default"
                  className="h-14 w-full text-base font-bold"
                  size="lg"
                  disabled={cart.length === 0 || isProcessingPayment}
                  onClick={handleCheckout}
                >
                  Cobrar {formatMoney(total)}
                </Button>
                <Button
                  variant="secondary"
                  className="h-14 w-full text-base"
                  onClick={() => {
                    const isCurrentOrderEmpty = cart.length === 0;
                    if (isCurrentOrderEmpty) {
                      navigate("/open-orders");
                      return;
                    }
                    void handleSendOrderToPending();
                  }}
                  disabled={isSendingToPending}
                >
                  {isSendingToPending
                    ? "Guardando..."
                    : cart.length === 0
                      ? "Guardadas"
                      : "Guardar"}
                </Button>
                <Button
                  variant="outline"
                  className="h-14 w-full text-base"
                  onClick={() => {
                    setCart([]);
                    setSelectedDiscount(null);
                    clearPersistedDraft();
                  }}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <Dialog open={isPendingReferenceDialogOpen} onOpenChange={setIsPendingReferenceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Referencia requerida</DialogTitle>
            <DialogDescription>Ingresa una referencia para enviar la orden a Open Orders.</DialogDescription>
          </DialogHeader>
          <Input
            value={pendingReferenceDraft}
            onChange={(event) => setPendingReferenceDraft(event.target.value)}
            placeholder="Ej: Mesa 4 / Nombre cliente"
            maxLength={120}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsPendingReferenceDialogOpen(false)}>Cancelar</Button>
            <Button onClick={() => void handleSendOrderToPending()} disabled={!pendingReferenceDraft.trim()}>
              Enviar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isPendingChoiceOpen} onOpenChange={setIsPendingChoiceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Open orders detected</DialogTitle>
            <DialogDescription>
              There are {pendingOrdersCount} active open orders. Do you want to continue to POS or review Open Orders?
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={() => setIsPendingChoiceOpen(false)}>Go to POS</Button>
            <Button onClick={() => navigate("/open-orders")}>Open Orders</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isDiscountDialogOpen}
        onOpenChange={(open) => {
          if (import.meta.env.DEV && open) {
            // eslint-disable-next-line no-console
            console.info("[discount-debug] modal_open", {
              manualDiscountId: selectedDiscount?.id ?? null,
              autoDiscountCandidates: availableDiscounts.filter((discount) => discount.autoApply).map((discount) => ({
                id: discount.id,
                name: discount.name,
                availableNow: discount.availableNow,
              })),
            });
          }
          setIsDiscountDialogOpen(open);
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Seleccionar descuento</DialogTitle>
            <DialogDescription>Aplica un descuento manual al pedido actual (solo 1 por pedido).</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              placeholder="Buscar descuento..."
              value={discountSearch}
              onChange={(event) => setDiscountSearch(event.target.value)}
            />
            {selectedDiscount ? (
              <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="font-semibold">{selectedDiscount.name}</p>
                  <p className="text-xs text-muted-foreground">Aplicado manualmente</p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedDiscount(null);
                    toast.success("Descuento removido");
                  }}
                >
                  Quitar descuento
                </Button>
              </div>
            ) : null}
            <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-1">
              {isLoadingDiscounts ? (
                <p className="text-sm text-muted-foreground">Cargando descuentos…</p>
              ) : filteredDiscounts.length === 0 ? (
                <p className="text-sm text-muted-foreground">No hay descuentos activos.</p>
              ) : (
                filteredDiscounts.map((discount) => (
                  <div key={discount.id} className="rounded-md border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">{discount.name}</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <Badge variant="secondary">{discount.type === "percent" ? `% ${discount.value}` : `$ ${discount.value}`}</Badge>
                          <Badge variant="outline">{discount.appliesTo === "order" ? "Ticket" : discount.appliesTo === "categories" ? "Categorías" : "Productos"}</Badge>
                          <Badge variant={discount.availableNow ? "default" : "secondary"}>
                            {discount.availableNow ? "Disponible ahora" : "Fuera de condiciones"}
                          </Badge>
                        </div>
                      </div>
                      <Button
                        onClick={() => {
                          let applyReason: "manual_click" | "out_of_conditions_confirm" = "manual_click";
                          if (!discount.availableNow) {
                            const confirmOut = window.confirm("Este descuento está fuera de condiciones. ¿Aplicar de todos modos?");
                            if (!confirmOut) return;
                            applyReason = "out_of_conditions_confirm";
                          }
                          if (selectedDiscount && selectedDiscount.id !== discount.id) {
                            const confirmReplace = window.confirm("Ya hay un descuento aplicado. ¿Reemplazarlo?");
                            if (!confirmReplace) return;
                          }
                          if (import.meta.env.DEV) {
                            // eslint-disable-next-line no-console
                            console.info("[discount-debug] manual_discount_apply", {
                              reason: applyReason,
                              discountId: discount.id,
                              discountName: discount.name,
                            });
                          }
                          setSelectedDiscount(discount);
                          setIsDiscountDialogOpen(false);
                          toast.success(`Descuento "${discount.name}" aplicado`);
                        }}
                      >
                        Aplicar
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isCashDialogOpen}
        onOpenChange={(open) => {
          setIsCashDialogOpen(open);
          if (!open) {
            setCloseCashStep("idle");
            setCloseBillsInput("");
            setCloseCoinsInput("");
          }
        }}
      >
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
              {canViewSensitiveCash && cashSnapshot.open && cashSnapshot.summary && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-muted-foreground">
                  <div>Efectivo inicial: {formatMoney(cashSnapshot.summary.openingCash)}</div>
                  <div>Efectivo ventas: {formatMoney(cashSnapshot.summary.totalCashSales)}</div>
                  <div>Tarjeta: {formatMoney(cashSnapshot.summary.methods.card)}</div>
                  <div>Transferencia: {formatMoney(cashSnapshot.summary.methods.transfer)}</div>
                  <div>Pedidos Ya: {formatMoney(cashSnapshot.summary.methods.pedidosYa)}</div>
                  <div>PayPal: {formatMoney(cashSnapshot.summary.methods.payPal)}</div>
                  <div>Pagos/gastos: -{formatMoney(cashSnapshot.summary.totalCashOut)}</div>
                  <div className="font-semibold text-foreground">Esperado en caja: {formatMoney(cashSnapshot.summary.expectedCashInDrawer)}</div>
                </div>
              )}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Button className="h-14 text-base font-semibold" onClick={() => requestOpenSession()} disabled={cashSnapshot.open || !canManageCashOperations}>
                {cashSnapshot.open ? "CAJA APERTURADA" : "APERTURAR CAJA"}
              </Button>
              <Button
                variant="destructive"
                className="h-14 text-base font-semibold bg-red-600 text-white hover:bg-red-700 active:bg-red-800 disabled:bg-red-300 disabled:text-red-50 dark:bg-red-700 dark:hover:bg-red-600 dark:active:bg-red-500 dark:disabled:bg-red-900 dark:disabled:text-red-200"
                onClick={() => setIsPayoutDialogOpen(true)}
                disabled={!cashSnapshot.open || !canManageCashPayouts}
              >
                PAGOS
              </Button>
              <TooltipProvider delayDuration={120}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={handleOpenDrawer}
                      disabled={isOpeningDrawer || !cashSnapshot.open || !canManageCashOperations}
                      className={`h-14 w-full ${!cashSnapshot.open ? "opacity-50 cursor-not-allowed" : ""}`}
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
                {!canCloseCash ? <div className="text-sm text-muted-foreground">No tienes permisos para cerrar caja.</div> : null}
                {canCloseCash && closeCashStep === "idle" ? (
                  <div className="space-y-3">
                    <div className="text-sm text-muted-foreground">Caja abierta.</div>
                    <Button
                      className="h-14 w-full text-base font-semibold bg-red-600 text-white hover:bg-red-700 active:bg-red-800 disabled:bg-red-300 disabled:text-red-50 dark:bg-red-700 dark:hover:bg-red-600 dark:active:bg-red-500 dark:disabled:bg-red-900 dark:disabled:text-red-200"
                      onClick={() => setCloseCashStep("bills")}
                    >
                      Iniciar cierre
                    </Button>
                  </div>
                ) : null}
                {canCloseCash && closeCashStep === "bills" ? (
                  <>
                    <div className="text-center text-2xl font-bold">Billetes</div>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      inputMode="decimal"
                      className="h-16 text-center text-2xl font-semibold"
                      placeholder="0.00"
                      value={closeBillsInput}
                      onChange={(e) => setCloseBillsInput(e.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("coins")} disabled={Number(closeBillsInput || 0) < 0}>Continuar</Button>
                    </div>
                  </>
                ) : null}
                {canCloseCash && closeCashStep === "coins" ? (
                  <>
                    <div className="text-center text-2xl font-bold">Monedas</div>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      inputMode="decimal"
                      className="h-16 text-center text-2xl font-semibold"
                      placeholder="0.00"
                      value={closeCoinsInput}
                      onChange={(e) => setCloseCoinsInput(e.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("bills")}>Atrás</Button>
                      <Button className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("posCards")} disabled={Number(closeCoinsInput || 0) < 0}>Continuar</Button>
                    </div>
                  </>
                ) : null}
                {canCloseCash && closeCashStep === "posCards" ? (
                  <>
                    <div className="text-center text-2xl font-bold">POS tarjetas</div>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      inputMode="decimal"
                      className="h-16 text-center text-2xl font-semibold"
                      placeholder="0.00"
                      value={closePosCardsInput}
                      onChange={(e) => setClosePosCardsInput(e.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("coins")}>Atrás</Button>
                      <Button className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("pedidosYa")} disabled={Number(closePosCardsInput || 0) < 0}>Continuar</Button>
                    </div>
                  </>
                ) : null}
                {canCloseCash && closeCashStep === "pedidosYa" ? (
                  <>
                    <div className="text-center text-2xl font-bold">PedidosYa</div>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      inputMode="decimal"
                      className="h-16 text-center text-2xl font-semibold"
                      placeholder="0.00"
                      value={closePedidosYaInput}
                      onChange={(e) => setClosePedidosYaInput(e.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("posCards")}>Atrás</Button>
                      <Button className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("confirm")} disabled={Number(closePedidosYaInput || 0) < 0}>Continuar</Button>
                    </div>
                  </>
                ) : null}
                {canCloseCash && closeCashStep === "confirm" ? (
                  <>
                    <div className="space-y-2 rounded-lg border p-3 text-base">
                      <div className="flex justify-between"><span>Total billetes</span><span>{formatMoney(Number(closeBillsInput || 0))}</span></div>
                      <div className="flex justify-between"><span>Total monedas</span><span>{formatMoney(Number(closeCoinsInput || 0))}</span></div>
                      <div className="flex justify-between"><span>Total POS tarjetas</span><span>{formatMoney(Number(closePosCardsInput || 0))}</span></div>
                      <div className="flex justify-between"><span>Total PedidosYa</span><span>{formatMoney(Number(closePedidosYaInput || 0))}</span></div>
                      <div className="flex justify-between font-bold"><span>Total contado</span><span>{formatMoney(Number(closeBillsInput || 0) + Number(closeCoinsInput || 0))}</span></div>
                    </div>
                    <Label>Notas</Label>
                    <Textarea rows={2} value={cashNotes} onChange={(e) => setCashNotes(e.target.value)} placeholder="Opcional" />
                    {pendingOrdersCount > 0 ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-300">
                        You cannot close the register because there are {pendingOrdersCount} open orders. Resolve them in Open Orders first.
                      </div>
                    ) : null}
                    <div className="flex items-center gap-2">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("pedidosYa")}>Atrás</Button>
                      <Button variant="destructive" className="h-14 flex-1 text-base font-semibold" onClick={handleCloseCashSession} disabled={isSavingCashAction || pendingOrdersCount > 0}>Confirmar cierre</Button>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            {canViewSensitiveCash ? (
              <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2 text-sm">
                {cashTransactions.length === 0 ? (
                  <div className="text-muted-foreground">Sin gastos registrados.</div>
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
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isOpenSessionModalOpen}
        onOpenChange={(open) => {
          if (!open && !cashSnapshot.open) return;
          setIsOpenSessionModalOpen(open);
        }}
      >
        <DialogContent
          className="max-w-md"
          showCloseButton={cashSnapshot.open}
          onEscapeKeyDown={(event) => {
            if (!cashSnapshot.open) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (!cashSnapshot.open) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (!cashSnapshot.open) event.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>{cashSnapshot.open ? "Aperturar caja" : "Caja cerrada / Apertura requerida"}</DialogTitle>
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
              {cashSnapshot.open ? (
                <Button variant="outline" className="flex-1" onClick={() => setIsOpenSessionModalOpen(false)}>Cancelar</Button>
              ) : null}
              <Button className="flex-1" onClick={handleOpenCashSession} disabled={isSavingCashAction}>
                {isSavingCashAction ? "Aperturando..." : "Aperturar"}
              </Button>
            </div>
            {!cashSnapshot.open ? (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => {
                  setIsOpenSessionModalOpen(false);
                  navigate("/");
                }}
              >
                Volver
              </Button>
            ) : null}
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
                    <div className="mt-2 text-3xl font-bold text-secondary">{formatMoney(paymentTotal)}</div>
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
                        {(activeOrder?.items?.length ? activeOrder.items : checkoutDraft.items.map((item) => ({
                          id: Number(String(item.id).replace(/\D/g, "")) || Date.now(),
                          productName: item.name,
                          quantity: item.quantity,
                          unitPriceBeforeDiscount: getItemUnitTotal(item),
                          unitPriceFinal: getItemUnitTotal(item),
                          discountAmount: 0,
                          lineTotalFinal: getItemUnitTotal(item) * item.quantity,
                          lineTotalDiscount: 0,
                        }))).map((item) => (
                          <div key={item.id} className="grid grid-cols-[1fr_auto_auto] items-start gap-3 p-2">
                            <div className="min-w-0">
                              <div className="truncate font-medium">{item.productName}</div>
                              <div className="text-xs text-muted-foreground">
                                {(item.unitPriceBeforeDiscount ?? item.unitPriceFinal ?? 0) > (item.unitPriceFinal ?? 0) && (
                                  <span className="mr-1 line-through">{formatMoney(item.unitPriceBeforeDiscount ?? 0)}</span>
                                )}
                                {formatMoney(item.unitPriceFinal ?? item.unitPriceBeforeDiscount ?? 0)} c/u
                              </div>
                              {(item.discountAmount ?? 0) > 0 && (
                                <div className="text-[11px] text-emerald-600">
                                  Descuento {formatMoney(item.discountAmount ?? 0)}
                                </div>
                              )}
                            </div>
                            <div className="text-center text-xs text-muted-foreground">x{item.quantity}</div>
                            <div className="text-right font-semibold">{formatMoney(item.lineTotalFinal ?? ((item.unitPriceFinal ?? 0) * item.quantity))}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-md border p-3 text-sm">
                    <div className="mb-2 font-semibold">Resumen</div>
                    <div className="space-y-1 text-muted-foreground">
                      <div className="flex justify-between"><span>Subtotal (antes descuentos)</span><span>{formatMoney(checkoutSummarySubtotalBefore)}</span></div>
                      {checkoutDiscountLines.length > 0
                        ? checkoutDiscountLines.map((line) => (
                            <div key={`checkout-${line.source}-${line.id}`} className="flex justify-between text-emerald-600">
                              <span>Descuento ({line.name})</span>
                              <span>-{formatMoney(line.amount)}</span>
                            </div>
                          ))
                        : checkoutSummaryDiscount > 0
                          ? <div className="flex justify-between text-emerald-600"><span>Descuento</span><span>-{formatMoney(checkoutSummaryDiscount)}</span></div>
                          : null}
                      {checkoutDisposableTotal > 0 && <div className="flex justify-between"><span>Desechables</span><span>{formatMoney(checkoutDisposableTotal)}</span></div>}
                      <div className="flex justify-between font-semibold text-foreground"><span>Total</span><span>{formatMoney(checkoutSummaryTotal)}</span></div>
                    </div>
                  </div>

                  {splitEnabled && activeSplitPart ? (
                    <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium">
                      Cobrando Parte {parts.findIndex((part) => part.id === activeSplitPart.id) + 1}: {formatMoney(activeSplitPart.amountCents / 100)}
                    </div>
                  ) : null}
                </div>

                <div className="sticky bottom-0 z-30 shrink-0 space-y-3 border-t bg-background px-4 py-4 sm:px-6">
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Button className="h-14 min-w-0 text-base" type="button" variant="outline" onClick={() => setIsCustomerDteOpen(true)}>
                      <span className="min-w-0 truncate text-left">
                        Cliente: {selectedCustomer ? `${selectedCustomer.fullName} (${dteDocumentType})` : `Consumidor final (${dteDocumentType})`}
                      </span>
                    </Button>
                    <Button className="h-14 min-w-0 text-base" type="button" variant="outline" onClick={() => setIsSplitConfigOpen(true)}>
                      Dividir cuenta: {splitEnabled ? "Activado" : "Desactivado"}
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" className="h-14 flex-1 text-base" onClick={() => setIsPaymentOpen(false)}>Cerrar</Button>
                    <Button className="h-14 flex-1 text-base" onClick={() => { setIsPaymentOpen(false); setIsPaymentMethodOpen(true); }} disabled={splitEnabled && !splitValidation.isValid}>
                      Continuar al pago
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">No hay pedido activo.</div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPaymentMethodOpen} onOpenChange={setIsPaymentMethodOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Pago</DialogTitle>
            <DialogDescription>{splitEnabled && activeSplitPart ? `Cobrando Parte ${parts.findIndex((part) => part.id === activeSplitPart.id) + 1}/${parts.length}` : "Pago completo"}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-xl border bg-muted/30 p-4 text-center">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Total a pagar</div>
              <div className="text-4xl font-extrabold text-secondary">{formatMoney(expectedPaymentCents / 100)}</div>
            </div>
            <Label>Método</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {paymentMethodButtons.map((option) => (
                <Button
                  key={option.code}
                  type="button"
                  variant={(option.code === "card" ? paymentMethod === "card" : selectedPaymentMethodCode === option.code) ? "default" : "outline"}
                  className="h-14 text-base"
                  onClick={() => {
                    setPaymentMethod(option.method);
                    if (option.code === "card") {
                      setSelectedPaymentMethodCode(option.code);
                      setCardType("credit");
                    } else {
                      setSelectedPaymentMethodCode(option.code);
                      setCardType(null);
                    }
                  }}
                >
                  {option.label}
                </Button>
              ))}
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
            {activeTenderField ? (
              <div ref={keypadRef} className="grid grid-cols-4 gap-2">
                {DENOMINATION_CENTS.map((value) => (
                  <Button key={value} type="button" className="h-14 text-base" variant="outline" onClick={() => applyTenderDenomination(value)}>
                    {formatMoney(value / 100)}
                  </Button>
                ))}
                <Button type="button" className="h-14 text-base" variant="outline" onClick={clearTenderField}>Borrar</Button>
                <Button type="button" className="h-14 text-base" variant="outline" onClick={backspaceTenderField}>←</Button>
                <Button type="button" className="col-span-2 h-14 text-base" variant="outline" onClick={setExactTenderAmount}>Exacto</Button>
              </div>
            ) : null}
            <div className="flex gap-2">
              <Button variant="outline" className="h-14 flex-1 text-base" onClick={() => { setIsPaymentMethodOpen(false); setIsPaymentOpen(true); }}>Volver</Button>
              <Button className="h-14 flex-1 text-base" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || paymentAmountValue <= 0 || (splitEnabled && !splitValidation.isValid)}>
                {isProcessingPayment ? "Procesando..." : "Registrar pago"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isCustomerDteOpen} onOpenChange={setIsCustomerDteOpen}>
        <DialogContent className="w-[95vw] max-w-xl">
          <DialogHeader>
            <DialogTitle>Cliente / DTE</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Tipo DTE</Label>
              <div className="grid grid-cols-3 gap-2">
                <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CF" ? "default" : "outline"} onClick={() => setDteDocumentType("CF")}>CF</Button>
                <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CCF" ? "default" : "outline"} onClick={() => setDteDocumentType("CCF")}>CCF</Button>
                <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "SX" ? "default" : "outline"} onClick={() => setDteDocumentType("SX")}>SX</Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Cliente</Label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-stretch">
                <Button
                  type="button"
                  variant="outline"
                  className="h-12 w-full min-w-0 justify-start overflow-hidden text-sm sm:h-14 sm:text-base"
                  onClick={() => {
                    setIsCustomerPickerOpen(true);
                    setCustomerSearch("");
                  }}
                >
                  <span className="block w-full min-w-0 truncate text-left">
                    {selectedCustomer ? `${selectedCustomer.fullName} (${selectedCustomer.clientType})` : "Selecciona cliente"}
                  </span>
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-12 w-full min-w-[120px] shrink-0 text-sm sm:h-14 sm:w-auto sm:px-5 sm:text-base"
                  onClick={() => {
                    setCustomerFormErrors({});
                    setCustomerServerErrors({});
                    setActivitySearch("");
                    setIsCustomerCreateOpen(true);
                    void preloadCustomerFormFromDTE(dteDocumentType);
                  }}
                >
                  Administrar
                </Button>
              </div>
            </div>
            {dteDocumentType === "CCF" ? (
              <div className="flex items-center justify-between rounded-md border p-2 text-sm"><span>Exento IVA</span><Checkbox checked={ivaExempt} onCheckedChange={(v) => setIvaExempt(v === true)} /></div>
            ) : null}
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="h-12 flex-1 text-sm sm:h-14 sm:text-base" variant="outline" onClick={() => setIsCustomerDteOpen(false)}>Cancelar</Button>
              <Button className="h-12 flex-1 text-sm sm:h-14 sm:text-base" onClick={() => void handleAcceptCustomerDte()}>Aceptar</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isSplitConfigOpen} onOpenChange={setIsSplitConfigOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Dividir cuenta</DialogTitle>
          </DialogHeader>
          <SplitPanel
            enabled={splitEnabled}
            onEnabledChange={setSplitEnabled}
            totalCents={checkoutTotalCents}
            parts={parts}
            onPartsChange={setParts}
            activePartId={activePartId}
            onActivePartIdChange={setActivePartId}
          />
          <div className="flex gap-2">
            <Button className="h-14 flex-1 text-base" variant="outline" onClick={() => setIsSplitConfigOpen(false)}>Cerrar</Button>
            <Button className="h-14 flex-1 text-base" onClick={() => setIsSplitConfigOpen(false)}>Aceptar</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isCustomerPickerOpen} onOpenChange={setIsCustomerPickerOpen}>
        <DialogContent className="w-[92vw] max-w-lg rounded-2xl p-5">
          <DialogHeader>
            <DialogTitle>Seleccionar cliente</DialogTitle>
            <DialogDescription>Busca por nombre, email, teléfono o documento.</DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            placeholder="Buscar cliente…"
            value={customerSearch}
            onChange={(event) => setCustomerSearch(event.target.value)}
            className="h-12"
          />
          <div className="max-h-72 space-y-2 overflow-y-auto">
            {visibleCustomers.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Sin resultados</p>
            ) : (
              visibleCustomers.map((customer) => (
                <Button
                  key={customer.id}
                  type="button"
                  variant={String(customer.id) === selectedCustomerId ? "default" : "outline"}
                  className="h-12 w-full justify-start text-left"
                  onClick={() => {
                    setSelectedCustomerId(String(customer.id));
                    setIsCustomerPickerOpen(false);
                  }}
                >
                  <span className="truncate">{customer.fullName}</span>
                  <span className="ml-2 text-xs opacity-80">({customer.clientType})</span>
                </Button>
              ))
            )}
          </div>
          {filteredCustomers.length > visibleCustomers.length && (
            <p className="text-xs text-muted-foreground">
              Refina tu búsqueda (mostrando 4 de {filteredCustomers.length})
            </p>
          )}
          {!normalizedCustomerSearch && customersByDte.length > visibleCustomers.length && (
            <p className="text-xs text-muted-foreground">Mostrando 4 de {customersByDte.length}</p>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={isCustomerCreateOpen} onOpenChange={(open) => !isSavingCustomer && setIsCustomerCreateOpen(open)}>
        <DialogContent className="w-[94vw] max-w-xl rounded-2xl p-5">
          <DialogHeader>
            <DialogTitle>Nuevo cliente</DialogTitle>
            <DialogDescription>Completa los datos del cliente sin salir de la venta.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <Label>Tipo DTE</Label>
              <div className="flex gap-2">
                <Button type="button" variant={customerForm.clientType === "CF" ? "default" : "outline"} className="h-11 flex-1" onClick={() => void preloadCustomerFormFromDTE("CF")}>CF</Button>
                <Button type="button" variant={customerForm.clientType === "CCF" ? "default" : "outline"} className="h-11 flex-1" onClick={() => void preloadCustomerFormFromDTE("CCF")}>CCF</Button>
                <Button type="button" variant={customerForm.clientType === "SX" ? "default" : "outline"} className="h-11 flex-1" onClick={() => void preloadCustomerFormFromDTE("SX")}>SX</Button>
              </div>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label>Nombre completo</Label>
              <Input
                autoFocus
                value={customerForm.fullName}
                onChange={(event) => setCustomerForm((prev) => ({ ...prev, fullName: event.target.value }))}
                className="h-12"
              />
              {customerFormErrors.fullName && <p className="text-xs text-destructive">{customerFormErrors.fullName}</p>}
              {customerServerErrors.full_name && <p className="text-xs text-destructive">{customerServerErrors.full_name}</p>}
            </div>
            <div className="space-y-1">
              <Label>Teléfono</Label>
              <Input value={customerForm.phone} onChange={(event) => setCustomerForm((prev) => ({ ...prev, phone: event.target.value }))} className="h-12" />
              {customerFormErrors.phone && <p className="text-xs text-destructive">{customerFormErrors.phone}</p>}
              {customerServerErrors.phone && <p className="text-xs text-destructive">{customerServerErrors.phone}</p>}
            </div>
            <div className="space-y-1">
              <Label>Email</Label>
              <Input value={customerForm.email} onChange={(event) => setCustomerForm((prev) => ({ ...prev, email: event.target.value }))} className="h-12" />
              {customerFormErrors.email && <p className="text-xs text-destructive">{customerFormErrors.email}</p>}
              {customerServerErrors.email && <p className="text-xs text-destructive">{customerServerErrors.email}</p>}
            </div>
            <div className="space-y-1">
              <Label>{customerForm.clientType === "SX" ? "Documento" : "DUI"}</Label>
              <Input value={customerForm.dui} onChange={(event) => setCustomerForm((prev) => ({ ...prev, dui: event.target.value }))} className="h-12" />
              {customerFormErrors.dui && <p className="text-xs text-destructive">{customerFormErrors.dui}</p>}
              {customerServerErrors.dui && <p className="text-xs text-destructive">{customerServerErrors.dui}</p>}
            </div>
            {customerForm.clientType === "CCF" && (
              <>
                <div className="space-y-1">
                  <Label>NIT</Label>
                  <Input value={customerForm.nit} onChange={(event) => setCustomerForm((prev) => ({ ...prev, nit: event.target.value }))} className="h-12" />
                  {customerFormErrors.nit && <p className="text-xs text-destructive">{customerFormErrors.nit}</p>}
                  {customerServerErrors.nit && <p className="text-xs text-destructive">{customerServerErrors.nit}</p>}
                </div>
                <div className="space-y-1">
                  <Label>NRC</Label>
                  <Input value={customerForm.nrc} onChange={(event) => setCustomerForm((prev) => ({ ...prev, nrc: event.target.value }))} className="h-12" />
                  {customerFormErrors.nrc && <p className="text-xs text-destructive">{customerFormErrors.nrc}</p>}
                  {customerServerErrors.nrc && <p className="text-xs text-destructive">{customerServerErrors.nrc}</p>}
                </div>
                <div className="space-y-1 sm:col-span-2">
                  <Label>Empresa</Label>
                  <Input value={customerForm.companyName} onChange={(event) => setCustomerForm((prev) => ({ ...prev, companyName: event.target.value }))} className="h-12" />
                  {customerFormErrors.companyName && <p className="text-xs text-destructive">{customerFormErrors.companyName}</p>}
                </div>
              </>
            )}
            <div className="space-y-1 sm:col-span-2">
              <Label>Dirección</Label>
              <Input value={customerForm.direccion} onChange={(event) => setCustomerForm((prev) => ({ ...prev, direccion: event.target.value }))} className="h-12" />
              {customerFormErrors.direccion && <p className="text-xs text-destructive">{customerFormErrors.direccion}</p>}
              {customerServerErrors.direccion && <p className="text-xs text-destructive">{customerServerErrors.direccion}</p>}
            </div>
            <div className="space-y-1">
              <Label>Departamento</Label>
              <Select
                value={customerForm.departmentCode || "__empty"}
                onValueChange={(value) =>
                  setCustomerForm((prev) => ({
                    ...prev,
                    departmentCode: value === "__empty" ? "" : value,
                    municipalityCode: "",
                  }))
                }
              >
                <SelectTrigger className="h-12"><SelectValue placeholder="Selecciona departamento" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__empty">Selecciona</SelectItem>
                  {departments.map((department) => (
                    <SelectItem key={department.code} value={department.code}>{department.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {customerFormErrors.departmentCode && <p className="text-xs text-destructive">{customerFormErrors.departmentCode}</p>}
              {customerServerErrors.department_code && <p className="text-xs text-destructive">{customerServerErrors.department_code}</p>}
            </div>
            <div className="space-y-1">
              <Label>Municipio</Label>
              <Select
                value={customerForm.municipalityCode || "__empty"}
                onValueChange={(value) => setCustomerForm((prev) => ({ ...prev, municipalityCode: value === "__empty" ? "" : value }))}
              >
                <SelectTrigger className="h-12"><SelectValue placeholder="Selecciona municipio" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__empty">Selecciona</SelectItem>
                  {municipalities.map((municipality) => (
                    <SelectItem key={municipality.code} value={municipality.code}>{municipality.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {customerFormErrors.municipalityCode && <p className="text-xs text-destructive">{customerFormErrors.municipalityCode}</p>}
              {customerServerErrors.municipality_code && <p className="text-xs text-destructive">{customerServerErrors.municipality_code}</p>}
            </div>
            {customerForm.clientType === "CCF" && (
              <div className="space-y-1 sm:col-span-2">
                <Label>Actividad económica</Label>
                <Input
                  placeholder="Buscar actividad…"
                  value={activitySearch}
                  onChange={(event) => setActivitySearch(event.target.value)}
                  className="h-12"
                />
                <Select
                  value={customerForm.activityCode || "__empty"}
                  onValueChange={(value) => {
                    const selected = activities.find((activity) => activity.code === value);
                    setCustomerForm((prev) => ({
                      ...prev,
                      activityCode: value === "__empty" ? "" : value,
                      activityDescription: value === "__empty" ? "" : selected?.description ?? prev.activityDescription,
                    }));
                  }}
                >
                  <SelectTrigger className="h-12"><SelectValue placeholder="Selecciona actividad" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__empty">Selecciona</SelectItem>
                    {filteredActivities.map((activity) => (
                      <SelectItem key={activity.code} value={activity.code}>{activity.code} - {activity.description}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {customerFormErrors.activityCode && <p className="text-xs text-destructive">{customerFormErrors.activityCode}</p>}
                {customerServerErrors.activity_code && <p className="text-xs text-destructive">{customerServerErrors.activity_code}</p>}
              </div>
            )}
          </div>
          <div className="mt-4 flex gap-2">
            <Button type="button" variant="outline" className="h-12 flex-1" onClick={() => setIsCustomerCreateOpen(false)} disabled={isSavingCustomer}>
              Cancelar
            </Button>
            <Button type="button" className="h-12 flex-1" onClick={() => void handleCreateCustomerFromPOS()} disabled={isSavingCustomer}>
              {isSavingCustomer ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isKitchenPromptOpen} onOpenChange={(open) => !isSubmittingKitchenChoice && setIsKitchenPromptOpen(open)}>
        <DialogContent className="w-[92vw] max-w-md rounded-2xl p-6">
          <DialogHeader>
            <DialogTitle className="text-2xl">Finalizar venta</DialogTitle>
            <DialogDescription className="text-base">
              La venta ya se guardó. Configura cocina e impresión.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <span>Enviar a cocina</span>
              <Checkbox checked={postSaleKitchenChoice} onCheckedChange={(value) => setPostSaleKitchenChoice(value === true)} disabled={isSubmittingKitchenChoice} />
            </div>
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <span>{printerAvailable ? "Imprimir ticket" : "Descargar ticket"}</span>
              <Checkbox checked={postSalePrintChoice} onCheckedChange={(value) => setPostSalePrintChoice(value === true)} disabled={isSubmittingKitchenChoice} />
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Button
              type="button"
              className="h-14 text-lg"
              disabled={isSubmittingKitchenChoice}
              onClick={() => void handleKitchenChoice(postSaleKitchenChoice)}
            >
              {isSubmittingKitchenChoice ? "Guardando..." : "Confirmar"}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-14 text-lg"
              disabled={isSubmittingKitchenChoice}
              onClick={() => {
                setIsKitchenPromptOpen(false);
                finalizePaidSale();
                scheduleReload();
                scheduleHardReload("finalize_omit");
              }}
            >
              Omitir
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={fallbackPdfModal.open}
        onOpenChange={(open) => {
          if (!open && cashCloseFlowState === "pendingUserAck") return;
          setFallbackPdfModal((prev) => ({
            ...prev,
            open,
          }));
          if (!open && fallbackPdfModal.shouldHardReloadAfterClose) {
            scheduleHardReload("fallback_modal_closed");
          }
        }}
      >
        <DialogContent className="w-[92vw] max-w-md rounded-2xl p-6">
          <DialogHeader>
            <DialogTitle className="text-2xl">{fallbackPdfModal.title}</DialogTitle>
            <DialogDescription className="text-base">{fallbackPdfModal.message}</DialogDescription>
          </DialogHeader>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Button
              type="button"
              className="h-12"
              onClick={() => {
                if (!fallbackPdfModal.onDownload) return;
                void fallbackPdfModal.onDownload()
                  .then(() => {
                    if (fallbackPdfModal.shouldHardReloadAfterClose) {
                      scheduleHardReload("fallback_pdf_download");
                      return;
                    }
                  })
                  .catch((error) => toast.error(error instanceof Error ? error.message : "No se pudo descargar PDF"));
              }}
            >
              Descargar PDF
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-12"
              onClick={() => {
                if (fallbackPdfModal.shouldHardReloadAfterClose) {
                  scheduleHardReload("fallback_pdf_close");
                  return;
                }
                if (import.meta.env.DEV) {
                  // eslint-disable-next-line no-console
                  console.info("[cash-close-flow] user_ack_close");
                }
                setFallbackPdfModal((prev) => ({ ...prev, open: false }));
                setCashCloseFlowState("idle");
                setIsCashDialogOpen(false);
                setIsOpenSessionModalOpen(false);
                navigate("/");
              }}
            >
              Cerrar
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <PrivilegePinModal
        open={Boolean(privilegedGuard.pendingAction)}
        onCancel={() => privilegedGuard.setPendingAction(null)}
        onSuccess={(pin) =>
          privilegedGuard.onPinSuccess({
            manualProduct: () => setIsManualProductOpen(true),
            discounts: () => setIsDiscountDialogOpen(true),
            cashTransactions: () => {
              setIsCashDialogOpen(true);
              loadCashData().catch(() => undefined);
            },
            removePendingItem: (approvedPin) => {
              if (!approvedPin) return;
              setPendingEditAuthorizationPin(approvedPin);
            },
          }, pin)
        }
      />

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
            <DialogDescription>Ingresa el PIN de 6 dígitos para autorizar cambio de precio.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-center text-2xl tracking-[0.4em]">{Array.from({ length: 6 }).map((_, i) => (pinInput[i] ? "●" : "○")).join(" ")}</div>
            <div className="grid grid-cols-3 gap-2">
              {[1,2,3,4,5,6,7,8,9].map((n) => (
                <Button key={n} variant="outline" className="h-12" onClick={async () => {
                  const next = `${pinInput}${n}`.slice(0, 6);
                  setPinInput(next);
                  if (next.length === 6) {
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
                const next = `${pinInput}0`.slice(0, 6);
                setPinInput(next);
                if (next.length === 6) {
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
