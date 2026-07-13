import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, ShoppingCart, Wallet, ChevronDown, ChevronUp, Delete, BadgePercent, LayoutGrid, RefreshCw, Settings2, Printer, Save, XCircle, ReceiptText, Send, PrinterCheck, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney, moneyToFixedString, toCents, toNumber } from "@/lib/money";
import { getReadableTextColor, isValidHexColor } from "@/lib/color";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  ApiRequestError,
  checkCartInventoryAvailability,
  checkOrderInventoryAvailability,
  createOrder,
  Customer,
  createPayment,
  setOrderSendToKitchen,
  getPaymentMethods,
  getOrderById,
  updateOrderCustomerDte,
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
  getRecentSalesActions,
  getLastSaleAction,
  dteDeliverByOrder,
  type RecentSaleAction,
  type PosQuickSalesButtonMode,
  type PosQuickSalesHistoryScope,
  type PosQuickSalesHistoryWindowMinutes,
  createCashPayout,
  openCashDrawer,
  downloadCashSessionTicketPdf,
  validateOrderPricePin,
  getActiveDiscounts,
  getPendingOrders,
  setOrderPending,
  getPrintingStatus,
  getFeatureFlags,
  getFeatureSettings,
  getDteSettings,
  getDiningAreas,
  getRestaurantTables,
  getTableSessions,
  createTableSession,
  Category,
  Discount,
  ModifierGroup,
  Product,
  PaymentMethod,
  PaymentMethodOption,
  CartAvailabilityItem,
  InventoryAvailabilityCheck,
  InventoryStockPolicy,
  ServiceType,
  CashSessionSnapshot,
  CashTransaction,
  Order,
} from "@/lib/api";
import { getCashSessionStatus } from "@/lib/cashSessionStatus";
import { toast } from "sonner";
import { smartPrintTicket } from "@/lib/ticketPrinting";
import { useServiceTypes } from "@/hooks/useServiceTypes";
import { usePrivilegedActionGuard } from "@/hooks/usePrivilegedActionGuard";
import { PrivilegePinModal } from "@/components/pos/PrivilegePinModal";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { ClockSV } from "@/components/ClockSV";
import { formatWhatsAppClientPhone, normalizeWhatsAppClientPhone, validateWhatsAppClientPhone, type WhatsAppCountry } from "@/lib/whatsappClientPhone";
import { WhatsAppPhoneInput } from "@/components/dte/WhatsAppPhoneInput";

const POS_DEBUG = import.meta.env.DEV && import.meta.env.VITE_DEBUG === "true";
const posDebug = (...args: unknown[]) => {
  if (POS_DEBUG) console.info(...args);
};

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

interface SaleCompletionSummary {
  totalToPay: number;
  amountReceived: number;
  changeAmount: number;
  paymentMethod: PaymentMethod;
  paymentMethodCode: string;
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

const shouldOpenCashDrawer = (method: PaymentMethod, methodCode?: string): boolean => {
  if (method === "cash") return true;
  const normalizedCode = String(methodCode || "").trim().toLowerCase();
  return normalizedCode === "cash" || normalizedCode === "efectivo";
};

const isCashPaymentMethod = (method?: (PaymentMethodOption & { isCash?: boolean }) | { code?: string | null; name?: string | null; isCash?: boolean; fiscalPaymentType?: string } | null): boolean => {
  if (!method) return false;
  if (method.fiscalPaymentType === "CASH") return true;
  if (method.isCash === true) return true;
  const normalizedCode = String(method.code || "").trim().toLowerCase();
  if (["cash", "efectivo"].includes(normalizedCode)) return true;
  return String(method.name || "").trim().toLowerCase() === "efectivo";
};

const getPaymentMethodKind = (method: PaymentMethodOption): PaymentMethod => {
  if (method.fiscalPaymentType === "CASH" || isCashPaymentMethod(method)) return "cash";
  if (method.fiscalPaymentType === "CARD") return "card";
  if (method.fiscalPaymentType === "TRANSFER") return "transfer";
  const normalized = String(method.code || "").trim().toLowerCase();
  if (normalized.includes("card") || normalized.includes("tarjeta")) return "card";
  return "transfer";
};

type PaymentButtonOption = {
  code: string;
  label: string;
  method: PaymentMethod;
  option: PaymentMethodOption;
};

const getPaymentButtonStyle = (option: PaymentButtonOption | null | undefined, selected = false): CSSProperties | undefined => {
  const color = option?.option.colorHex;
  if (!color || !isValidHexColor(color)) return undefined;
  if (selected) {
    return { backgroundColor: color, borderColor: color, color: getReadableTextColor(color) };
  }
  return { borderColor: color, color };
};

const shouldShowChange = (summary: SaleCompletionSummary | null): boolean => {
  if (!summary) return false;
  if (!shouldOpenCashDrawer(summary.paymentMethod, summary.paymentMethodCode)) return false;
  return summary.changeAmount > 0.009;
};

const buildSaleCompletionSummary = (params: {
  totalToPay: number;
  amountReceived: number;
  paymentMethod: PaymentMethod;
  paymentMethodCode: string;
}): SaleCompletionSummary => {
  const { totalToPay, amountReceived, paymentMethod, paymentMethodCode } = params;
  const rawChange = amountReceived - totalToPay;
  return {
    totalToPay,
    amountReceived,
    changeAmount: rawChange > 0 ? rawChange : 0,
    paymentMethod,
    paymentMethodCode,
  };
};

type CashPaymentPanelProps = {
  totalCents: number;
  paymentAmount: string;
  tipAmount: string;
  activeTenderField: "payment" | "tip" | null;
  changeCents: number;
  isExactPayment: boolean;
  onPaymentAmountChange: (value: string) => void;
  onTipAmountChange: (value: string) => void;
  onFocusTenderField: (field: "payment" | "tip") => void;
  onApplyDenomination: (amountCents: number) => void;
  onClear: () => void;
  onBackspace: () => void;
  onExact: () => void;
  panelRef?: RefObject<HTMLDivElement>;
  paymentInputRef?: RefObject<HTMLInputElement>;
};

const CashPaymentPanel = ({
  totalCents,
  paymentAmount,
  tipAmount,
  activeTenderField,
  changeCents,
  isExactPayment,
  onPaymentAmountChange,
  onTipAmountChange,
  onFocusTenderField,
  onApplyDenomination,
  onClear,
  onBackspace,
  onExact,
  panelRef,
  paymentInputRef,
}: CashPaymentPanelProps) => (
  <div ref={panelRef} className="space-y-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
    <div className="flex items-center justify-between gap-3">
      <div>
        <h3 className="font-semibold">Pago en efectivo</h3>
        <p className="text-xs text-muted-foreground">Monto recibido, propina y cambio.</p>
      </div>
      <Badge variant="outline">Total {formatMoney(totalCents / 100)}</Badge>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>Monto recibido</Label>
        <Input ref={paymentInputRef} value={paymentAmount} onFocus={() => onFocusTenderField("payment")} onClick={() => onFocusTenderField("payment")} onChange={(e) => onPaymentAmountChange(e.target.value)} inputMode="decimal" />
      </div>
      <div className="space-y-2">
        <Label>Propina</Label>
        <Input value={tipAmount} onFocus={() => onFocusTenderField("tip")} onClick={() => onFocusTenderField("tip")} onChange={(e) => onTipAmountChange(e.target.value)} inputMode="decimal" />
      </div>
    </div>
    <div className={cn("rounded-lg border bg-background/80 p-3 text-center font-semibold", isExactPayment ? "text-lg" : "text-2xl sm:text-3xl")}> 
      {changeCents < -1 && <span className="text-destructive">Faltan {formatMoney(Math.abs(changeCents) / 100)}</span>}
      {isExactPayment && <span className="text-secondary">Pago exacto</span>}
      {changeCents > 1 && <span className="text-amber-500">Cambio: {formatMoney(changeCents / 100)}</span>}
    </div>
    <div className="grid grid-cols-4 gap-2">
      {DENOMINATION_CENTS.map((value) => (
        <Button key={value} type="button" className="h-11 text-sm" variant="outline" onClick={() => onApplyDenomination(value)}>
          {formatMoney(value / 100)}
        </Button>
      ))}
      <Button type="button" className="h-11 text-sm" variant="outline" onClick={onClear}>Borrar</Button>
      <Button type="button" className="h-11 text-sm" variant="outline" onClick={onBackspace}>←</Button>
      <Button type="button" className="col-span-2 h-12 text-sm" variant="outline" onClick={onExact}>Exacto</Button>
    </div>
  </div>
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
  const [allowCloseWithPendingOrders, setAllowCloseWithPendingOrders] = useState(false);
  const [isPendingChoiceOpen, setIsPendingChoiceOpen] = useState(false);
  const [cashSnapshot, setCashSnapshot] = useState<CashSessionSnapshot>({ open: false });
  const [isCashGateLoading, setIsCashGateLoading] = useState(true);
  const [cashTransactions, setCashTransactions] = useState<CashTransaction[]>([]);
  const [isRecentSalesOpen, setIsRecentSalesOpen] = useState(false);
  const [recentSales, setRecentSales] = useState<RecentSaleAction[]>([]);
  const [recentSalesLoading, setRecentSalesLoading] = useState(false);
  const [recentSalesError, setRecentSalesError] = useState("");
  const [recentSalesPrintingId, setRecentSalesPrintingId] = useState<number | null>(null);
  const [recentSalesSendingId, setRecentSalesSendingId] = useState<number | null>(null);
  const [dteEnabled, setDteEnabled] = useState(false);
  const [isQuickSaleProcessing, setIsQuickSaleProcessing] = useState(false);
  const [quickSalesMode, setQuickSalesMode] = useState<PosQuickSalesButtonMode>("last_sale");
  const [quickSalesHistoryScope, setQuickSalesHistoryScope] = useState<PosQuickSalesHistoryScope>("current_shift");
  const [quickSalesHistoryWindowMinutes, setQuickSalesHistoryWindowMinutes] = useState<PosQuickSalesHistoryWindowMinutes>(60);
  const [lastClosedSessionId, setLastClosedSessionId] = useState<number | null>(() => {
    const raw = localStorage.getItem("last_closed_cash_session_id");
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  });
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
  const closeCashSubmittingRef = useRef(false);
  const [isOpeningDrawer, setIsOpeningDrawer] = useState(false);
  const lastDrawerOpenAtRef = useRef<number>(0);
  const openSessionInputRef = useRef<HTMLInputElement | null>(null);
  const postOpenSessionActionRef = useRef<(() => Promise<void>) | null>(null);
  const openSessionResolverRef = useRef<((opened: boolean) => void) | null>(null);
  const [pendingProduct, setPendingProduct] = useState<Product | null>(null);
  const [editingModifiersItemId, setEditingModifiersItemId] = useState<string | null>(null);
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
  const [isOrderTypeSelectorOpen, setIsOrderTypeSelectorOpen] = useState(false);
  const [showCashPanel, setShowCashPanel] = useState(false);
  const [isCustomerDteOpen, setIsCustomerDteOpen] = useState(false);
  const [isSplitConfigOpen, setIsSplitConfigOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [cardType, setCardType] = useState<"debit" | "credit" | null>(null);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>([]);
  const [selectedPaymentMethodCode, setSelectedPaymentMethodCode] = useState<string>("");
  const [paymentMethodAutoSelectedFromOrderType, setPaymentMethodAutoSelectedFromOrderType] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [defaultConsumerCustomer, setDefaultConsumerCustomer] = useState<Customer | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [whatsappClientCountry, setWhatsappClientCountry] = useState<WhatsAppCountry>("ESA");
  const [whatsappClientInput, setWhatsappClientInput] = useState("");
  const [whatsappClientError, setWhatsappClientError] = useState("");
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
    isIvaExempt: false,
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
  const checkoutModalScrollRef = useRef<HTMLDivElement | null>(null);
  const cashPanelRef = useRef<HTMLDivElement | null>(null);
  const cashAmountInputRef = useRef<HTMLInputElement | null>(null);
  const keypadRef = useRef<HTMLDivElement | null>(null);
  const cartItemsScrollRef = useRef<HTMLDivElement | null>(null);
  const cartEndRef = useRef<HTMLDivElement | null>(null);
  const previousCartLengthRef = useRef(0);
  const previousServiceTypeRef = useRef<string>("");
  const [paymentReference, setPaymentReference] = useState("");
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [stockWarning, setStockWarning] = useState<{ check: InventoryAvailabilityCheck; mode: "warn" | "block"; resolve?: (confirmed: boolean) => void } | null>(null);
  const [inventoryStockPolicy, setInventoryStockPolicy] = useState<InventoryStockPolicy>("allow");
  const [posProductImagesEnabled, setPosProductImagesEnabled] = useState(false);
  const [tableMapEnabled, setTableMapEnabled] = useState(false);
  const [posMode, setPosMode] = useState<"tables"|"pos">("pos");
  const [diningAreas, setDiningAreas] = useState<any[]>([]);
  const [restaurantTables, setRestaurantTables] = useState<any[]>([]);
  const [tableSessions, setTableSessions] = useState<any[]>([]);
  const [selectedOpsArea, setSelectedOpsArea] = useState<number | "all">("all");
  const [selectedOpsFilter, setSelectedOpsFilter] = useState<"all"|"free"|"occupied"|"kitchen">("all");
  const [selectedOpsTableId, setSelectedOpsTableId] = useState<number | null>(null);
  const [newSessionDialog, setNewSessionDialog] = useState<{ open: boolean; tableId: number | null; guests: number; orderMode: "table"|"per_person"; notes: string }>({ open: false, tableId: null, guests: 2, orderMode: "table", notes: "" });
  const [opsContextMenu, setOpsContextMenu] = useState<{ open: boolean; x: number; y: number; tableId: number | null }>({ open: false, x: 0, y: 0, tableId: null });
  const [mergeMode, setMergeMode] = useState<{ active: boolean; sessionId: number | null; sourceTableId: number | null }>({ active: false, sessionId: null, sourceTableId: null });
  const longPressOpsRef = useRef<number | null>(null);
  const [hiddenProductImages, setHiddenProductImages] = useState<Record<number, boolean>>({});
  const [cartAvailability, setCartAvailability] = useState<Record<number, CartAvailabilityItem>>({});
  const [isSendingToPending, setIsSendingToPending] = useState(false);
  const [isPendingReferenceDialogOpen, setIsPendingReferenceDialogOpen] = useState(false);
  const [pendingReferenceDraft, setPendingReferenceDraft] = useState("");
  const [pendingEditAuthorizationPin, setPendingEditAuthorizationPin] = useState("");
  const [isKitchenPromptOpen, setIsKitchenPromptOpen] = useState(false);
  const [kitchenPromptOrderId, setKitchenPromptOrderId] = useState<number | null>(null);
  const [isSubmittingKitchenChoice, setIsSubmittingKitchenChoice] = useState(false);
  const [postSaleKitchenChoice, setPostSaleKitchenChoice] = useState(true);
  const [postSalePrintChoice, setPostSalePrintChoice] = useState(true);
  const [saleCompletionSummary, setSaleCompletionSummary] = useState<SaleCompletionSummary | null>(null);
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
  const [lastPaymentAutoPrint, setLastPaymentAutoPrint] = useState(false);
  const [splitEnabled, setSplitEnabled] = useState(false);
  const [parts, setParts] = useState<SplitPart[]>([]);
  const [activePartId, setActivePartId] = useState<string | null>(null);
  const [createdOrderId, setCreatedOrderId] = useState<number | null>(null);
  const [createdOrderNumber, setCreatedOrderNumber] = useState<number | null>(null);
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
  const canManageCashOperations = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canManageCashPayouts = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canCloseCash = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canViewSensitiveCash = Boolean(user?.isSuperuser || user?.role === "admin");
  const canUseLastSaleQuickAction = quickSalesMode === "last_sale" && Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canViewRecentSalesActions = quickSalesMode === "history" && Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
  const shouldShowQuickSalesButton = quickSalesMode !== "hidden" && (canUseLastSaleQuickAction || canViewRecentSalesActions);
  const requiresCashOpen = !getCashSessionStatus(cashSnapshot).hasOpenCashSession;
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

  const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

  const shouldShowProductImage = useCallback((product: Product) => {
    if (!product.imageUrl || hiddenProductImages[product.id]) return false;
    if (product.posImagePolicy === "show") return true;
    if (product.posImagePolicy === "hide") return false;
    const categoryPolicy = categoryById.get(product.categoryId)?.posProductImagesPolicy ?? "inherit";
    if (categoryPolicy === "show") return true;
    if (categoryPolicy === "hide") return false;
    return posProductImagesEnabled;
  }, [categoryById, hiddenProductImages, posProductImagesEnabled]);

  const loadMenuData = async () => {
    const [categoriesResponse, modifierGroupsResponse] = await Promise.all([
      getCategories(),
      getModifierGroups(),
    ]);
    setCategories(categoriesResponse);
    setModifierGroups(modifierGroupsResponse);
  };

  useEffect(() => {
    getDteSettings()
      .then((settings) => setDteEnabled(settings.haciendaEnabled))
      .catch(() => setDteEnabled(false));
  }, []);

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
    if (!tableMapEnabled) return;
    Promise.all([getDiningAreas().catch(() => []), getRestaurantTables().catch(() => []), getTableSessions().catch(() => [])])
      .then(([areas, tables, sessions]) => {
        setDiningAreas(areas);
        setRestaurantTables(tables);
        setTableSessions(sessions);
      })
      .catch(() => undefined);
  }, [tableMapEnabled]);

  const sessionByTableId = useMemo(() => {
    const map = new Map<number, any>();
    tableSessions.forEach((session) => {
      (session.tableIds || []).forEach((tableId: number) => map.set(tableId, session));
    });
    return map;
  }, [tableSessions]);

  const openTableSession = async (tableId: number) => {
    const existing = sessionByTableId.get(tableId);
    if (existing?.primaryOrder) {
      navigate(`/pos?pending_order_id=${existing.primaryOrder}&mode=edit`, { state: { fromOpenOrders: true } });
      return;
    }
    try {
      const created = await createTableSession({ tableIds: [tableId], guestsCount: 2, orderMode: "table" });
      if (created.primaryOrder) navigate(`/pos?pending_order_id=${created.primaryOrder}&mode=edit`, { state: { fromOpenOrders: true } });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo abrir mesa.");
    }
  };

  const getSessionStateLabel = (session: any | undefined) => {
    if (!session) return "Libre";
    if (session.status === "sent_to_kitchen") return "En cocina";
    if (session.status === "partially_paid") return "Parcial";
    return "Ocupada";
  };


  const handleMergeWithTable = async (targetTableId: number) => {
    if (!mergeMode.active || !mergeMode.sessionId) return;
    const targetSession = sessionByTableId.get(targetTableId);
    if (targetSession) { toast.error("Solo puedes unir mesas libres en esta versión."); return; }
    try {
      const { mergeTableSessionTables } = await import("@/lib/api");
      await mergeTableSessionTables(mergeMode.sessionId, [targetTableId]);
      toast.success("Mesas unidas correctamente.");
      setMergeMode({ active: false, sessionId: null, sourceTableId: null });
      const sessions = await getTableSessions();
      setTableSessions(sessions);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo unir la mesa.");
    }
  };

  const beginSessionFromDialog = async () => {
    if (!newSessionDialog.tableId) return;
    try {
      const created = await createTableSession({ tableIds: [newSessionDialog.tableId], guestsCount: Math.max(1, newSessionDialog.guests), orderMode: newSessionDialog.orderMode, notes: newSessionDialog.notes || undefined });
      setNewSessionDialog({ open: false, tableId: null, guests: 2, orderMode: "table", notes: "" });
      if (created.primaryOrder) {
        navigate(`/pos?pending_order_id=${created.primaryOrder}&mode=edit`, { state: { fromOpenOrders: true } });
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo iniciar orden de mesa.");
    }
  };
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
    posDebug("open_order.pos_loader.source", { order_id: pendingOrderId, mode, total_db: null, items: 0 });
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
        posDebug("open_order.pos_loader.source", {
          order_id: order.id,
          mode,
          total_db: order.totalPayable ?? order.total,
          items: restoredCart.length,
        });
        posDebug("open_order.pos_loader.recomputed_totals", {
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
        if (order.whatsappNumClienteCountry === "ESA" || order.whatsappNumClienteCountry === "USA") {
          setWhatsappClientCountry(order.whatsappNumClienteCountry);
        }
        if (order.whatsappNumCliente) {
          const country = order.whatsappNumClienteCountry === "USA" ? "USA" : "ESA";
          setWhatsappClientInput(formatWhatsAppClientPhone(country, order.whatsappNumCliente));
        } else {
          setWhatsappClientInput("");
        }
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
          posDebug("open_order.pay.load", {
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
        whatsappNumCliente?: string;
        whatsappNumClienteCountry?: WhatsAppCountry;
      };
      const restoredCart = Array.isArray(parsed.cart) ? parsed.cart : [];
      if (restoredCart.length > 0) {
        setCart(restoredCart);
      }
      const restoredServiceType = normalizeServiceTypeKey(parsed.serviceType || "", serviceTypes);
      if (restoredServiceType) setServiceType(restoredServiceType);
      if (parsed.selectedCustomerId) setSelectedCustomerId(parsed.selectedCustomerId);
      if (restoredCart.length > 0 && parsed.selectedDiscount) setSelectedDiscount(parsed.selectedDiscount);
      if (parsed.dteDocumentType && parsed.dteDocumentType !== "SX") setDteDocumentType(parsed.dteDocumentType);
      if (typeof parsed.ivaExempt === "boolean") setIvaExempt(parsed.ivaExempt);
      if (parsed.whatsappNumClienteCountry === "ESA" || parsed.whatsappNumClienteCountry === "USA") {
        setWhatsappClientCountry(parsed.whatsappNumClienteCountry);
      }
      if (parsed.whatsappNumCliente) {
        const country = parsed.whatsappNumClienteCountry === "USA" ? "USA" : "ESA";
        setWhatsappClientInput(formatWhatsAppClientPhone(country, parsed.whatsappNumCliente));
      }
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
          whatsappNumCliente: whatsappClientInput,
          whatsappNumClienteCountry: whatsappClientCountry,
        })
      );
    }, 250);
    return () => {
      if (draftPersistTimeoutRef.current) window.clearTimeout(draftPersistTimeoutRef.current);
    };
  }, [cart, dteDocumentType, ivaExempt, posDraftStorageKey, selectedCustomerId, selectedDiscount, serviceType, whatsappClientCountry, whatsappClientInput]);

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
    const selected = customers.find((customer) => String(customer.id) === selectedCustomerId);
    setIvaExempt(Boolean(dteDocumentType === "CF" && selected?.clientType === "CF" && selected.isIvaExempt));
  }, [customers, dteDocumentType, selectedCustomerId]);

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

  const cartAvailabilityItems = useMemo(() => {
    const grouped = new Map<number, number>();
    cart.forEach((item) => {
      if (item.productId) grouped.set(item.productId, (grouped.get(item.productId) ?? 0) + item.quantity);
    });
    return Array.from(grouped.entries()).map(([productId, quantity]) => ({ productId, quantity }));
  }, [cart]);

  const productAvailability = (productId: number | null | undefined) => (productId ? cartAvailability[productId] : undefined);
  const canAddProductByStock = (productId: number | null | undefined) => {
    const row = productAvailability(productId);
    return !row || row.resolvedPolicy !== "block" || row.canAddOne;
  };
  const warnIfStockLimited = (productId: number | null | undefined) => {
    const row = productAvailability(productId);
    if (!row) return;
    if (row.resolvedPolicy === "block" && !row.canAddOne) toast.error(row.policySource === "category" ? "Bloqueado por política de categoría." : "No hay stock disponible para agregar más unidades de este producto.");
    else if (row.resolvedPolicy === "warn" && row.status === "warning") toast.warning("Este producto no tiene stock suficiente.");
  };

  useEffect(() => {
    const candidateProductIds = filteredProducts.map((product) => product.id);
    const timeout = window.setTimeout(() => {
      void checkCartInventoryAvailability({ cartItems: cartAvailabilityItems, candidateProductIds })
        .then((result) => setCartAvailability(Object.fromEntries(result.items.map((item) => [item.productId, item]))))
        .catch((error) => console.error("Failed to check cart inventory", error));
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [cartAvailabilityItems, products, selectedCategory, searchQuery]);

  const getPosModifierGroups = (product: Product | null) => {
    const visibleGroupIds = product?.modifierGroupsPos ?? product?.modifierGroups ?? [];
    if (!visibleGroupIds.length) return [] as ModifierGroup[];
    return visibleGroupIds
      .map((groupId) => modifierGroups.find((group) => group.id === groupId))
      .filter((group): group is ModifierGroup => Boolean(group));
  };

  const handleProductClick = (product: Product) => {
    if (requiresCashOpen) {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] pos-blocked", { action: "product-click", reason: "requires-cash-open" });
      }
      return;
    }
    if (!canAddProductByStock(product.id)) {
      warnIfStockLimited(product.id);
      return;
    }
    warnIfStockLimited(product.id);
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

  const cycleServiceType = () => {
    if (serviceTypes.length === 0) return;
    const currentIndex = serviceTypes.findIndex((type) => type.key === serviceType);
    const nextType = serviceTypes[(currentIndex + 1) % serviceTypes.length] ?? serviceTypes[0];
    if (!nextType) return;
    setServiceType(nextType.key);
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
    if (requiresCashOpen) {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] pos-blocked", { action: "addToCart", reason: "requires-cash-open" });
      }
      return;
    }
    if (!canAddProductByStock(product.id)) {
      warnIfStockLimited(product.id);
      return;
    }
    warnIfStockLimited(product.id);
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
    if (requiresCashOpen) return;
    const target = cart.find((item) => item.id === itemId);
    if (delta > 0 && target && !canAddProductByStock(target.productId)) {
      warnIfStockLimited(target.productId);
      return;
    }
    setCart(
      cart
        .map((item) =>
          item.id === itemId ? { ...item, quantity: item.quantity + delta } : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeItem = (itemId: string) => {
    if (requiresCashOpen) return;
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
    posDebug("open_order.pay.modal_totals", {
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
        whatsappNumCliente: normalizedWhatsappClient ?? "",
        whatsappNumClienteCountry: normalizedWhatsappClient ? whatsappClientCountry : "",
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
      posDebug("open_order.save.start", { id: order.id, is_update: false });
    } else {
      order = await getOrderById(order.id);
      setActiveOrder(order);
    }
    const dueCents = typeof order.remainingCents === "number" ? order.remainingCents : Math.round(toNumber(order.remaining) * 100);
    setPaymentAmount(centsToInput(dueCents));
    setTipAmount("0");
    setPaymentReference("");
    setSelectedPaymentMethodCode("");
    setPaymentMethodAutoSelectedFromOrderType(false);
    setPaymentMethod("cash");
    setCardType(null);
    setShowCashPanel(false);
    setActiveTenderField(null);
    setSplitEnabled(false);
    const initialParts = splitEvenly(dueCents, 1);
    setParts(initialParts);
    setActivePartId(initialParts[0]?.id ?? null);
    setIsPaymentOpen(true);
  };

  const requestOpenSession = (postAction?: () => Promise<void>, resolver?: (opened: boolean) => void) => {
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      posDebug("[cash-debug] open-session-modal", {
        source: "requestOpenSession",
        hasPostAction: Boolean(postAction),
        currentCashSession: cashSnapshot.session?.id ?? null,
        requiresCashOpen,
      });
    }
    postOpenSessionActionRef.current = postAction ?? null;
    openSessionResolverRef.current = resolver ?? null;
    setOpenSessionAmount("0.00");
    setIsOpenSessionModalOpen(true);
    setTimeout(() => openSessionInputRef.current?.select(), 0);
  };

  const cancelPendingCheckoutContinuation = (reason: string) => {
    const hadPendingContinuation = Boolean(postOpenSessionActionRef.current);
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      posDebug("[cash-debug] continue-checkout", { reason, executed: false, hadPendingContinuation });
    }
    postOpenSessionActionRef.current = null;
    openSessionResolverRef.current?.(false);
    openSessionResolverRef.current = null;
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
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      posDebug("[cash-debug] cobrar-click", {
        cartItems: cart.length,
        cartTotal: total,
        currentCashSession: cashSnapshot.session?.id ?? null,
        open: cashSnapshot.open,
        requiresCashOpen,
        isOpenSessionModalOpen,
        customerId: checkoutCustomer?.id ?? null,
        customerType: checkoutCustomer?.clientType ?? null,
        whatsappNumCliente: normalizedWhatsappClient ?? "",
        whatsappNumClienteCountry: normalizedWhatsappClient ? whatsappClientCountry : "",
      });
    }
    try {
      await ensureCashSessionOpen(async () => {
        if (import.meta.env.DEV) {
          // eslint-disable-next-line no-console
          posDebug("[cash-debug] continue-checkout", { reason: "cash-ready" });
        }
        await proceedToCheckout();
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (/caja no aperturada|cash session|required/i.test(message)) {
        if (import.meta.env.DEV) {
          // eslint-disable-next-line no-console
          posDebug("[cash-debug] checkout-blocked", { reason: message });
        }
        try {
          const current = await getCurrentCashSession();
          setCashSnapshot(current);
          if (!current.open) {
            requestOpenSession(async () => {
              if (import.meta.env.DEV) {
                // eslint-disable-next-line no-console
                posDebug("[cash-debug] continue-checkout", { reason: "resolved-after-error" });
              }
              await proceedToCheckout();
            });
            return;
          }
          await proceedToCheckout();
          return;
        } catch {
          requestOpenSession(async () => {
            if (import.meta.env.DEV) {
              // eslint-disable-next-line no-console
              posDebug("[cash-debug] continue-checkout", { reason: "resolved-after-refetch-failed" });
            }
            await proceedToCheckout();
          });
        }
        return;
      }
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] checkout-blocked", { reason: "order-or-backend-error", message });
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

  const checkoutCustomer = useMemo(
    () => customers.find((customer) => String(customer.id) === selectedCustomerId) ?? null,
    [customers, selectedCustomerId],
  );
  const normalizedWhatsappClient = useMemo(() => {
    const trimmed = whatsappClientInput.trim();
    if (!trimmed) return null;
    const parsed = normalizeWhatsAppClientPhone(whatsappClientCountry, trimmed);
    return parsed.ok ? parsed.e164 : null;
  }, [whatsappClientCountry, whatsappClientInput]);

  const pendingSelectionValidation = getPendingSelectionValidation();
  const selectedExtrasCount = pendingSelectionValidation.selectedMods.length;
  const canAddPendingProduct = Object.keys(pendingSelectionValidation.errors).length === 0 && (!pendingProduct || canAddProductByStock(pendingProduct.id));

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
    if (editingModifiersItemId) {
      setCart((prev) =>
        prev.map((item) =>
          item.id === editingModifiersItemId
            ? {
                ...item,
                modifiers: pendingSelectionValidation.selectedMods,
                price: getItemBaseEffective(item) + pendingSelectionValidation.selectedMods.reduce((sum, mod) => sum + Number(mod.price || 0), 0),
              }
            : item
        )
      );
    } else {
      addToCart(pendingProduct, pendingSelectionValidation.selectedMods);
    }
    setIsExtrasOpen(false);
    setPendingProduct(null);
    setEditingModifiersItemId(null);
    setSelectedModifiers({});
    setOpenModifierGroups({});
    setModifierValidationErrors({});
  };



  const loadRecentSalesActions = async () => {
    if (!canViewRecentSalesActions) return;
    setRecentSalesLoading(true);
    setRecentSalesError("");
    try {
      setRecentSales(await getRecentSalesActions());
    } catch (error) {
      const statusCode = error instanceof ApiRequestError ? error.status : undefined;
      setRecentSalesError(statusCode === 403 ? "No tienes permiso para ver ventas recientes." : "No se pudieron cargar las ventas recientes. Intenta nuevamente.");
    } finally {
      setRecentSalesLoading(false);
    }
  };

  const openRecentSalesActions = () => {
    setIsRecentSalesOpen(true);
    void loadRecentSalesActions();
  };

  const handleRecentSalePrint = async (sale: RecentSaleAction) => {
    setRecentSalesPrintingId(sale.paymentId);
    try {
      const result = await smartPrintTicket({ paymentId: sale.paymentId });
      toast.success(result.method === "direct" ? "Ticket enviado a impresora." : "Ticket listo para imprimir.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo imprimir el ticket. Intenta nuevamente.");
    } finally {
      setRecentSalesPrintingId(null);
    }
  };

  const handleRecentSaleSendDte = async (sale: RecentSaleAction) => {
    if (!sale.canSendDte || !sale.controlNumber) {
      toast.warning("Este pedido aún no tiene DTE disponible para enviar.");
      return;
    }
    setRecentSalesSendingId(sale.id);
    try {
      const result = await dteDeliverByOrder(sale.id, ["whatsapp", "email"]);
      if (result.success) toast.success("DTE enviado al cliente.");
      else toast.error(result.summary || "No se pudo enviar DTE");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo enviar DTE");
    } finally {
      setRecentSalesSendingId(null);
    }
  };



  const handleLastSaleQuickAction = async () => {
    if (isQuickSaleProcessing) return;
    setIsQuickSaleProcessing(true);
    try {
      const sale = await getLastSaleAction();
      if (!sale) {
        toast.warning("No hay una venta reciente para reimprimir.");
        return;
      }

      let dteSent = false;
      const dteSkipped = !sale.canSendDte || !sale.controlNumber;
      let dteContactIssue = false;
      if (!dteSkipped) {
        try {
          const result = await dteDeliverByOrder(sale.orderId, ["whatsapp", "email"]);
          dteSent = Boolean(result.success);
          if (!result.success) {
            const errors = Object.values(result.results ?? {}).map((row) => row?.error).filter(Boolean).join(" ");
            dteContactIssue = /contacto|correo|email|whatsapp|tel[eé]fono|recipient|destinatario/i.test(errors || result.summary || "");
          }
        } catch (error) {
          dteContactIssue = /contacto|correo|email|whatsapp|tel[eé]fono|recipient|destinatario/i.test(error instanceof Error ? error.message : String(error));
        }
      }

      let printed = false;
      try {
        await smartPrintTicket({ paymentId: sale.paymentId, orderId: sale.orderId });
        printed = true;
      } catch (error) {
        if (dteSent) {
          toast.warning("DTE enviado, pero no se pudo abrir la impresión del ticket.");
          return;
        }
        throw error;
      }

      if (printed && dteSent) toast.success("Ticket reenviado a impresión y DTE enviado al cliente.");
      else if (printed && dteSkipped) toast.warning("Ticket reenviado a impresión. Este pedido aún no tiene DTE disponible para enviar.");
      else if (printed && dteContactIssue) toast.warning("Ticket reenviado a impresión. No se encontró contacto para reenviar DTE.");
      else if (printed) toast.warning("Ticket reenviado a impresión. No se pudo reenviar el DTE al cliente.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo procesar la última venta.");
    } finally {
      setIsQuickSaleProcessing(false);
    }
  };

  const loadCashData = async () => {
    try {
      const snapshot = await getCurrentCashSession();
      let transactions = [] as Awaited<ReturnType<typeof getCashTransactions>>;
      try {
        transactions = await getCashTransactions();
      } catch (transactionsError) {
        console.warn("cash.transactions.load_failed", {
          reason: transactionsError instanceof Error ? transactionsError.message : String(transactionsError),
          non_blocking: true,
        });
        toast.warning("No se pudieron cargar transacciones de caja, pero puedes continuar.");
      }
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] current-session", {
          open: snapshot.open,
          sessionId: snapshot.session?.id ?? null,
          status: getCashSessionStatus(snapshot),
          totalSessionsToday: snapshot.totalSessionsToday ?? 0,
          lastOpenedAt: snapshot.lastOpenedAt ?? null,
          lastClosedAt: snapshot.lastClosedAt ?? null,
        });
      }
      setCashSnapshot(snapshot);
      setCashTransactions(transactions);
      const hasOpenCashSession = getCashSessionStatus(snapshot).hasOpenCashSession;
      posDebug("cash.open_session_modal", {
        source: "loadCashData",
        reason: hasOpenCashSession ? "session_open" : "session_closed",
      });
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-modal", {
          source: "loadCashData",
          action: hasOpenCashSession ? "close" : "open",
          reason: hasOpenCashSession ? "session-open" : "session-missing",
        });
      }
      setIsOpenSessionModalOpen(!hasOpenCashSession);
    } catch (error) {
      console.error("Failed to load cash data", error);
      toast.error("No se pudo cargar información de caja");
      posDebug("cash.open_session_modal", {
        source: "loadCashData",
        reason: "fetch_error",
      });
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-modal", { source: "loadCashData", action: "open", reason: "fetch-error" });
      }
      setCashSnapshot({ open: false, hasOpenCashSession: false, session: undefined });
      setIsOpenSessionModalOpen(true);
    } finally {
      setIsCashGateLoading(false);
    }
  };

  useEffect(() => {
    getFeatureFlags()
      .then((flags) => {
        const enabled = flags.some((flag) => flag.key === "FF_CASH_CLOSE_ALLOW_PENDING_ORDERS" && flag.isEnabled);
        setAllowCloseWithPendingOrders(enabled);
      })
      .catch(() => undefined);
    getFeatureSettings().then((settings) => {
      setInventoryStockPolicy(settings.inventoryStockPolicy);
      setPosProductImagesEnabled(settings.posProductImagesEnabled);
      setTableMapEnabled(settings.tableMapEnabled);
      setQuickSalesMode(settings.posQuickSalesButtonMode);
      setQuickSalesHistoryScope(settings.posQuickSalesHistoryScope);
      setQuickSalesHistoryWindowMinutes(settings.posQuickSalesHistoryWindowMinutes);
    }).catch(() => undefined);
    loadCashData().catch(() => undefined);
    const forceCashGate = () => {
      setCashSnapshot((previous) => ({ ...previous, open: false, hasOpenCashSession: false, session: undefined }));
      if (cashCloseFlowState === "pendingUserAck" || cashCloseFlowState === "closingInProgress") {
        return;
      }
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-modal", { source: "cash:required", action: "open" });
      }
      setIsOpenSessionModalOpen(true);
    };
    window.addEventListener("cash:required", forceCashGate as EventListener);
    return () => {
      window.removeEventListener("cash:required", forceCashGate as EventListener);
    };
  }, [cashCloseFlowState]);

  const refreshPaymentMethods = useCallback(() => {
    getPaymentMethods().then((methods) => {
      setPaymentMethods(methods.filter((method) => method.isActive !== false));
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshPaymentMethods();
    window.addEventListener("payment-methods:changed", refreshPaymentMethods);
    return () => window.removeEventListener("payment-methods:changed", refreshPaymentMethods);
  }, [refreshPaymentMethods]);

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
      setDteDocumentType(selected.clientType === "SX" ? "CF" : selected.clientType);
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

  const paymentMethodButtons = useMemo<PaymentButtonOption[]>(() => {
    return paymentMethods
      .filter((method) => method.isActive !== false)
      .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.name.localeCompare(b.name))
      .map((method) => ({
        code: method.code,
        label: method.name || method.code,
        method: getPaymentMethodKind(method),
        option: method,
      }));
  }, [paymentMethods]);

  const selectedPaymentMethodOption = useMemo(
    () => paymentMethods.find((method) => String(method.code || "").toLowerCase() === String(selectedPaymentMethodCode || "").toLowerCase()),
    [paymentMethods, selectedPaymentMethodCode],
  );
  const selectedPaymentIsCash = Boolean(selectedPaymentMethodOption) && (isCashPaymentMethod(selectedPaymentMethodOption) || shouldOpenCashDrawer(paymentMethod, selectedPaymentMethodCode));
  const selectedPaymentAutoPrint = Boolean(selectedPaymentMethodOption?.autoPrintTicket);
  const selectedServiceType = useMemo(
    () => serviceTypes.find((type) => type.key === serviceType) ?? serviceTypes[0] ?? null,
    [serviceTypes, serviceType],
  );

  const selectPaymentMethodOption = useCallback((option: PaymentButtonOption, autoSelectedFromOrderType = false) => {
    setPaymentMethod(option.method);
    setSelectedPaymentMethodCode(option.code);
    setPaymentMethodAutoSelectedFromOrderType(autoSelectedFromOrderType);
    setCardType(option.method === "card" ? "credit" : null);
    const cashSelected = isCashPaymentMethod(option.option) || shouldOpenCashDrawer(option.method, option.code);
    setShowCashPanel(cashSelected);
    if (cashSelected) {
      setPaymentAmount(centsToInput(expectedPaymentCents));
      setTipAmount("0");
      setActiveTenderField("payment");
    } else {
      setTipAmount("0");
      setActiveTenderField(null);
    }
    setShouldResetTenderOnFirstTap(true);
  }, [expectedPaymentCents]);

  const resolveConfiguredPaymentMethod = useCallback((type: ServiceType | null | undefined) => {
    const linked = type
      ? paymentMethodButtons.find((option) => option.option.linkedOrderTypeId === type.id)
      : null;
    if (linked) return linked;
    return paymentMethodButtons.find((option) => option.option.isDefault) ?? paymentMethodButtons[0] ?? null;
  }, [paymentMethodButtons]);

  const applyConfiguredPaymentMethod = useCallback((autoSelectedFromOrderType = false) => {
    const option = resolveConfiguredPaymentMethod(selectedServiceType);
    if (!option) return false;
    selectPaymentMethodOption(option, autoSelectedFromOrderType || option.option.linkedOrderTypeId === selectedServiceType?.id);
    return true;
  }, [resolveConfiguredPaymentMethod, selectPaymentMethodOption, selectedServiceType]);

  useEffect(() => {
    if (!serviceType || paymentMethods.length === 0) return;
    const serviceTypeChanged = previousServiceTypeRef.current !== serviceType;
    if (serviceTypeChanged) {
      applyConfiguredPaymentMethod(true);
    } else if (!selectedPaymentMethodCode) {
      applyConfiguredPaymentMethod(false);
    }
    previousServiceTypeRef.current = serviceType;
  }, [applyConfiguredPaymentMethod, paymentMethods.length, selectedPaymentMethodCode, serviceType]);

  useEffect(() => {
    if (!isPaymentOpen || selectedPaymentMethodCode) return;
    applyConfiguredPaymentMethod(false);
  }, [applyConfiguredPaymentMethod, isPaymentOpen, selectedPaymentMethodCode]);

  useEffect(() => {
    if (!isPaymentOpen) {
      setShowCashPanel(false);
      return;
    }
    if (!selectedPaymentIsCash) {
      setShowCashPanel(false);
    }
    if (!showCashPanel || !selectedPaymentIsCash) {
      if (splitEnabled) {
        const targetAmount = (activeSplitPart?.amountCents ?? checkoutTotalCents) / 100;
        setPaymentAmount(toNumber(targetAmount).toFixed(2));
      } else {
        setPaymentAmount(toNumber(checkoutTotal).toFixed(2));
      }
      if (selectedPaymentIsCash && !showCashPanel) {
        setTipAmount("0");
        setActiveTenderField(null);
      }
    }
  }, [checkoutTotal, checkoutTotalCents, isPaymentOpen, splitEnabled, activeSplitPart, selectedPaymentIsCash, showCashPanel]);

  useEffect(() => {
    if (!isPaymentOpen || !selectedPaymentIsCash || !showCashPanel) return;
    let frame = 0;
    let nestedFrame = 0;
    frame = window.requestAnimationFrame(() => {
      nestedFrame = window.requestAnimationFrame(() => {
        const container = checkoutModalScrollRef.current;
        if (container) {
          container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        } else {
          cashPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
        }
        cashAmountInputRef.current?.focus({ preventScroll: true });
      });
    });
    return () => {
      window.cancelAnimationFrame(frame);
      window.cancelAnimationFrame(nestedFrame);
    };
  }, [isPaymentOpen, selectedPaymentIsCash, showCashPanel]);

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
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      posDebug("[cash-debug] open-session-submit", { amount: Number(openSessionAmount || 0), currentCashSession: cashSnapshot.session?.id ?? null });
    }
    setIsSavingCashAction(true);
    try {
      await openCashSession(Number(openSessionAmount || 0));
      const current = await getCurrentCashSession();
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-refetch", {
          open: current.open,
          sessionId: current.session?.id ?? null,
          status: getCashSessionStatus(current),
        });
      }
      setCashSnapshot(current);
      if (!current.open) {
        toast.error("No se pudo confirmar apertura de caja.");
        openSessionResolverRef.current?.(false);
        return;
      }
      await loadCashData();
      const action = postOpenSessionActionRef.current;
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-result", { status: "opened", willContinueCheckout: Boolean(action) });
      }
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
            if (import.meta.env.DEV) {
              // eslint-disable-next-line no-console
              posDebug("[cash-debug] open-session-result", { status: "already-open", willContinueCheckout: Boolean(action) });
            }
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
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-debug] open-session-result", { status: "error", message, willContinueCheckout: false });
      }
      openSessionResolverRef.current?.(false);
      toast.error(`No se pudo aperturar la caja: ${message}`);
    } finally {
      openSessionResolverRef.current = null;
      setIsSavingCashAction(false);
    }
  };

  const handleCloseCashSession = async () => {
    if (closeCashSubmittingRef.current || isSavingCashAction) return;
    if (!canCloseCash) {
      toast.error("No tienes permisos para cerrar caja.");
      return;
    }
    if (pendingOrdersCount > 0 && !allowCloseWithPendingOrders) {
      toast.error(`You cannot close the register because there are ${pendingOrdersCount} open orders.`);
      return;
    }
    const totalBills = Number(closeBillsInput || 0);
    const totalCoins = Number(closeCoinsInput || 0);
    const totalPosCards = Number(closePosCardsInput || 0);
    const totalPedidosYa = Number(closePedidosYaInput || 0);
    const totalBillsCents = toCents(closeBillsInput);
    const totalCoinsCents = toCents(closeCoinsInput);
    const countedTotal = moneyToFixedString((totalBillsCents + totalCoinsCents) / 100);
    if (
      !Number.isFinite(totalBills) || totalBills < 0
      || !Number.isFinite(totalCoins) || totalCoins < 0
      || !Number.isFinite(totalPosCards) || totalPosCards < 0
      || !Number.isFinite(totalPedidosYa) || totalPedidosYa < 0
    ) {
      toast.error("Ingresa montos válidos para el cierre.");
      return;
    }
    closeCashSubmittingRef.current = true;
    setCashCloseFlowState("closingInProgress");
    setIsSavingCashAction(true);
    try {
      const closeResp = await closeCashSession(
        countedTotal,
        cashNotes,
        {
          bills: moneyToFixedString(closeBillsInput),
          coins: moneyToFixedString(closeCoinsInput),
          posCards: moneyToFixedString(closePosCardsInput),
          pedidosYa: moneyToFixedString(closePedidosYaInput),
        },
        { sessionId: cashSnapshot.session?.id }
      );
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        posDebug("[cash-close-flow] close_success", { sessionId: closeResp.sessionId ?? null, printed: closeResp.printed, printError: closeResp.printError ?? null });
      }
      if (closeResp.sessionId) {
        setLastClosedSessionId(closeResp.sessionId);
        localStorage.setItem("last_closed_cash_session_id", String(closeResp.sessionId));
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
          posDebug("[cash-close-flow] fallback_modal_opened");
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
              posDebug("[cash-close-flow] user_ack_download");
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
      closeCashSubmittingRef.current = false;
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

  const buildQuickPrintPendingReference = () => {
    const existing = pendingReferenceDraft.trim();
    if (existing) return existing;
    const label = selectedCustomer?.fullName || selectedCustomer?.name || "POS";
    return `QuickPrint ${label}`.slice(0, 120);
  };

  const ensureOrderForQuickPrint = async (): Promise<Order> => {
    if (activeOrder) return activeOrder;
    if (cart.length === 0) {
      throw new Error("No hay productos en el pedido");
    }
    const created = await createOrder({
      serviceType,
      customerName: selectedCustomer?.fullName || selectedCustomer?.name || "CONSUMIDOR FINAL",
      customerId: selectedCustomer ? Number(selectedCustomer.id) : undefined,
      whatsappNumCliente: normalizedWhatsappClient ?? "",
      whatsappNumClienteCountry: normalizedWhatsappClient ? whatsappClientCountry : "",
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
    setActiveOrder(created);
    setCreatedOrderId(created.id);
    setCreatedOrderNumber(created.orderNumber ?? null);
    return created;
  };

  const saveCurrentOrderAsHeld = async (order: Order): Promise<Order> => {
    const pendingState = order.paymentStatus === "paid" ? "paid_pending_delivery" : "pending_payment";
    const payloadItems = cart.length > 0
      ? buildPendingPayloadItems(cart)
      : buildPendingPayloadItems(order.items.map((item) => mapOrderItemToCartItem(item)));
    const saved = await setOrderPending(order.id, {
      isPending: true,
      pendingState,
      pendingReference: buildQuickPrintPendingReference(),
      authorizationPin: pendingEditAuthorizationPin || undefined,
      items: payloadItems,
    });
    setActiveOrder(saved);
    return saved;
  };

  const handleQuickPrintTicket = async () => {
    if (cart.length === 0 && !(activeOrder?.items?.length)) {
      toast.info("No hay pedido para imprimir");
      return;
    }
    try {
      const baseOrder = await ensureOrderForQuickPrint();
      const heldOrder = baseOrder.isPending ? baseOrder : await saveCurrentOrderAsHeld(baseOrder);
      const result = await smartPrintTicket({ orderId: heldOrder.id, preferDirect: false });
      if (result.method === "direct") toast.success("Ticket enviado a impresora.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo imprimir el ticket");
    }
  };

  const syncExistingOpenOrder = async (order: Order) => {
    const pricing = calculatePosPricing({
      items: cart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
      products,
      serviceType,
      serviceTypes,
      selectedDiscount: null,
      availableDiscounts,
    });
    posDebug("open_order.update.request", { order_id: order.id, is_update: true });
    posDebug("open_order.save.payload", {
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
    posDebug("open_order.save.done", {
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
          whatsappNumCliente: normalizedWhatsappClient ?? "",
          whatsappNumClienteCountry: normalizedWhatsappClient ? whatsappClientCountry : "",
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
        posDebug("open_order.save.start", { id: saved.id, is_update: false });
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
      setEditingModifiersItemId(null);
      setSelectedModifiers({});
      setOpenModifierGroups({});
      setModifierValidationErrors({});
    }
  };

  const handleEditLineModifiers = (itemId: string) => {
    const cartItem = cart.find((item) => item.id === itemId);
    if (!cartItem?.productId) {
      toast.error("Esta línea no permite modificadores");
      return;
    }
    const product = products.find((candidate) => candidate.id === cartItem.productId);
    if (!product) {
      toast.error("No se encontró el producto");
      return;
    }
    if (!canAddProductByStock(product.id)) {
      warnIfStockLimited(product.id);
      return;
    }
    warnIfStockLimited(product.id);
    const visibleGroups = getPosModifierGroups(product);
    if (!visibleGroups.length) {
      toast.error("Este producto no tiene modificadores disponibles");
      return;
    }
    const modifiersByGroup = visibleGroups.reduce<Record<string, string[]>>((acc, group) => {
      const selected = cartItem.modifiers
        .filter((mod) => mod.id != null && group.modifiers.some((candidate) => candidate.id === mod.id))
        .map((mod) => String(mod.id));
      acc[String(group.id)] = selected;
      return acc;
    }, {});
    const openState = visibleGroups.reduce<Record<string, boolean>>((acc, group) => {
      acc[String(group.id)] = false;
      return acc;
    }, {});
    setPendingProduct(product);
    setEditingModifiersItemId(itemId);
    setSelectedModifiers(modifiersByGroup);
    setOpenModifierGroups(openState);
    setModifierValidationErrors({});
    setIsExtrasOpen(true);
  };

  const focusTenderField = (field: "payment" | "tip") => {
    setActiveTenderField(field);
    setShouldResetTenderOnFirstTap(true);
  };

  const applyTenderDenomination = (amountCents: number) => {
    const field = activeTenderField ?? "payment";
    const current = field === "payment" ? parseMoneyToCents(paymentAmount) : parseMoneyToCents(tipAmount);
    const next = shouldResetTenderOnFirstTap ? amountCents : current + amountCents;
    const value = centsToInput(next);
    if (field === "payment") setPaymentAmount(value);
    if (field === "tip") setTipAmount(value);
    setActiveTenderField(field);
    setShouldResetTenderOnFirstTap(false);
  };

  const clearTenderField = () => {
    const field = activeTenderField ?? "payment";
    if (field === "payment") setPaymentAmount("");
    if (field === "tip") setTipAmount("");
    setActiveTenderField(field);
    setShouldResetTenderOnFirstTap(true);
  };

  const backspaceTenderField = () => {
    const field = activeTenderField ?? "payment";
    const currentRaw = field === "payment" ? paymentAmount : tipAmount;
    const nextRaw = currentRaw.slice(0, -1);
    if (field === "payment") setPaymentAmount(nextRaw);
    if (field === "tip") setTipAmount(nextRaw);
    setActiveTenderField(field);
    setShouldResetTenderOnFirstTap(false);
  };

  const setExactTenderAmount = () => {
    setPaymentAmount(centsToInput(totalDueCents));
    setActiveTenderField("payment");
    setShouldResetTenderOnFirstTap(false);
  };

  const clearPersistedDraft = () => {
    localStorage.removeItem(posDraftStorageKey);
  };

  const finalizePaidSale = () => {
    const previousPaymentMethod = paymentMethod;
    const previousPaymentMethodCode = selectedPaymentMethodCode;
    const previousPath = `${location.pathname}${location.search}`;
    setIsPaymentOpen(false);
    setIsPaymentMethodOpen(false);
    setPaymentMethod("cash");
    setSelectedPaymentMethodCode("");
    setPaymentMethodAutoSelectedFromOrderType(false);
    setCardType(null);
    setPaymentAmount("");
    setTipAmount("");
    setPaymentReference("");
    setShowCashPanel(false);
    setActiveTenderField(null);
    setShouldResetTenderOnFirstTap(true);
    setActiveOrder(null);
    setCart([]);
    setSelectedDiscount(null);
    setCheckoutDraft(null);
    setCreatedOrderId(null);
    setCreatedOrderNumber(null);
    setLastPaymentId(null);
    setSplitEnabled(false);
    setParts([]);
    setActivePartId(null);
    setKitchenPromptOrderId(null);
    setIsKitchenPromptOpen(false);
    setPostSaleKitchenChoice(true);
    setPostSalePrintChoice(true);
    setSaleCompletionSummary(null);
    setFallbackPdfModal({
      open: false,
      title: "",
      message: "",
      onDownload: null,
      shouldHardReloadAfterClose: false,
    });
    setDteDocumentType("CF");
    if (defaultConsumerCustomer) {
      setSelectedCustomerId(String(defaultConsumerCustomer.id));
    } else {
      setSelectedCustomerId("");
    }
    hydratedPendingOrderIdRef.current = null;
    clearPersistedDraft();
    posDebug("[pos-finalize] reset_state", {
      previousPath,
      nextPath: "/pos",
      previousPaymentMethod,
      previousPaymentMethodCode,
      nextPaymentMethod: "cash",
      nextPaymentMethodCode: "cash",
    });
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
      posDebug("[pos-debug] hard_reload", { reason });
    }
    window.location.reload();
  }, []);

  const scheduleHardReload = (reason: string) => {
    if (hardReloadTriggeredRef.current) return;
    window.setTimeout(() => hardReloadPos(reason), 400);
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
        // Evitar aviso duplicado: el flujo de cierre ya confirma la venta.
      }
      const shouldPrintTicket = Boolean(lastPaymentId) && (postSalePrintChoice || lastPaymentAutoPrint);
      if (shouldPrintTicket && lastPaymentId) {
        try {
          const result = await smartPrintTicket({ paymentId: lastPaymentId });
          if (result.method === "direct") toast.success("Ticket enviado a impresora.");
        } catch (printError) {
          console.error("Ticket print failed", printError);
          toast.warning("La venta fue registrada, pero no se pudo imprimir el ticket.");
        }
      }
      setIsKitchenPromptOpen(false);
      posDebug("[pos-finalize] confirm", {
        orderId: kitchenPromptOrderId,
        sendToKitchen: shouldSend,
        printChoice: postSalePrintChoice,
        nextPath: "/pos",
      });
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


  const showStockWarningModal = (check: InventoryAvailabilityCheck, mode: "warn" | "block"): Promise<boolean> => {
    if (mode === "block") {
      setStockWarning({ check, mode });
      return Promise.resolve(false);
    }
    return new Promise((resolve) => setStockWarning({ check, mode, resolve }));
  };

  const closeStockWarning = (confirmed: boolean) => {
    stockWarning?.resolve?.(confirmed);
    setStockWarning(null);
  };

  const validateInventoryBeforeFinalPayment = async (orderId: number | string): Promise<boolean | null> => {
    try {
      const check = await checkOrderInventoryAvailability(orderId);
      if (!check.hasInsufficientStock) return false;
      if (check.policy === "block") {
        await showStockWarningModal(check, "block");
        return null;
      }
      if (check.policy === "warn") {
        const confirmed = await showStockWarningModal(check, "warn");
        return confirmed ? true : null;
      }
      toast.warning("Hay artículos con stock insuficiente, pero la política actual permite continuar.");
      return false;
    } catch (error) {
      console.error("Inventory availability check failed", error);
      toast.warning("No se pudo verificar inventario. Revisa la conexión o intenta de nuevo.");
      return inventoryStockPolicy === "block" ? null : false;
    }
  };

  const handleSubmitPayment = async () => {
    if (isProcessingPayment) return;
    if (!checkoutDraft || checkoutDraft.items.length === 0) {
      toast.error("No hay productos en el pedido");
      return;
    }
    if (!selectedPaymentMethodCode) {
      toast.error("Selecciona un método de pago.");
      return;
    }
    const rawAmountReceived = toNumber(paymentAmount);
    const rawTipValue = toNumber(tipAmount);
    const exactCashAmount = expectedPaymentCents / 100;
    const amountReceived = selectedPaymentIsCash && !showCashPanel ? exactCashAmount : rawAmountReceived;
    const tipValue = selectedPaymentIsCash && !showCashPanel ? 0 : rawTipValue;
    const totalDue = selectedPaymentIsCash && !showCashPanel ? exactCashAmount : totalDueCents / 100;
    const remainingOrderAmount = Math.max(0, toNumber(activeOrder?.remaining) || checkoutTotal);
    const splitPartAmount = splitEnabled ? (activeSplitPart?.amountCents ?? expectedPaymentCents) / 100 : null;
    const paymentAmountForApi = splitEnabled ? (splitPartAmount ?? expectedPaymentCents / 100) : remainingOrderAmount;

    if (selectedPaymentIsCash && (!amountReceived || amountReceived <= 0)) {
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
    if (selectedPaymentIsCash && amountReceived < totalDue) {
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
      const receivedForApi = selectedPaymentIsCash ? amountReceived : amountForApi;

      const inventoryWarningConfirmed = amountForApi >= latestRemaining - 0.01 ? await validateInventoryBeforeFinalPayment(Number(orderId)) : false;
      if (inventoryWarningConfirmed === null) return;

      const paymentResult = await createPayment({
        orderId,
        method: paymentMethod,
        cardType: paymentMethod === "card" ? "credit" : undefined,
        amount: amountForApi,
        amountApplied: amountForApi,
        cashReceived: selectedPaymentIsCash ? receivedForApi : undefined,
        tipAmount: tipValue,
        reference: paymentReference || undefined,
        paymentMethodCode: selectedPaymentMethodCode,
        splitPart: splitEnabled && activeSplitPart ? (parts.findIndex((part) => part.id === activeSplitPart.id) + 1) : undefined,
        inventoryWarningConfirmed,
      });
      setLastPaymentId(paymentResult.id);
      setLastPaymentAutoPrint(selectedPaymentAutoPrint);
      if (shouldOpenCashDrawer(paymentMethod, selectedPaymentMethodCode)) {
        await triggerDrawerOpen({ showSuccessToast: false });
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
        const finalTotalToPay = toNumber(refreshed.totalPayable ?? refreshed.total ?? checkoutSummaryTotal);
        setSaleCompletionSummary(
          buildSaleCompletionSummary({
            totalToPay: finalTotalToPay,
            amountReceived: selectedPaymentIsCash ? receivedForApi : amountForApi,
            paymentMethod,
            paymentMethodCode: selectedPaymentMethodCode,
          })
        );
        if (refreshed.isPending) {
          try {
            const finalizedOrder = await setOrderPending(refreshed.id, {
              isPending: false,
              removalReason: "Pagada en POS",
              completionType: "paid",
            });
            posDebug("open_order.finalize_paid", {
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
          setLastPaymentAutoPrint(selectedPaymentAutoPrint);
          setIsKitchenPromptOpen(true);
        }
      } else {
        toast.success("Pago registrado");
      }
    } catch (error) {
      console.error("Failed to create payment", error);
      if (error instanceof ApiRequestError && error.code === "INVENTORY_STOCK_INSUFFICIENT") {
        const availability = (error.payload as any)?.availability;
        if (availability) setStockWarning({ check: { ok: Boolean(availability.ok), policy: availability.policy, hasInsufficientStock: Boolean(availability.has_insufficient_stock), items: (availability.items || []).map((item: any) => ({ inventoryItemId: Number(item.inventory_item_id), name: String(item.name || ""), sku: item.sku || "", unit: String(item.unit || ""), available: String(item.available || "0"), required: String(item.required || "0"), missing: String(item.missing || "0"), affectedProducts: (item.affected_products || []).map((product: any) => ({ productId: Number(product.product_id), productName: String(product.product_name || ""), quantity: String(product.quantity || "0"), policySource: product.policy_source === "product" || product.policy_source === "category" ? product.policy_source : "global", policySourceLabel: String(product.policy_source_label || "Configuración global"), policyLabel: String(product.policy_label || "Permitir venta") })) })), message: availability.message }, mode: availability.policy === "block" ? "block" : "warn" });
        else toast.error(error.message);
      } else {
        toast.error(error instanceof Error ? error.message : "No se pudo registrar el pago");
      }
    } finally {
      setIsProcessingPayment(false);
    }
  };

  const isQuickCustomerSaveDisabled =
    isSavingCustomer ||
    !customerForm.fullName.trim() ||
    !customerForm.departmentCode ||
    !customerForm.municipalityCode ||
    (customerForm.clientType === "CCF" &&
      (!customerForm.companyName.trim() ||
        customerForm.nit.replace(/\D/g, "").length !== 14 ||
        !customerForm.nrc.trim() ||
        customerForm.phone.replace(/\D/g, "").length !== 8 ||
        !customerForm.email.includes("@") ||
        !customerForm.direccion.trim() ||
        (!customerForm.activityCode.trim() && !customerForm.activityDescription.trim())));

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
  const handleOpenCustomerDte = () => {
    if (activeOrder?.whatsappNumClienteCountry === "ESA" || activeOrder?.whatsappNumClienteCountry === "USA") {
      setWhatsappClientCountry(activeOrder.whatsappNumClienteCountry);
    }
    if (activeOrder?.whatsappNumCliente) {
      const country = activeOrder.whatsappNumClienteCountry === "USA" ? "USA" : "ESA";
      setWhatsappClientInput(formatWhatsAppClientPhone(country, activeOrder.whatsappNumCliente));
    }
    setWhatsappClientError("");
    setIsCustomerDteOpen(true);
  };

  const handleAcceptCustomerDte = async () => {
    if (!selectedCustomerId) {
      toast.error("Selecciona un cliente");
      return;
    }
    const trimmedWhatsAppInput = whatsappClientInput.trim();
    if (trimmedWhatsAppInput) {
      const phoneError = validateWhatsAppClientPhone(whatsappClientCountry, trimmedWhatsAppInput);
      if (phoneError) {
        setWhatsappClientError(phoneError);
        toast.error(phoneError);
        return;
      }
    }
    setWhatsappClientError("");
    if (activeOrder) {
      try {
        const updatedOrder = await updateOrderCustomerDte(activeOrder.id, {
          customerId: Number(selectedCustomerId),
          dteDocumentType,
          ivaExempt,
          whatsappNumCliente: normalizedWhatsappClient ?? "",
          whatsappNumClienteCountry: normalizedWhatsappClient ? whatsappClientCountry : "",
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
            whatsappNumCliente: updatedOrder.whatsappNumCliente,
            whatsappNumClienteCountry: updatedOrder.whatsappNumClienteCountry,
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
        isIvaExempt: Boolean(prev.isIvaExempt),
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
      isIvaExempt: false,
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
        isIvaExempt: customerForm.clientType === "CF" && Boolean(customerForm.isIvaExempt),
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
        isIvaExempt: false,
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


  const submitPricePin = useCallback(async (candidatePin = pinInput) => {
    if (candidatePin.length !== 6) return;
    try {
      await validateOrderPricePin(candidatePin);
      setValidatedPin(candidatePin);
      const activeItem = cart.find((item) => item.id === priceEditorItemId);
      setNewPriceInput((activeItem ? getItemBaseEffective(activeItem) : 0).toFixed(2));
      setIsPinModalOpen(false);
      setIsPriceModalOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Código incorrecto");
      setPinInput("");
    }
  }, [cart, pinInput, priceEditorItemId]);

  const appendPricePinDigit = useCallback((digit: string) => {
    setPinInput((previous) => {
      const next = `${previous}${digit}`.replace(/\D/g, "").slice(0, 6);
      if (next.length === 6) {
        window.setTimeout(() => void submitPricePin(next), 0);
      }
      return next;
    });
  }, [submitPricePin]);

  useEffect(() => {
    if (!isPinModalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (/^\d$/.test(event.key)) {
        event.preventDefault();
        appendPricePinDigit(event.key);
      } else if (event.key === "Backspace") {
        event.preventDefault();
        setPinInput((previous) => previous.slice(0, -1));
      } else if (event.key === "Enter") {
        event.preventDefault();
        void submitPricePin();
      } else if (event.key === "Escape") {
        event.preventDefault();
        setIsPinModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [appendPricePinDigit, isPinModalOpen, submitPricePin]);

  const handlePrintReceipt = async () => {
    if (!activeOrder) return;
    try {
      const result = await smartPrintTicket({ orderId: activeOrder.id, preferDirect: false });
      if (result.method === "direct") toast.success("Ticket enviado a impresora.");
    } catch (error) {
      console.error("Failed to print ticket", error);
      toast.error("No se pudo preparar el ticket. Intenta nuevamente.");
    }
  };

  if (isCashGateLoading) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Verificando estado de caja...</div>
      </div>
    );
  }

  if (tableMapEnabled && posMode === "tables") {
    const opsTables = restaurantTables.filter((table) => selectedOpsArea === "all" || table.area === selectedOpsArea).filter((table) => {
      const session = sessionByTableId.get(table.id);
      if (selectedOpsFilter === "free") return !session;
      if (selectedOpsFilter === "occupied") return Boolean(session && session.status !== "sent_to_kitchen");
      if (selectedOpsFilter === "kitchen") return session?.status === "sent_to_kitchen";
      return true;
    });
    const freeCount = restaurantTables.filter((t) => !sessionByTableId.get(t.id)).length;
    const kitchenCount = restaurantTables.filter((t) => sessionByTableId.get(t.id)?.status === "sent_to_kitchen").length;
    const occupiedCount = restaurantTables.filter((t) => !!sessionByTableId.get(t.id) && sessionByTableId.get(t.id)?.status !== "sent_to_kitchen").length;

    return (
      <div className="h-[100dvh] bg-background p-3 sm:p-4">
        <div className="mx-auto grid h-full max-w-[1800px] grid-cols-1 gap-3 lg:grid-cols-[250px_1fr_320px]">
          <Card className="p-3 space-y-3">
            <Button variant="outline" onClick={() => setPosMode("pos")}>POS rápido</Button>{selectedOpsArea !== "all" ? <Button variant="outline" onClick={() => setSelectedOpsArea("all")}>Volver a todas</Button> : null}
            <Button variant="outline" onClick={() => navigate("/tables/editor")}>Editor de mesas</Button>
            <div className="space-y-1 text-sm"><p className="font-semibold">Áreas</p><button className={cn("w-full rounded border p-2 text-left", selectedOpsArea === "all" && "border-primary")} onClick={() => setSelectedOpsArea("all")}>Todas</button>{diningAreas.map((a) => <button key={a.id} className={cn("w-full rounded border p-2 text-left", selectedOpsArea === a.id && "border-primary")} onClick={() => setSelectedOpsArea(a.id)}>{a.name}</button>)}</div>
            <div className="space-y-1 text-sm"><p className="font-semibold">Estado</p><Button variant={selectedOpsFilter === "all" ? "default" : "outline"} className="w-full" onClick={() => setSelectedOpsFilter("all")}>Todas</Button><Button variant={selectedOpsFilter === "free" ? "default" : "outline"} className="w-full" onClick={() => setSelectedOpsFilter("free")}>Libres</Button><Button variant={selectedOpsFilter === "occupied" ? "default" : "outline"} className="w-full" onClick={() => setSelectedOpsFilter("occupied")}>Ocupadas</Button><Button variant={selectedOpsFilter === "kitchen" ? "default" : "outline"} className="w-full" onClick={() => setSelectedOpsFilter("kitchen")}>En cocina</Button></div>
          </Card>

          <Card className="p-3 overflow-auto">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-bold">Mesas</h2><div className="flex gap-2 text-xs"><Badge variant="secondary">Libres: {freeCount}</Badge><Badge variant="secondary">Ocupadas: {occupiedCount}</Badge><Badge variant="secondary">En cocina: {kitchenCount}</Badge></div></div>
            <div className="relative h-[calc(100dvh-170px)] overflow-auto rounded-xl border bg-slate-950">
              <div className="relative h-[1200px] w-[1800px]">
                {selectedOpsArea === "all" ? diningAreas.map((area) => {
                  const areaTables = restaurantTables.filter((t) => t.area === area.id);
                  const areaFree = areaTables.filter((t) => !sessionByTableId.get(t.id)).length;
                  const areaKitchen = areaTables.filter((t) => sessionByTableId.get(t.id)?.status === "sent_to_kitchen").length;
                  const areaOccupied = areaTables.length - areaFree;
                  return <button key={area.id} className="absolute rounded-xl border-2 p-3 text-left text-white" style={{ left: area.x ?? 0, top: area.y ?? 0, width: area.width ?? 320, height: area.height ?? 220, borderColor: area.color || "#64748b", backgroundColor: `${area.color || "#64748b"}33` }} onClick={() => setSelectedOpsArea(area.id)}><p className="font-semibold">{area.name}</p><p className="text-xs opacity-90">Libres: {areaFree}</p><p className="text-xs opacity-90">Ocupadas: {areaOccupied}</p><p className="text-xs opacity-90">En cocina: {areaKitchen}</p></button>;
                }) : opsTables.map((table) => {
                  const session = sessionByTableId.get(table.id);
                  const selected = selectedOpsTableId === table.id;
                  const stateLabel = getSessionStateLabel(session);
                  return (
                    <button key={table.id} onContextMenu={(e)=>{ e.preventDefault(); setSelectedOpsTableId(table.id); setOpsContextMenu({ open:true, x:e.clientX, y:e.clientY, tableId: table.id }); }} onPointerDown={(e)=>{ if (longPressOpsRef.current) window.clearTimeout(longPressOpsRef.current); longPressOpsRef.current = window.setTimeout(()=>setOpsContextMenu({ open:true, x:e.clientX, y:e.clientY, tableId: table.id }),2000); }} onPointerUp={()=>{ if (longPressOpsRef.current) window.clearTimeout(longPressOpsRef.current); }} onClick={() => { if (mergeMode.active) { void handleMergeWithTable(table.id); return; } setSelectedOpsTableId(table.id); if (!session) setNewSessionDialog({ open: true, tableId: table.id, guests: Math.max(2, Number(table.capacity || 2)), orderMode: "table", notes: "" }); else void openTableSession(table.id); }} className={cn("absolute border-2 shadow-md", selected && "ring-2 ring-white/70", table.shape === "round" && "rounded-full", table.shape === "square" && "rounded-md", table.shape === "rectangle" && "rounded-lg", table.shape === "booth" && "rounded-xl", table.shape === "bar" && "rounded-sm")} style={{ left: table.x, top: table.y, width: table.width, height: table.height, transform: `rotate(${table.rotation}deg)`, backgroundColor: `${table.color || "#10b981"}33`, borderColor: table.color || "#10b981" }}>
                      <div className="flex h-full w-full flex-col items-center justify-center px-1 text-center text-white">
                        <p className="max-w-full truncate text-sm font-semibold">{table.name}</p>
                        {Math.min(table.width, table.height) > 80 ? <p className="text-[11px] opacity-90">Cap. {table.capacity}</p> : null}
                        <span className="mt-1 rounded bg-black/40 px-1 text-[10px]">{stateLabel}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>

          <Card className="p-3">
            {!selectedOpsTableId ? <p className="text-sm text-muted-foreground">Selecciona una mesa para ver acciones.</p> : (() => { const table = restaurantTables.find((t) => t.id === selectedOpsTableId); const session = selectedOpsTableId ? sessionByTableId.get(selectedOpsTableId) : null; if (!table) return null; return <div className="space-y-2"><h3 className="font-semibold">{table.name}</h3><p className="text-sm text-muted-foreground">{session ? "Mesa ocupada" : "Mesa libre"}</p><Button className="w-full" onClick={() => session ? void openTableSession(table.id) : setNewSessionDialog({ open: true, tableId: table.id, guests: Math.max(2, Number(table.capacity || 2)), orderMode: "table", notes: "" })}>{session ? "Agregar productos" : "Nueva orden"}</Button><Button className="w-full" variant="outline" disabled={!session}>Enviar a cocina</Button><Button className="w-full" variant="outline" disabled={!session}>Unir mesa</Button><Button className="w-full" variant="outline" disabled={!session}>Cobrar mesa</Button></div>; })()}
          </Card>
        </div>

        {opsContextMenu.open ? <div className="fixed inset-0 z-50" onClick={() => setOpsContextMenu({ open:false, x:0, y:0, tableId:null })}><Card className="absolute w-64 p-2" style={{ left: Math.min(opsContextMenu.x, window.innerWidth - 270), top: Math.min(opsContextMenu.y, window.innerHeight - 320) }} onClick={(e)=>e.stopPropagation()}>{(() => { const table = restaurantTables.find((t) => t.id === opsContextMenu.tableId); const session = table ? sessionByTableId.get(table.id) : null; if (!table) return null; return <div className="space-y-1"><Button className="h-11 w-full justify-start" variant="ghost" onClick={() => { setSelectedOpsTableId(table.id); if (!session) setNewSessionDialog({ open:true, tableId: table.id, guests: Math.max(2, Number(table.capacity || 2)), orderMode:"table", notes:"" }); else void openTableSession(table.id); setOpsContextMenu({ open:false, x:0, y:0, tableId:null }); }}>{session ? "Ver orden" : "Nueva orden"}</Button><Button className="h-11 w-full justify-start" variant="ghost" disabled={!session} onClick={() => { setMergeMode({ active:true, sessionId: session?.id ?? null, sourceTableId: table.id }); toast.message("Selecciona una mesa libre para unirla."); setOpsContextMenu({ open:false, x:0, y:0, tableId:null }); }}>Unir mesa</Button><Button className="h-11 w-full justify-start" variant="ghost" disabled onClick={() => toast.message("Unir cuentas requiere soporte de fusión de órdenes en backend.")}>Unir cuenta</Button><Button className="h-11 w-full justify-start" variant="ghost" disabled onClick={() => toast.message("Transferir cuenta queda preparado para próxima iteración.")}>Transferir cuenta</Button><Button className="h-11 w-full justify-start" variant="ghost" onClick={() => setOpsContextMenu({ open:false, x:0, y:0, tableId:null })}>Cancelar</Button></div>; })()}</Card></div> : null}
        <Dialog open={newSessionDialog.open} onOpenChange={(open) => setNewSessionDialog((prev) => ({ ...prev, open }))}>
          <DialogContent>
            <DialogHeader><DialogTitle>Nueva orden</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Personas</Label><div className="mt-2 flex flex-wrap gap-2">{[1,2,3,4,5,6].map((n)=><Button key={n} type="button" variant={newSessionDialog.guests===n?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,guests:n}))}>{n}</Button>)}<div className="ml-2 inline-flex items-center gap-1 rounded-lg border px-2 py-1"><Button type="button" size="sm" variant="ghost" onClick={()=>setNewSessionDialog((p)=>({...p,guests:Math.max(1,p.guests-1)}))}>-</Button><span className="min-w-8 text-center font-semibold">{newSessionDialog.guests}</span><Button type="button" size="sm" variant="ghost" onClick={()=>setNewSessionDialog((p)=>({...p,guests:Math.min(99,p.guests+1)}))}>+</Button></div></div></div>{(() => { const table = restaurantTables.find((t) => t.id === newSessionDialog.tableId); const cap = Number(table?.capacity || 0); return cap > 0 && newSessionDialog.guests > cap ? <p className="text-xs text-amber-500">Sobre capacidad sugerida de la mesa.</p> : null; })()}
              <div><Label>Modo de orden</Label><div className="mt-2 flex gap-2"><Button type="button" variant={newSessionDialog.orderMode==="table"?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,orderMode:"table"}))}>Orden completa</Button><Button type="button" variant={newSessionDialog.orderMode==="per_person"?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,orderMode:"per_person"}))}>Por persona</Button></div></div>
              <div><Label>Notas</Label><Textarea value={newSessionDialog.notes} onChange={(e)=>setNewSessionDialog((p)=>({...p,notes:e.target.value}))} /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={()=>setNewSessionDialog({ open:false, tableId:null, guests:2, orderMode:"table", notes:"" })}>Cancelar</Button><Button onClick={() => void beginSessionFromDialog()}>Iniciar orden</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] overflow-x-hidden overflow-y-hidden bg-background">
      <div className={cn("h-full min-h-0 px-2 pb-4 pt-4 lg:px-4", requiresCashOpen && "pointer-events-none select-none opacity-80")}>
        <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[60%_40%]">
          {/* Products Section */}
          <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
            {/* Table mode controls are intentionally hidden from the classic POS workspace. */}

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
                    const availability = productAvailability(product.id);
                    const blocked = availability?.resolvedPolicy === "block" && !availability.canAddOne;
                    const badgeText = blocked ? (Number(availability?.currentCartQuantity ?? 0) > 0 ? "Máximo" : "Sin stock") : availability?.status === "warning" ? "Stock bajo" : availability?.status === "allowed_without_stock" ? "Venta sin stock" : "";
                    const stockTitle = blocked ? (availability?.policySource === "category" ? "Bloqueado por política de categoría" : "No hay stock disponible para agregar más unidades") : product.name;
                    const showProductImage = shouldShowProductImage(product);
                    return (
                    <Card
                      key={product.id}
                      className={cn("relative overflow-hidden hover-lift", showProductImage ? "p-2" : "p-4", blocked ? "cursor-not-allowed border-red-500/50 opacity-60" : "cursor-pointer")}
                      onClick={() => blocked ? warnIfStockLimited(product.id) : handleProductClick(product)}
                      title={stockTitle}
                      aria-disabled={blocked}
                    >
                      {showProductImage && (
                        <div className="relative mb-2 aspect-[4/3] overflow-hidden rounded-xl bg-muted/40">
                          <img
                            src={product.imageUrl ?? ""}
                            alt={product.name}
                            loading="lazy"
                            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                            onError={() => setHiddenProductImages((previous) => ({ ...previous, [product.id]: true }))}
                          />
                          {badgeText ? <Badge variant={blocked ? "destructive" : "outline"} className="absolute right-2 top-2 bg-background/90 text-[10px] shadow-sm backdrop-blur">{badgeText}</Badge> : null}
                        </div>
                      )}
                      <div className="mb-1 flex items-start justify-between gap-2">
                        <h3 className="font-semibold text-sm line-clamp-2">{product.name}</h3>
                        {!showProductImage && badgeText ? <Badge variant={blocked ? "destructive" : "outline"} className="shrink-0 text-[10px]">{badgeText}</Badge> : null}
                      </div>
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

                    {shouldShowQuickSalesButton ? (
                      <TooltipProvider delayDuration={120}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              title={quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"}
                              aria-label={quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"}
                              className="h-11 w-11 rounded-xl border-emerald-500/60 text-emerald-600 dark:text-emerald-300"
                              onClick={quickSalesMode === "last_sale" ? handleLastSaleQuickAction : openRecentSalesActions}
                              disabled={isQuickSaleProcessing}
                            >
                              {quickSalesMode === "last_sale" ? (
                                <PrinterCheck className="h-5 w-5" />
                              ) : (
                                <History className="h-5 w-5" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"}</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : null}
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
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Popover open={isOrderTypeSelectorOpen} onOpenChange={setIsOrderTypeSelectorOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant={selectedServiceType && isValidHexColor(selectedServiceType.colorHex) ? "outline" : "default"}
                      aria-label="Seleccionar tipo de pedido"
                      className="relative min-h-16 justify-center rounded-xl px-4 text-center"
                      style={selectedServiceType && isValidHexColor(selectedServiceType.colorHex) ? { backgroundColor: selectedServiceType.colorHex ?? undefined, color: getReadableTextColor(selectedServiceType.colorHex), borderColor: selectedServiceType.colorHex ?? undefined } : undefined}
                    >
                      <span className="flex min-w-0 flex-col leading-tight">
                        <span className="text-[10px] font-medium uppercase tracking-[1px] opacity-70">Tipo de Pedido</span>
                        <span className="truncate text-base font-bold">{selectedServiceType?.label ?? "Sin tipo"}</span>
                      </span>
                      <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 opacity-80" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent align="start" className="z-50 w-[min(24rem,calc(100vw-2rem))] p-3">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">Elige Tipo de Pedido</div>
                    <div className="grid grid-cols-2 gap-2" role="listbox" aria-label="Tipos de pedido activos">
                      {serviceTypes.map((type) => {
                        const selected = type.key === serviceType;
                        const hasColor = isValidHexColor(type.colorHex);
                        const style = hasColor ? { backgroundColor: type.colorHex ?? undefined, color: getReadableTextColor(type.colorHex), borderColor: type.colorHex ?? undefined } : undefined;
                        return (
                          <Button
                            key={type.key}
                            type="button"
                            variant={selected ? "default" : "outline"}
                            className={cn("min-h-14 whitespace-normal rounded-xl px-3 text-sm font-bold", selected && "ring-2 ring-primary/60 ring-offset-2 ring-offset-background")}
                            style={style}
                            role="option"
                            aria-selected={selected}
                            onClick={() => {
                              setServiceType(type.key);
                              setIsOrderTypeSelectorOpen(false);
                            }}
                          >
                            {type.label}
                          </Button>
                        );
                      })}
                    </div>
                  </PopoverContent>
                </Popover>

                <Button
                  type="button"
                  variant="outline"
                  aria-label="Seleccionar cliente"
                  className="relative min-h-16 justify-center rounded-xl px-4 text-center"
                  onClick={handleOpenCustomerDte}
                >
                  <span className="flex min-w-0 flex-col leading-tight">
                    <span className="text-[10px] font-medium uppercase tracking-[1px] text-muted-foreground">Cliente</span>
                    <span className="truncate text-base font-bold">{selectedCustomer ? selectedCustomer.fullName : "Consumidor final"}</span>
                  </span>
                </Button>
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
                <div className="space-y-2">
                  {cart.map((item) => (
                    <Card key={item.id} className="p-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <h4 className="whitespace-normal break-words text-sm font-semibold leading-snug">{item.name}</h4>
                            {item.isCustom && <Badge variant="secondary" className="text-[10px] uppercase leading-none">Manual</Badge>}
                          </div>
                          {item.originalBasePrice != null && item.originalBasePrice !== item.basePrice && (
                            <p className="text-xs text-muted-foreground">
                              <span className="line-through mr-1">{formatMoney(item.originalBasePrice)}</span>
                              <span className="font-medium text-secondary">Oferta aplicada</span>
                            </p>
                          )}
                          {item.appliedSpecialPriceRuleName && (
                            <p className="text-[11px] text-secondary/90">{item.appliedSpecialPriceRuleName}</p>
                          )}
                          {!item.appliedSpecialPriceRuleName && item.originalBasePrice != null && item.originalBasePrice !== item.basePrice && (
                            <p className="text-[11px] text-secondary/90">OFERTA</p>
                          )}
                          {item.unitPriceOverride != null && (
                            <Badge variant="outline" className="mt-1 border-amber-500/60 text-amber-400">Precio ajustado</Badge>
                          )}
                          {item.modifiers.length > 0 && (
                            <div className="mt-1 whitespace-normal break-words text-[11px] leading-snug text-secondary">
                              {item.modifiers.map((mod) => mod.name).join(", ")}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="flex items-center rounded-lg border bg-muted/20">
                            <Button variant="ghost" size="icon" onClick={() => updateQuantity(item.id, -1)} className="h-10 w-10 rounded-none">
                              <Minus className="h-4 w-4" />
                            </Button>
                            <span className="w-7 text-center text-sm font-semibold">{item.quantity}</span>
                            <Button variant="ghost" size="icon" onClick={() => updateQuantity(item.id, 1)} className="h-10 w-10 rounded-none" disabled={!canAddProductByStock(item.productId)} title={!canAddProductByStock(item.productId) ? "No hay más stock disponible" : "Agregar unidad"} aria-label={!canAddProductByStock(item.productId) ? "No hay más stock disponible" : "Agregar unidad"}>
                              <Plus className="h-4 w-4" />
                            </Button>
                          </div>
                          <span className="w-20 text-right text-sm font-bold">{formatMoney(getItemUnitTotal(item) * item.quantity)}</span>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-10 w-10" title="Acciones de línea">
                                <Settings2 className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleEditLineModifiers(item.id)}>
                                Modificadores
                              </DropdownMenuItem>
                              {!item.isCustom && (
                                <DropdownMenuItem onClick={() => openItemPriceEditor(item.id)}>
                                  Precio
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => removeItem(item.id)}
                                disabled={Boolean(activeOrder?.isPending && (activeOrder.sendToKitchen || ["preparing", "ready", "delivered"].includes(String(activeOrder.status || ""))))}
                              >
                                Eliminar
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
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

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  className="h-14 w-14 p-0"
                  onClick={() => void handleQuickPrintTicket()}
                  title="Imprimir ticket"
                  aria-label="Imprimir ticket"
                >
                  <Printer className="h-5 w-5" />
                </Button>
                <Button
                  variant="secondary"
                  className="h-14 w-14 p-0"
                  onClick={() => {
                    const isCurrentOrderEmpty = cart.length === 0;
                    if (isCurrentOrderEmpty) {
                      navigate("/open-orders");
                      return;
                    }
                    void handleSendOrderToPending();
                  }}
                  disabled={isSendingToPending}
                  title={cart.length === 0 ? "Órdenes guardadas" : "Guardar orden"}
                  aria-label={cart.length === 0 ? "Órdenes guardadas" : "Guardar orden"}
                >
                  <Save className="h-5 w-5" />
                </Button>
                <Button
                  variant="default"
                  className="h-14 flex-1 text-base font-bold"
                  size="lg"
                  disabled={cart.length === 0 || isProcessingPayment || requiresCashOpen}
                  onClick={handleCheckout}
                >
                  <span className="flex flex-col leading-tight">
                    <span className="text-base font-semibold">Cobrar</span>
                    <span className="text-sm font-medium opacity-90">{formatMoney(total)}</span>
                  </span>
                </Button>
                <Button
                  variant="outline"
                  className="h-14 w-14 p-0"
                  onClick={() => {
                    setCart([]);
                    setSelectedDiscount(null);
                    clearPersistedDraft();
                  }}
                  title="Cancelar orden"
                >
                  <XCircle className="h-5 w-5" />
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
            posDebug("[discount-debug] modal_open", {
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
                            posDebug("[discount-debug] manual_discount_apply", {
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


      <Dialog open={isRecentSalesOpen} onOpenChange={setIsRecentSalesOpen}>
        <DialogContent className="flex max-h-[88dvh] w-[min(94vw,760px)] max-w-3xl flex-col overflow-hidden border-emerald-500/50 bg-zinc-950 text-zinc-50 p-0">
          <DialogHeader className="border-b border-emerald-500/30 px-5 py-4">
            <DialogTitle className="flex items-center gap-2 text-emerald-300"><ReceiptText className="h-5 w-5" /> Ventas recientes</DialogTitle>
            <DialogDescription>Acciones rápidas para imprimir ticket{dteEnabled ? " o enviar DTE" : ""} sin entrar a Reportes. {quickSalesHistoryScope === "current_shift" ? "Mostrando última apertura de caja." : quickSalesHistoryWindowMinutes === 1440 ? "Mostrando ventas de hoy." : `Mostrando últimos ${quickSalesHistoryWindowMinutes} minutos.`}</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {recentSalesLoading ? (
              <div className="py-8 text-center text-sm text-zinc-400">Cargando ventas recientes...</div>
            ) : recentSalesError ? (
              <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">{recentSalesError}</div>
            ) : recentSales.length === 0 ? (
              <div className="py-8 text-center text-sm text-zinc-400">No hay ventas recientes para mostrar.</div>
            ) : (
              <div className="space-y-3">
                {recentSales.map((sale) => (
                  <div key={`${sale.id}-${sale.paymentId}`} className="rounded-xl border border-emerald-500/25 bg-zinc-900/80 p-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-emerald-200">{sale.orderNumber}</span>
                          <Badge variant="outline" className="border-emerald-500/40 text-emerald-200">{sale.status}</Badge>
                          <span className="text-sm font-semibold">{formatMoney(sale.total)}</span>
                        </div>
                        <div className="text-xs text-zinc-400">{formatDateTimeSV(sale.createdAt)} · {sale.customerName} · {sale.paymentMethod}</div>
                        {dteEnabled ? <div className="truncate text-xs text-zinc-500">DTE: {sale.controlNumber || "No disponible"}</div> : null}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="border-emerald-500/50" onClick={() => void handleRecentSalePrint(sale)} disabled={recentSalesPrintingId === sale.paymentId}>
                          <Printer className="mr-1 h-4 w-4" /> {recentSalesPrintingId === sale.paymentId ? "Imprimiendo..." : "Ticket"}
                        </Button>
                        {dteEnabled ? (
                          <Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-500" onClick={() => void handleRecentSaleSendDte(sale)} disabled={recentSalesSendingId === sale.id || !sale.canSendDte}>
                            <Send className="mr-1 h-4 w-4" /> {recentSalesSendingId === sale.id ? "Enviando..." : "Enviar DTE"}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
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
        <DialogContent className="flex max-h-[92dvh] w-[min(94vw,720px)] max-w-2xl flex-col overflow-hidden p-0">
          <DialogHeader className="shrink-0 border-b px-6 py-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <DialogTitle>Transacciones de Caja</DialogTitle>
                <DialogDescription>Control de sesión, pagos y cierre de caja.</DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
            <div className="rounded-md border p-3 text-sm">
              <div className="font-semibold">Estado: {cashSnapshot.open ? "Caja Abierta" : "Caja Cerrada"}</div>
              {canViewSensitiveCash && cashSnapshot.open && cashSnapshot.summary && (
                <div className="mt-2 grid grid-cols-1 gap-2 text-muted-foreground sm:grid-cols-2">
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
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
              <div className="space-y-3 rounded-md border p-3">
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
                      <div className="flex justify-between font-bold"><span>Total contado</span><span>{formatMoney((toCents(closeBillsInput) + toCents(closeCoinsInput)) / 100)}</span></div>
                    </div>
                    <Label>Notas</Label>
                    <Textarea rows={2} className="max-h-24" value={cashNotes} onChange={(e) => setCashNotes(e.target.value)} placeholder="Opcional" />
                    {pendingOrdersCount > 0 && !allowCloseWithPendingOrders ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-300">
                        You cannot close the register because there are {pendingOrdersCount} open orders. Resolve them in Open Orders first.
                      </div>
                    ) : null}
                    {pendingOrdersCount > 0 && allowCloseWithPendingOrders ? (
                      <div className="rounded-md border border-blue-500/30 bg-blue-500/10 p-2 text-sm text-blue-700 dark:text-blue-300">
                        Hay {pendingOrdersCount} órdenes pendientes, pero el cierre con pendientes está habilitado por configuración.
                      </div>
                    ) : null}
                    <div className="sticky bottom-0 z-10 -mx-3 flex items-center gap-2 border-t bg-background/95 p-3 backdrop-blur">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("pedidosYa")}>Atrás</Button>
                      <Button variant="destructive" className="h-14 flex-1 text-base font-semibold" onClick={handleCloseCashSession} disabled={isSavingCashAction || (pendingOrdersCount > 0 && !allowCloseWithPendingOrders)}>{isSavingCashAction ? "Cerrando..." : "Confirmar cierre"}</Button>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            {canViewSensitiveCash ? (
              <div className="space-y-2 rounded-md border p-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold">Transacciones</div>
                  {lastClosedSessionId ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void downloadCashSessionTicketPdf(lastClosedSessionId)}
                    >
                      Ver ticket de cierre
                    </Button>
                  ) : null}
                </div>
                <div className="max-h-[28vh] space-y-2 overflow-y-auto pr-1">
                {cashTransactions.length === 0 ? (
                  <div className="text-muted-foreground">Sin transacciones registradas.</div>
                ) : (
                  cashTransactions.map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between rounded border px-2 py-1">
                      <div>
                        <div className="font-medium">{tx.description || tx.displayType || tx.type}</div>
                        <div className="text-xs text-muted-foreground">
                          {tx.displayType || tx.type.toUpperCase()} · {formatDateTimeSV(tx.createdAt)}
                          {tx.orderId ? ` · Pedido #${tx.orderId}` : ""}
                        </div>
                      </div>
                      <div className={tx.impactsCash ? "font-semibold text-destructive" : "font-semibold text-foreground"}>
                        {tx.impactsCash ? "-" : ""}{formatMoney(tx.amount)}
                      </div>
                    </div>
                  ))
                )}
                </div>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isOpenSessionModalOpen}
        onOpenChange={(open) => {
          if (!open && !cashSnapshot.open) return;
          if (!open) {
            cancelPendingCheckoutContinuation("modal_closed_by_user");
          }
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
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    cancelPendingCheckoutContinuation("open-session-cancel");
                    setIsOpenSessionModalOpen(false);
                  }}
                >
                  Cancelar
                </Button>
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
                  cancelPendingCheckoutContinuation("open-session-back");
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

      <Dialog open={Boolean(stockWarning)} onOpenChange={(open) => { if (!open) closeStockWarning(false); }}>
        <DialogContent className="max-w-3xl border-red-500/30 bg-background">
          <DialogHeader><DialogTitle>Stock insuficiente</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Algunos artículos no tienen suficiente stock para completar esta venta.</p>
            <div className="max-h-80 overflow-auto rounded-xl border">
              <table className="w-full min-w-[680px] text-sm">
                <thead className="bg-muted/40 text-xs uppercase text-muted-foreground"><tr><th className="px-3 py-2 text-left">Artículo</th><th className="px-3 py-2 text-right">Disponible</th><th className="px-3 py-2 text-right">Requerido</th><th className="px-3 py-2 text-right">Faltante</th><th className="px-3 py-2 text-left">Unidad</th><th className="px-3 py-2 text-left">Usado en</th></tr></thead>
                <tbody>
                  {stockWarning?.check.items.map((item) => (
                    <tr key={item.inventoryItemId} className="border-t">
                      <td className="px-3 py-2 font-medium">{item.name}</td>
                      <td className="px-3 py-2 text-right">{item.available}</td>
                      <td className="px-3 py-2 text-right">{item.required}</td>
                      <td className="px-3 py-2 text-right font-semibold text-red-400">{item.missing}</td>
                      <td className="px-3 py-2">{item.unit}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">{item.affectedProducts.map((product) => `${product.productName} x${product.quantity}${product.policySourceLabel ? ` · ${product.policySourceLabel}` : ""}`).join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => closeStockWarning(false)}>{stockWarning?.mode === "block" ? "Entendido" : "Cancelar"}</Button>
              {stockWarning?.mode === "warn" ? <Button onClick={() => closeStockWarning(true)}>Continuar de todos modos</Button> : null}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPaymentOpen} onOpenChange={(open) => { setIsPaymentOpen(open); if (!open) { setSelectedPaymentMethodCode(""); setPaymentMethodAutoSelectedFromOrderType(false); setShowCashPanel(false); setActiveTenderField(null); } }}>
        <DialogContent className="flex h-[92vh] w-[96vw] max-h-[92vh] max-w-3xl flex-col overflow-hidden p-0">
          <div className="flex min-h-0 flex-1 flex-col">
            <DialogHeader className="border-b px-4 py-3 sm:px-6">
              <DialogTitle>Cobrar pedido</DialogTitle>
              <DialogDescription>Confirma el pago y envía a cocina</DialogDescription>
            </DialogHeader>
            {checkoutDraft ? (
              <>
                <div ref={checkoutModalScrollRef} className="flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6 min-h-0">
                  <div className="rounded-xl border bg-muted/20 px-4 py-3 text-center shadow-sm">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">TOTAL A PAGAR</div>
                    <div className="mt-2 text-4xl font-extrabold leading-none text-secondary sm:text-5xl">{formatMoney(paymentTotal)}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm font-semibold">
                      <span>Detalle</span>
                      <span className="text-xs text-muted-foreground">
                        {activeOrder?.orderNumber ? `Pedido #${activeOrder.orderNumber}` : createdOrderNumber ? `Pedido #${createdOrderNumber}` : "Pedido (pendiente)"}
                      </span>
                    </div>
                    <div className="rounded-md border">
                      <div className="max-h-80 divide-y divide-border overflow-y-auto text-sm">
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

                  {selectedPaymentIsCash && showCashPanel ? (
                    <CashPaymentPanel
                      totalCents={expectedPaymentCents}
                      paymentAmount={paymentAmount}
                      tipAmount={tipAmount}
                      activeTenderField={activeTenderField}
                      changeCents={changeCents}
                      isExactPayment={isExactPayment}
                      onPaymentAmountChange={setPaymentAmount}
                      onTipAmountChange={setTipAmount}
                      onFocusTenderField={focusTenderField}
                      onApplyDenomination={applyTenderDenomination}
                      onClear={clearTenderField}
                      onBackspace={backspaceTenderField}
                      onExact={setExactTenderAmount}
                      panelRef={cashPanelRef}
                      paymentInputRef={cashAmountInputRef}
                    />
                  ) : null}
                </div>

                <div className="sticky bottom-0 z-30 shrink-0 space-y-2 border-t bg-background px-4 py-3 sm:px-6">
                  <div className="space-y-2 rounded-xl border bg-muted/20 p-2" role="group" aria-label="Métodos de pago">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                      {paymentMethodButtons.map((option) => {
                        const selected = selectedPaymentMethodCode === option.code;
                        return (
                          <Button
                            key={option.code}
                            type="button"
                            variant={selected ? "default" : "outline"}
                            className={cn("h-11 px-2 text-sm font-semibold", selected && "ring-2 ring-primary/40")}
                            style={getPaymentButtonStyle(option, selected)}
                            onClick={() => selectPaymentMethodOption(option, false)}
                          >
                            {option.label}
                          </Button>
                        );
                      })}
                    </div>
                    {!selectedPaymentMethodCode ? <p className="text-xs text-muted-foreground">Selecciona un método de pago para continuar.</p> : null}
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Button className="h-12 min-w-0 text-sm" type="button" variant="outline" onClick={handleOpenCustomerDte}>
                      <span className="min-w-0 truncate text-left">
                        Cliente: {selectedCustomer ? `${selectedCustomer.fullName}${dteEnabled ? ` (${dteDocumentType})` : ""}` : dteEnabled ? `Consumidor final (${dteDocumentType})` : "Consumidor final"}
                      </span>
                    </Button>
                    <Button className="h-12 min-w-0 text-sm" type="button" variant="outline" onClick={() => setIsSplitConfigOpen(true)}>
                      Dividir cuenta: {splitEnabled ? "Activado" : "Desactivado"}
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" className="h-12 flex-1 text-sm" onClick={() => setIsPaymentOpen(false)}>Cerrar</Button>
                    <Button className="h-12 flex-1 text-sm" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || !selectedPaymentMethodCode || (selectedPaymentIsCash && showCashPanel && paymentAmountValue <= 0) || (splitEnabled && !splitValidation.isValid)}>
                      {isProcessingPayment ? "Procesando..." : "Continuar con el pago"}
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
                  variant={selectedPaymentMethodCode === option.code ? "default" : "outline"}
                  className="h-14 text-base"
                  style={getPaymentButtonStyle(option, selectedPaymentMethodCode === option.code)}
                  onClick={() => selectPaymentMethodOption(option, false)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            {selectedPaymentIsCash ? (
              <>
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
                <div
                  className={cn(
                    "rounded-lg border p-3 text-center font-semibold",
                    isExactPayment ? "text-lg" : "text-2xl sm:text-3xl",
                  )}
                >
                  {changeCents < -1 && <span className="text-destructive">Faltan {formatMoney(Math.abs(changeCents) / 100)}</span>}
                  {isExactPayment && <span className="text-secondary">Pago exacto</span>}
                  {changeCents > 1 && <span className="text-amber-500">Cambio: {formatMoney(changeCents / 100)}</span>}
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
              </>
            ) : null}
            <div className="flex gap-2">
              <Button variant="outline" className="h-14 flex-1 text-base" onClick={() => { setIsPaymentMethodOpen(false); setIsPaymentOpen(true); }}>Volver</Button>
              <Button className="h-14 flex-1 text-base" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || (selectedPaymentIsCash && paymentAmountValue <= 0) || (splitEnabled && !splitValidation.isValid)}>
                {isProcessingPayment ? "Procesando..." : "Registrar pago"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isCustomerDteOpen} onOpenChange={setIsCustomerDteOpen}>
        <DialogContent className="w-[95vw] max-w-xl">
          <DialogHeader>
            <DialogTitle>{dteEnabled ? "Cliente / DTE" : "Cliente"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {dteEnabled ? <div className="space-y-2">
              <Label>Tipo DTE</Label>
              <div className="grid grid-cols-2 gap-2">
                <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CF" ? "default" : "outline"} onClick={() => setDteDocumentType("CF")}>CF</Button>
                <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CCF" ? "default" : "outline"} onClick={() => setDteDocumentType("CCF")}>CCF</Button>
              </div>
            </div> : null}
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
            <WhatsAppPhoneInput
              label="Número extra del cliente que se mostrará en WhatsApp"
              helpText="Este número solo se usará para el mensaje 'Número del cliente'. No reemplaza el teléfono fiscal del DTE ni el número destino de WhatsApp."
              country={whatsappClientCountry}
              onCountryChange={(nextCountry) => {
                setWhatsappClientCountry(nextCountry);
                setWhatsappClientError("");
              }}
              value={whatsappClientInput}
              onValueChange={(nextValue) => {
                setWhatsappClientError("");
                setWhatsappClientInput(nextValue);
              }}
              error={whatsappClientError}
            />
            {dteDocumentType === "CF" && selectedCustomer?.isIvaExempt ? (
              <div className="rounded-md border border-emerald-500/50 bg-emerald-500/10 p-3 text-sm">
                <p className="font-medium">Cliente exento de IVA</p>
                <p className="text-xs text-muted-foreground">El DTE se generará como venta exenta, sin IVA.</p>
              </div>
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
        <DialogContent className="flex max-h-[90vh] w-[96vw] max-w-3xl flex-col overflow-hidden rounded-2xl border-emerald-600/60 p-0">
          <DialogHeader>
            <div className="border-b px-5 py-4">
              <DialogTitle>Nuevo cliente</DialogTitle>
              <DialogDescription>Completa los datos del cliente sin salir de la venta.</DialogDescription>
            </div>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-24 pt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <Label>Tipo DTE</Label>
              <div className="flex gap-2">
                <Button type="button" variant={customerForm.clientType === "CF" ? "default" : "outline"} className="h-11 flex-1" onClick={() => void preloadCustomerFormFromDTE("CF")}>CF</Button>
                <Button type="button" variant={customerForm.clientType === "CCF" ? "default" : "outline"} className="h-11 flex-1" onClick={() => void preloadCustomerFormFromDTE("CCF")}>CCF</Button>
              </div>
            </div>
            {customerForm.clientType === "CF" ? (
              <div className="rounded-xl border border-emerald-600/50 p-3 sm:col-span-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <Label>Exento de IVA</Label>
                    <p className="text-xs text-muted-foreground">Si está activo, el DTE se generará sin IVA para este cliente.</p>
                  </div>
                  <Checkbox checked={Boolean(customerForm.isIvaExempt)} onCheckedChange={(value) => setCustomerForm((prev) => ({ ...prev, isIvaExempt: value === true }))} />
                </div>
              </div>
            ) : null}
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
              <Label>DUI</Label>
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
          </div>
          <div className="sticky bottom-0 border-t bg-background/95 px-5 py-4 backdrop-blur">
          <div className="flex gap-2">
            <Button type="button" variant="outline" className="h-12 flex-1" onClick={() => setIsCustomerCreateOpen(false)} disabled={isSavingCustomer}>
              Cancelar
            </Button>
            <Button type="button" className="h-12 flex-1" onClick={() => void handleCreateCustomerFromPOS()} disabled={isQuickCustomerSaveDisabled}>
              {isSavingCustomer ? "Guardando..." : "Guardar"}
            </Button>
          </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isKitchenPromptOpen}
        onOpenChange={(open) => {
          if (!open) return;
          if (!isSubmittingKitchenChoice) setIsKitchenPromptOpen(open);
        }}
      >
        <DialogContent
          className="w-[92vw] max-w-md rounded-2xl p-6"
          showCloseButton={false}
          onInteractOutside={(event) => event.preventDefault()}
          onEscapeKeyDown={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="text-2xl">Finalizar venta</DialogTitle>
            <DialogDescription className="text-base">
              La venta ya se guardó. Configura cocina e impresión.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {shouldShowChange(saleCompletionSummary) ? (
              <div className="rounded-xl border bg-muted/20 px-4 py-4 text-center">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">CAMBIO</p>
                <p className="mt-1 text-4xl font-extrabold text-amber-500">
                  {formatMoney(saleCompletionSummary?.changeAmount ?? 0)}
                </p>
              </div>
            ) : null}
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <span>Enviar a cocina</span>
              <Checkbox checked={postSaleKitchenChoice} onCheckedChange={(value) => setPostSaleKitchenChoice(value === true)} disabled={isSubmittingKitchenChoice} />
            </div>
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <span>Imprimir ticket</span>
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
                posDebug("[pos-finalize] omit", {
                  orderId: kitchenPromptOrderId,
                  sendToKitchen: postSaleKitchenChoice,
                  printChoice: postSalePrintChoice,
                  nextPath: "/pos",
                });
                setIsKitchenPromptOpen(false);
                finalizePaidSale();
                scheduleReload();
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
                  posDebug("[cash-close-flow] user_ack_close");
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

      <Dialog open={isExtrasOpen} onOpenChange={closeExtrasDialog}>
        <DialogContent className="flex h-[90vh] w-[94vw] max-w-6xl flex-col rounded-2xl border border-border/70 p-0">
          <DialogHeader className="border-b px-5 py-4">
            <DialogTitle className="text-2xl">Extras</DialogTitle>
            <DialogDescription className="text-base">
              {pendingProduct
                ? editingModifiersItemId
                  ? `Actualiza los modificadores de ${pendingProduct.name}.`
                  : `Selecciona extras para ${pendingProduct.name}.`
                : "Selecciona extras de pago."}
            </DialogDescription>
          </DialogHeader>

          {(() => {
            const groups = getPosModifierGroups(pendingProduct);
            const activeGroup = groups.find((group) => openModifierGroups[String(group.id)]) ?? groups[0];
            const activeGroupId = activeGroup ? String(activeGroup.id) : "";
            const activeSelectedValues = activeGroup ? (selectedModifiers[activeGroupId] ?? []) : [];
            const activeError = activeGroup ? modifierValidationErrors[activeGroupId] : undefined;
            const selectGroup = (groupId: string) => setOpenModifierGroups(Object.fromEntries(groups.map((group) => [String(group.id), String(group.id) === groupId])));
            return (
              <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 md:grid-cols-[280px_minmax(0,1fr)]">
                <aside className="min-h-0 overflow-auto border-b bg-muted/20 p-3 md:border-b-0 md:border-r">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Grupos</p>
                  <div className="space-y-2">
                    {groups.map((group) => {
                      const groupId = String(group.id);
                      const selectedCount = (selectedModifiers[groupId] ?? []).length;
                      const groupError = modifierValidationErrors[groupId];
                      const active = activeGroupId === groupId;
                      return (
                        <button
                          key={group.id}
                          type="button"
                          className={cn("w-full rounded-xl border p-3 text-left transition hover:bg-muted/50", active && "border-primary bg-primary/10", groupError && "border-destructive/70")}
                          onClick={() => selectGroup(groupId)}
                          aria-label={`Ver opciones de ${group.name}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold">{group.name}</span>
                            <Badge variant={groupError ? "destructive" : selectedCount ? "default" : "outline"}>{selectedCount}/{group.maxSelection}</Badge>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">{group.required ? "Obligatorio" : "Opcional"} · Min {group.minSelection} · Max {group.maxSelection}</p>
                          {groupError ? <p className="mt-1 text-xs text-destructive">{groupError}</p> : null}
                        </button>
                      );
                    })}
                  </div>
                </aside>

                <section className="flex min-h-0 flex-col">
                  <div className="border-b px-4 py-3">
                    <h3 className="text-lg font-semibold">{activeGroup?.name ?? "Sin extras"}</h3>
                    {activeGroup ? <p className="text-sm text-muted-foreground">{activeGroup.required ? "Obligatorio" : "Opcional"} · Seleccionado {activeSelectedValues.length} de {activeGroup.maxSelection}</p> : null}
                    {activeError ? <p className="mt-1 text-sm text-destructive">{activeError}</p> : null}
                  </div>

                  <div className="min-h-0 flex-1 overflow-auto p-4">
                    {activeGroup ? (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {activeGroup.modifiers.filter((mod) => mod.price > 0).map((mod) => {
                          const modId = String(mod.id);
                          const selected = activeSelectedValues.includes(modId);
                          const maxReached = !selected && activeSelectedValues.length >= activeGroup.maxSelection;
                          const toggle = () => {
                            if (activeGroup.maxSelection === 1) {
                              setSelectedModifiers((prev) => ({ ...prev, [activeGroupId]: selected ? [] : [modId] }));
                            } else {
                              if (maxReached) return;
                              setSelectedModifiers((prev) => ({
                                ...prev,
                                [activeGroupId]: selected ? activeSelectedValues.filter((id) => id !== modId) : [...activeSelectedValues, modId],
                              }));
                            }
                            setModifierValidationErrors((prev) => { const next = { ...prev }; delete next[activeGroupId]; return next; });
                          };
                          return (
                            <div
                              key={mod.id}
                              role="button"
                              tabIndex={maxReached ? -1 : 0}
                              className={cn("min-h-28 rounded-2xl border p-4 text-left transition hover:bg-muted/50", maxReached && "cursor-not-allowed opacity-50", selected && "border-primary bg-primary/10 ring-2 ring-primary/20")}
                              onClick={() => { if (!maxReached) toggle(); }}
                              onKeyDown={(event) => {
                                if (maxReached) return;
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  toggle();
                                }
                              }}
                              aria-disabled={maxReached}
                              aria-label={`${selected ? "Quitar" : "Agregar"} ${mod.name}`}
                            >
                              <div className="flex h-full flex-col justify-between gap-3">
                                <div>
                                  <p className="text-lg font-semibold">{mod.name}</p>
                                  <p className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</p>
                                </div>
                                <div className="flex items-center justify-between">
                                  <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{selected ? "Seleccionado" : maxReached ? "Máximo" : "Tocar para agregar"}</span>
                                  {activeGroup.maxSelection === 1 ? <RadioGroup value={selected ? modId : ""}><RadioGroupItem value={modId} /></RadioGroup> : <Checkbox checked={selected} />}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : <p className="text-sm text-muted-foreground">Este producto no tiene extras disponibles.</p>}
                  </div>
                </section>
              </div>
            );
          })()}

          <div className="border-t bg-background/95 px-5 py-4 backdrop-blur">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="text-sm">
                <p className="font-semibold">{selectedExtrasCount} extra(s) seleccionado(s)</p>
                <p className="text-muted-foreground">Total extras: {formatMoney(pendingSelectionValidation.selectedMods.reduce((sum, mod) => sum + mod.price, 0))}</p>
                {Object.values(pendingSelectionValidation.errors)[0] ? <p className="text-destructive">{Object.values(pendingSelectionValidation.errors)[0]}</p> : null}
              </div>
              <Button className="h-14 min-w-48 text-base" onClick={handleAddPendingProduct} disabled={!canAddPendingProduct} title={pendingProduct && !canAddProductByStock(pendingProduct.id) ? "No hay más stock disponible" : "Agregar"}>
                {editingModifiersItemId
                  ? selectedExtrasCount > 0
                    ? `Actualizar (${selectedExtrasCount} extras)`
                    : "Actualizar"
                  : selectedExtrasCount > 0
                    ? `Agregar (${selectedExtrasCount} extras)`
                    : "Agregar"}
              </Button>
            </div>
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
        <DialogContent className="max-w-sm" tabIndex={-1}>
          <DialogHeader>
            <DialogTitle>Código de acceso</DialogTitle>
            <DialogDescription>Ingresa el PIN de 6 dígitos para autorizar cambio de precio.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-center text-2xl tracking-[0.4em]">{Array.from({ length: 6 }).map((_, i) => (pinInput[i] ? "●" : "○")).join(" ")}</div>
            <div className="grid grid-cols-3 gap-2">
              {[1,2,3,4,5,6,7,8,9].map((n) => (
                <Button key={n} variant="outline" className="h-12" onClick={() => appendPricePinDigit(String(n))}>{n}</Button>
              ))}
              <Button variant="outline" className="h-12" onClick={() => setPinInput("")}>Limpiar</Button>
              <Button variant="outline" className="h-12" onClick={() => appendPricePinDigit("0")}>0</Button>
              <Button variant="outline" className="h-12" onClick={() => setPinInput((prev) => prev.slice(0, -1))}><Delete className="h-4 w-4" /></Button>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsPinModalOpen(false)}>Cancelar</Button>
              <Button onClick={() => void submitPricePin()} disabled={pinInput.length !== 6}>Confirmar</Button>
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
