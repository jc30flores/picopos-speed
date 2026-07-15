import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Search, Plus, Minus, ShoppingCart, Wallet, ChevronDown, ChevronUp, Delete, BadgePercent, LayoutGrid, RefreshCw, Settings2, Printer, Save, XCircle, ReceiptText, Send, PrinterCheck, History, ArrowLeft, CreditCard, DoorOpen, Eye, Link2, Loader2, MoveRight, SplitSquareHorizontal, Utensils, X, Home, Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney, moneyToFixedString, toCents, toNumber } from "@/lib/money";
import { getReadableTextColor, isValidHexColor } from "@/lib/color";
import { resolveEffectiveUnitPrice } from "@/lib/pricing";
import { formatDateTimeSV } from "@/lib/datetime";
import { calculatePosPricing } from "@/lib/posPricing";
import { SplitPanel } from "@/components/pos/SplitPanel";
import { ThermalTicketDialog } from "@/components/printing/ThermalTicketDialog";
import { SplitPart, splitEvenly, validateParts } from "@/lib/splitPayments";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  getPaymentsByOrder,
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
  getRuntimeFeatureSettings,
  getDteSettings,
  getTicketSettings,
  getRestaurantTables,
  getTableSessions,
  getTableReadySummary,
  createTableSession,
  mergeTableSessionTables,
  splitTableSessionTable,
  moveTableSessionTable,
  releaseTableSession,
  forceReleaseTableSession,
  sendTableSessionToKitchen,
  renameTableSessionGuest,
  getTableKitchenSummary,
  markTableKitchenItemReady,
  markTableKitchenItemDelivered,
  serveTableSessionReadyItems,
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
  Payment,
  TableSession,
  RestaurantTable,
  TableKitchenSessionSummary,
  TableReadySummary,
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
  tableGuestId?: number | null;
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

type TablePaymentScope = {
  kind: "table" | "guest";
  tableId: number;
  tableSessionId: number;
  tableGuestId?: number | null;
  guestNumber?: number | null;
  guestLabel?: string;
  totalCents: number;
  paidCents: number;
  remainingCents: number;
  orderItemIds: number[];
};

type TablePaymentReturnTarget = {
  tableId: number;
  session: TableSession;
  reopenBill: boolean;
} | null;

type OpenTablePaymentOptions = {
  guest?: TableSession["guests"][number];
  returnToBill?: boolean;
  order?: Order | null;
  payments?: Payment[] | null;
};

type TableBillStatusFilter = "all" | "pending" | "in_kitchen" | "completed" | "served" | "paid";

const TABLE_BILL_STATUS_OPTIONS: Array<{ value: TableBillStatusFilter; label: string }> = [
  { value: "all", label: "Todos" },
  { value: "pending", label: "Pendiente de enviar" },
  { value: "in_kitchen", label: "En cocina" },
  { value: "completed", label: "Terminados" },
  { value: "served", label: "Servidos" },
  { value: "paid", label: "Pagados" },
];

type ThermalTicketState = {
  open: boolean;
  title: string;
  subtitle: string;
  text: string;
  logoUrl: string | null;
};

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
const getOrderItemTotal = (item: Order["items"][number]) => Number(item.lineTotalFinal ?? (item.unitPriceFinal ?? item.price) * item.quantity);
const getOrderItemTotalCents = (item: Order["items"][number]) => toCents(getOrderItemTotal(item));
const getOrderItemModifiers = (item: Order["items"][number]) => Array.isArray(item.modifiers) ? item.modifiers.filter(Boolean) : [];

const getPaidExtrasLines = (item: CartItem) =>
  (item.modifiers || []).filter((modifier) => modifier.price > 0).map((modifier) => ({
    name: modifier.name,
    price: modifier.price,
  }));

const isPendingKitchenItem = (item: Order["items"][number]) => (item.kitchenStatus ?? "pending") === "pending";

const mapOrderItemToCartItem = (item: Order["items"][number]): CartItem => {
  const basePrice = Number(item.unitPriceFinal ?? item.price ?? 0);
  const modifiers = Array.isArray(item.modifiers)
    ? item.modifiers.map((name) => ({ name, price: 0 }))
    : [];
  return {
    id: `order-item-${item.id}`,
    sourceOrderItemId: item.id,
    productId: item.productId ?? null,
    name: item.productName,
    basePrice,
    originalBasePrice: item.unitPriceBeforeDiscount ?? basePrice,
    price: basePrice,
    quantity: item.quantity,
    isCustom: Boolean(item.isCustom),
    customCode: item.code,
    assignedName: item.assignedName,
    tableGuestId: item.tableGuestId ?? null,
    unitPriceOverride: item.unitPriceOverride ?? null,
    requiresKitchen: item.kitchenStatus === "pending",
    modifiers,
  };
};

const mapOrderPendingItemsToCart = (order: Order): CartItem[] => (order.items || []).filter(isPendingKitchenItem).map((item) => mapOrderItemToCartItem(item));

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
  <div ref={panelRef} className="space-y-2 rounded-xl border gp-primary-border gp-primary-soft p-3">
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
type TableConfirmDialogState =
  | { open: false; type: null; sourceTableId: null; targetTableId: null; session: null }
  | { open: true; type: "merge" | "move"; sourceTableId: number; targetTableId: number; session: null }
  | { open: true; type: "release" | "split"; sourceTableId: number; targetTableId: null; session: TableSession };
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
  const [operationMode, setOperationMode] = useState<"quick_pos" | "table_service" | "both">("quick_pos");
  const [runtimeSettingsLoaded, setRuntimeSettingsLoaded] = useState(false);
  const [allowTableMerge, setAllowTableMerge] = useState(true);
  const [allowTableTransfer, setAllowTableTransfer] = useState(true);
  const [allowSplitByGuest, setAllowSplitByGuest] = useState(true);
  const [allowSplitByItem, setAllowSplitByItem] = useState(true);
  const [posMode, setPosMode] = useState<"tables"|"pos">("pos");
  const [restaurantTables, setRestaurantTables] = useState<RestaurantTable[]>([]);
  const [tableSessions, setTableSessions] = useState<TableSession[]>([]);
  const [tableReadySummaries, setTableReadySummaries] = useState<TableReadySummary[]>([]);
  const [selectedOpsTableId, setSelectedOpsTableId] = useState<number | null>(null);
  const [newSessionDialog, setNewSessionDialog] = useState<{ open: boolean; tableId: number | null; guests: number; orderMode: "table"|"per_person"; notes: string }>({ open: false, tableId: null, guests: 2, orderMode: "per_person", notes: "" });
  const [isStartingTableSession, setIsStartingTableSession] = useState(false);
  const [mergeSetupDialog, setMergeSetupDialog] = useState<{ open: boolean; sourceTableId: number | null; targetTableId: number | null; guests: number; orderMode: "table"|"per_person"; notes: string }>({ open: false, sourceTableId: null, targetTableId: null, guests: 2, orderMode: "per_person", notes: "" });
  const [opsContextMenu, setOpsContextMenu] = useState<{ open: boolean; x: number; y: number; tableId: number | null }>({ open: false, x: 0, y: 0, tableId: null });
  const [mergeMode, setMergeMode] = useState<{ active: boolean; sessionId: number | null; sourceTableId: number | null }>({ active: false, sessionId: null, sourceTableId: null });
  const [transferMode, setTransferMode] = useState<{ active: boolean; sessionId: number | null; sourceTableId: number | null }>({ active: false, sessionId: null, sourceTableId: null });
  const [tableConfirmDialog, setTableConfirmDialog] = useState<TableConfirmDialogState>({ open: false, type: null, sourceTableId: null, targetTableId: null, session: null });
  const [tableBillDialog, setTableBillDialog] = useState<{ open: boolean; loading: boolean; tableId: number | null; session: TableSession | null; order: Order | null; payments: Payment[] }>({ open: false, loading: false, tableId: null, session: null, order: null, payments: [] });
  const [tableBillGuestFilter, setTableBillGuestFilter] = useState<string>("all");
  const [tableBillStatusFilter, setTableBillStatusFilter] = useState<TableBillStatusFilter>("all");
  const [tablePaymentScope, setTablePaymentScope] = useState<TablePaymentScope | null>(null);
  const [tablePaymentReturn, setTablePaymentReturn] = useState<TablePaymentReturnTarget>(null);
  const [isOpeningTablePayment, setIsOpeningTablePayment] = useState(false);
  const [thermalTicketWidth, setThermalTicketWidth] = useState<"58mm" | "80mm">("58mm");
  const [thermalTicket, setThermalTicket] = useState<ThermalTicketState>({ open: false, title: "", subtitle: "", text: "", logoUrl: null });
  const [tableOrderContext, setTableOrderContext] = useState<{ sessionId: number; tableLabel: string; orderMode: "table" | "per_person"; guests: TableSession["guests"]; activeGuestId: number | null; activeGuestLabel: string | null } | null>(null);
  const [guestNameDialog, setGuestNameDialog] = useState<{ open: boolean; guest: TableSession["guests"][number] | null; name: string; loading: boolean }>({ open: false, guest: null, name: "", loading: false });
  const [tableKitchenSendDialog, setTableKitchenSendDialog] = useState<{ open: boolean; pendingGuestCount: number }>({ open: false, pendingGuestCount: 0 });
  const [tableBackDialogOpen, setTableBackDialogOpen] = useState(false);
  const [forceReleaseDialog, setForceReleaseDialog] = useState<{ open: boolean; session: TableSession | null; reason: string; pin: string; requiresPin: boolean; loading: boolean }>({ open: false, session: null, reason: "", pin: "", requiresPin: false, loading: false });
  const [kitchenSummaryDialog, setKitchenSummaryDialog] = useState<{ open: boolean; loading: boolean; sessions: TableKitchenSessionSummary[] }>({ open: false, loading: false, sessions: [] });
  const [readyServeDialog, setReadyServeDialog] = useState<{ open: boolean; tableId: number | null; summary: TableReadySummary | null; loading: boolean }>({ open: false, tableId: null, summary: null, loading: false });
  const tableMapViewportRef = useRef<HTMLDivElement | null>(null);
  const tableMapUserAdjustedRef = useRef(false);
  const tableMapDragRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  const opsMenuRef = useRef<HTMLDivElement | null>(null);
  const [tableMapTransform, setTableMapTransform] = useState({ scale: 1, x: 0, y: 0 });
  const [opsMenuPosition, setOpsMenuPosition] = useState<{ left: number; top: number; maxHeight: number; width: number; isSheet: boolean }>({ left: 16, top: 16, maxHeight: 560, width: 320, isSheet: false });
  const [viewportReflowTick, setViewportReflowTick] = useState(0);
  const longPressOpsRef = useRef<number | null>(null);
  const guestLongPressTimerRef = useRef<number | null>(null);
  const guestLongPressTriggeredRef = useRef(false);
  const tablePaymentOpenRequestRef = useRef(0);
  const waiterQuickRedirectShownRef = useRef(false);
  const tableAutoSaveTimeoutRef = useRef<number | null>(null);
  const tableAutoSaveSignatureRef = useRef("");
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
  const isWaiterRole = user?.role === "waiter";
  const canCollectTablePayments = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canManageTableStructure = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier" || user?.role === "waiter");
  const canCompleteKitchenItems = Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "kitchen");
  const canUseLastSaleQuickAction = quickSalesMode === "last_sale" && Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager" || user?.role === "cashier");
  const canViewRecentSalesActions = quickSalesMode === "history" && Boolean(user?.isSuperuser || user?.role === "admin" || user?.role === "manager");
  const shouldShowQuickSalesButton = quickSalesMode !== "hidden" && (canUseLastSaleQuickAction || canViewRecentSalesActions);
  const requiresCashOpen = canManageCashOperations && !getCashSessionStatus(cashSnapshot).hasOpenCashSession;
  const openAccountsCount = cashSnapshot.pendingOpenOrdersCount ?? pendingOrdersCount;
  const cashCloseBlockedByOpenAccounts = openAccountsCount > 0 && !allowCloseWithPendingOrders;
  const cashCloseOpenAccountsMessage = `No puedes cerrar la caja porque hay ${openAccountsCount} ${openAccountsCount === 1 ? "cuenta abierta" : "cuentas abiertas"}. Resuelve o cobra esas cuentas antes de cerrar.`;
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

  const activeTableGuestNumber = tableOrderContext?.guests.find((guest) => guest.id === tableOrderContext.activeGuestId)?.seatNumber ?? null;
  const urlMode = String(searchParams.get("mode") || "").trim().toLowerCase();
  const isQuickPosRequested = urlMode === "quick";
  const isTableFlowMode = ["table_order", "table_service", "edit", "pay"].includes(urlMode) || Boolean(searchParams.get("session_id"));
  const canShowOpenOrdersChoice = Boolean(
    runtimeSettingsLoaded &&
    posMode === "pos" &&
    !tableOrderContext &&
    !isTableFlowMode &&
    !isPaymentOpen &&
    (operationMode === "quick_pos" || operationMode === "both" || !tableMapEnabled)
  );
  const tableGuestMatchesActive = useCallback((item: CartItem) => {
    if (!tableOrderContext || tableOrderContext.orderMode !== "per_person") return true;
    if (tableOrderContext.activeGuestId != null && item.tableGuestId != null) {
      return item.tableGuestId === tableOrderContext.activeGuestId;
    }
    return (item.assignedName || "") === (tableOrderContext.activeGuestLabel || "");
  }, [tableOrderContext]);
  const visibleCart = useMemo(() => tableOrderContext ? cart.filter(tableGuestMatchesActive) : cart, [cart, tableOrderContext, tableGuestMatchesActive]);
  const pricingCart = tableOrderContext ? visibleCart : cart;
  const pendingGuestKeys = useMemo(() => {
    const keys = new Set<string>();
    if (!tableOrderContext) return keys;
    cart.forEach((item) => {
      keys.add(item.tableGuestId != null ? `guest:${item.tableGuestId}` : `label:${item.assignedName || "Mesa completa"}`);
    });
    return keys;
  }, [cart, tableOrderContext]);
  const pendingGuestCount = pendingGuestKeys.size;

  const cartPricing = useMemo(
    () =>
      calculatePosPricing({
        items: pricingCart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
        products,
        serviceType,
        serviceTypes,
        selectedDiscount,
        availableDiscounts,
      }),
    [availableDiscounts, pricingCart, products, selectedDiscount, serviceType, serviceTypes]
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
    if (isWaiterRole) {
      setDteEnabled(false);
      return;
    }
    getDteSettings()
      .then((settings) => setDteEnabled(settings.haciendaEnabled))
      .catch(() => setDteEnabled(false));
  }, [isWaiterRole]);

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
    Promise.all([getRestaurantTables().catch(() => []), getTableSessions().catch(() => []), getTableReadySummary().catch(() => ({ tables: [], totalReady: 0 }))])
      .then(([tables, sessions, readySummary]) => {
        setRestaurantTables(tables);
        setTableSessions(sessions);
        setTableReadySummaries(readySummary.tables);
      })
      .catch(() => undefined);
  }, [tableMapEnabled]);

  const sessionByTableId = useMemo(() => {
    const map = new Map<number, TableSession>();
    tableSessions.forEach((session) => {
      (session.tableIds || []).forEach((tableId: number) => map.set(tableId, session));
    });
    return map;
  }, [tableSessions]);

  const refreshTableSessions = useCallback(async () => {
    const sessions = await getTableSessions();
    setTableSessions(sessions);
    return sessions;
  }, []);

  const refreshTableReadySummaries = useCallback(async () => {
    const summary = await getTableReadySummary();
    setTableReadySummaries(summary.tables);
    return summary.tables;
  }, []);

  const readySummaryByTableId = useMemo(() => {
    const map = new Map<number, TableReadySummary>();
    tableReadySummaries.forEach((summary) => {
      summary.tableIds.forEach((tableId) => map.set(tableId, summary));
      if (summary.tableId != null && !map.has(summary.tableId)) map.set(summary.tableId, summary);
    });
    return map;
  }, [tableReadySummaries]);

  const upsertTableSession = useCallback((session: TableSession) => {
    setTableSessions((previous) => {
      const exists = previous.some((row) => row.id === session.id);
      return exists ? previous.map((row) => row.id === session.id ? session : row) : [session, ...previous];
    });
  }, []);

  useEffect(() => {
    if (!tableMapEnabled || posMode !== "tables") return;
    const refreshMapState = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        await Promise.all([refreshTableSessions(), refreshTableReadySummaries()]);
      } catch (error) {
        posDebug("table.map.refresh.failed", error);
      }
    };
    const interval = window.setInterval(() => {
      void refreshMapState();
    }, 5000);
    return () => window.clearInterval(interval);
  }, [posMode, refreshTableReadySummaries, refreshTableSessions, tableMapEnabled]);

  const setContextFromTableSession = useCallback((tableId: number, session: TableSession) => {
    const table = restaurantTables.find((row) => row.id === tableId);
    const firstGuest = session.guests?.[0] ?? null;
    const joinedTables = (session.tableIds || []).map((id) => restaurantTables.find((row) => row.id === id)?.name).filter(Boolean);
    setTableOrderContext({
      sessionId: session.id,
      tableLabel: joinedTables.length > 1 ? `Grupo ${joinedTables.join(" + ")}` : table?.name ?? "Mesa",
      orderMode: session.orderMode,
      guests: session.guests ?? [],
      activeGuestId: firstGuest?.id ?? null,
      activeGuestLabel: firstGuest?.label ?? null,
    });
  }, [restaurantTables]);

  const clearGuestLongPressTimer = useCallback(() => {
    if (guestLongPressTimerRef.current) {
      window.clearTimeout(guestLongPressTimerRef.current);
      guestLongPressTimerRef.current = null;
    }
  }, []);

  useEffect(() => clearGuestLongPressTimer, [clearGuestLongPressTimer]);

  const openGuestNameDialog = useCallback((guest: TableSession["guests"][number]) => {
    clearGuestLongPressTimer();
    guestLongPressTriggeredRef.current = true;
    setGuestNameDialog({ open: true, guest, name: "", loading: false });
  }, [clearGuestLongPressTimer]);

  const syncRenamedTableGuest = useCallback((session: TableSession, guest: TableSession["guests"][number]) => {
    upsertTableSession(session);
    setTableOrderContext((previous) => {
      if (!previous || previous.sessionId !== session.id) return previous;
      const guests = previous.guests.map((row) => row.id === guest.id ? guest : row);
      return {
        ...previous,
        guests,
        activeGuestLabel: previous.activeGuestId === guest.id ? guest.label : previous.activeGuestLabel,
      };
    });
    setCart((previous) => previous.map((item) => (
      item.tableGuestId === guest.id ? { ...item, assignedName: guest.label } : item
    )));
    setActiveOrder((previous) => previous ? {
      ...previous,
      items: previous.items.map((item) => (
        item.tableGuestId === guest.id
          ? { ...item, assignedName: guest.label, guestLabel: guest.label, tableGuestLabel: guest.label }
          : item
      )),
    } : previous);
    setTableBillDialog((previous) => {
      if (!previous.session || previous.session.id !== session.id) return previous;
      return {
        ...previous,
        session,
        order: previous.order ? {
          ...previous.order,
          items: previous.order.items.map((item) => (
            item.tableGuestId === guest.id
              ? { ...item, assignedName: guest.label, guestLabel: guest.label, tableGuestLabel: guest.label }
              : item
          )),
        } : previous.order,
      };
    });
  }, [upsertTableSession]);

  const startGuestLongPress = useCallback((guest: TableSession["guests"][number], event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    clearGuestLongPressTimer();
    guestLongPressTriggeredRef.current = false;
    guestLongPressTimerRef.current = window.setTimeout(() => openGuestNameDialog(guest), 600);
  }, [clearGuestLongPressTimer, openGuestNameDialog]);

  const handleGuestContextMenu = useCallback((guest: TableSession["guests"][number], event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    openGuestNameDialog(guest);
  }, [openGuestNameDialog]);

  const selectTableGuest = useCallback((guest: TableSession["guests"][number]) => {
    if (guestLongPressTriggeredRef.current) {
      guestLongPressTriggeredRef.current = false;
      return;
    }
    setTableOrderContext((previous) => previous ? { ...previous, activeGuestId: guest.id, activeGuestLabel: guest.label } : previous);
  }, []);

  const saveGuestName = useCallback(async (name: string) => {
    if (!tableOrderContext || !guestNameDialog.guest || guestNameDialog.loading) return;
    const guest = guestNameDialog.guest;
    const trimmed = name.trim();
    if (trimmed.length > 40) {
      toast.error("El nombre debe tener máximo 40 caracteres.");
      return;
    }
    setGuestNameDialog((previous) => ({ ...previous, loading: true }));
    try {
      const result = await renameTableSessionGuest(tableOrderContext.sessionId, guest.seatNumber, trimmed);
      syncRenamedTableGuest(result.session, result.guest);
      setGuestNameDialog({ open: false, guest: null, name: "", loading: false });
      toast.success(trimmed ? "Nombre asignado." : "Nombre eliminado.");
    } catch (error) {
      setGuestNameDialog((previous) => ({ ...previous, loading: false }));
      toast.error(error instanceof Error ? error.message : "No se pudo actualizar el nombre.");
    }
  }, [guestNameDialog.guest, guestNameDialog.loading, syncRenamedTableGuest, tableOrderContext]);

  const getGuestItems = useCallback((order: Order, guest: TableSession["guests"][number]) => {
    return (order.items || []).filter((item) => {
      if (item.tableGuestId != null && guest.id != null) return item.tableGuestId === guest.id;
      return item.tableGuestSeatNumber === guest.seatNumber || item.guestNumber === guest.seatNumber;
    });
  }, []);

  const getGuestPaidCents = useCallback((payments: Payment[], guest: TableSession["guests"][number]) => {
    return payments.reduce((sum, payment) => {
      return sum + (payment.allocations || []).reduce((allocationSum, allocation) => {
        const sameGuestId = allocation.tableGuestId != null && allocation.tableGuestId === guest.id;
        const sameGuestNumber = allocation.guestNumber != null && allocation.guestNumber === guest.seatNumber;
        return sameGuestId || sameGuestNumber ? allocationSum + Number(allocation.amountCents || 0) : allocationSum;
      }, 0);
    }, 0);
  }, []);

  const buildGuestPaymentScope = useCallback((
    tableId: number,
    session: TableSession,
    order: Order,
    payments: Payment[],
    guest: TableSession["guests"][number],
  ): TablePaymentScope => {
    const guestItems = getGuestItems(order, guest);
    const totalCents = guestItems.reduce((sum, item) => sum + getOrderItemTotalCents(item), 0);
    const paidCents = getGuestPaidCents(payments, guest);
    return {
      kind: "guest",
      tableId,
      tableSessionId: session.id,
      tableGuestId: guest.id,
      guestNumber: guest.seatNumber,
      guestLabel: guest.label,
      totalCents,
      paidCents,
      remainingCents: Math.max(totalCents - paidCents, 0),
      orderItemIds: guestItems.map((item) => item.id),
    };
  }, [getGuestItems, getGuestPaidCents]);

  const buildTablePaymentScope = useCallback((
    tableId: number,
    session: TableSession,
    order: Order,
  ): TablePaymentScope => {
    const remainingCents = typeof order.remainingCents === "number" ? Math.max(order.remainingCents, 0) : toCents(order.remaining);
    return {
      kind: "table",
      tableId,
      tableSessionId: session.id,
      tableGuestId: null,
      guestNumber: null,
      guestLabel: "Cuenta completa",
      totalCents: toCents(order.totalPayable ?? order.total),
      paidCents: toCents(order.totalPaid),
      remainingCents,
      orderItemIds: (order.items || []).map((item) => item.id),
    };
  }, []);

  const openTableOrderContext = useCallback((tableId: number, session: TableSession, mode: "edit" | "pay" = "edit") => {
    upsertTableSession(session);
    setContextFromTableSession(tableId, session);
    if (session.primaryOrder) {
      setPosMode("pos");
      navigate(`/pos?pending_order_id=${session.primaryOrder}&mode=${mode}`, { state: { fromOpenOrders: true, tableSession: session, tableId } });
    }
  }, [navigate, setContextFromTableSession, upsertTableSession]);

  const openTablePayment = useCallback(async (tableId: number, session: TableSession, options?: OpenTablePaymentOptions) => {
    if (!canCollectTablePayments) {
      toast.error("Mesero no puede cobrar.");
      return;
    }
    const orderId = options?.order?.id ?? session.primaryOrder;
    if (!orderId) {
      toast.error("La mesa no tiene orden activa.");
      return;
    }
    const requestId = tablePaymentOpenRequestRef.current + 1;
    tablePaymentOpenRequestRef.current = requestId;
    const returnTarget = { tableId, session, reopenBill: Boolean(options?.returnToBill) };
    upsertTableSession(session);
    setTableOrderContext(null);
    setTableBillDialog({ open: false, loading: false, tableId: null, session: null, order: null, payments: [] });
    setTablePaymentScope(null);
    setTablePaymentReturn(returnTarget);
    setActiveOrder(null);
    setCart([]);
    setCheckoutDraft(null);
    setCreatedOrderId(null);
    setCreatedOrderNumber(null);
    setSelectedDiscount(null);
    setIsPaymentMethodOpen(false);
    setIsOpeningTablePayment(true);
    setPosMode("tables");
    setIsPaymentOpen(true);
    try {
      const [order, payments] = await Promise.all([
        options?.order ? Promise.resolve(options.order) : getOrderById(orderId),
        options?.payments ? Promise.resolve(options.payments) : getPaymentsByOrder(orderId),
      ]);
      if (tablePaymentOpenRequestRef.current !== requestId) return;
      const scope = options?.guest ? buildGuestPaymentScope(tableId, session, order, payments, options.guest) : buildTablePaymentScope(tableId, session, order);
      if (scope.remainingCents <= 0) {
        toast.info(`${scope.guestLabel || "La persona"} ya no tiene saldo pendiente.`);
        setIsPaymentOpen(false);
        setTablePaymentScope(null);
        setTablePaymentReturn(null);
        setCheckoutDraft(null);
        setActiveOrder(null);
        if (options?.returnToBill) {
          setTableBillDialog({ open: true, loading: false, tableId, session, order, payments });
        }
        return;
      }
      const sourceItems = (order.items || []).filter((item) => scope.orderItemIds.includes(item.id));
      const restoredCart = sourceItems.map((item) => mapOrderItemToCartItem(item));
      const serviceKey = order.serviceType || serviceType;
      setActiveOrder(order);
      setCreatedOrderId(order.id);
      setCreatedOrderNumber(order.orderNumber);
      setCart(restoredCart);
      setSelectedDiscount(null);
      setServiceType(serviceKey);
      setCheckoutDraft({
        items: restoredCart,
        subtotal: order.subtotalBeforeDiscounts ?? order.total,
        tax: order.taxTotal ?? 0,
        total: scope.remainingCents / 100,
        taxRate,
        serviceType: serviceKey,
        createdAt: Date.now(),
      });
      const dueCents = scope.remainingCents;
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
      const initialParts = splitEvenly(scope.remainingCents, 1);
      setParts(initialParts);
      setActivePartId(initialParts[0]?.id ?? null);
      setTablePaymentScope(scope);
      setPosMode("tables");
      setIsPaymentMethodOpen(false);
      setIsPaymentOpen(true);
    } catch (error) {
      if (tablePaymentOpenRequestRef.current === requestId) {
        setIsPaymentOpen(false);
        setTablePaymentScope(null);
        setTablePaymentReturn(null);
        setCheckoutDraft(null);
        setActiveOrder(null);
        if (options?.returnToBill && options.order) {
          setTableBillDialog({ open: true, loading: false, tableId, session, order: options.order, payments: options.payments ?? [] });
        }
      }
      toast.error(error instanceof Error ? error.message : "No se pudo abrir el cobro de mesa.");
    } finally {
      if (tablePaymentOpenRequestRef.current === requestId) {
        setIsOpeningTablePayment(false);
      }
    }
  }, [buildGuestPaymentScope, buildTablePaymentScope, canCollectTablePayments, serviceType, taxRate, upsertTableSession]);

  const openTableSession = async (tableId: number) => {
    const existing = sessionByTableId.get(tableId);
    if (existing?.primaryOrder) {
      openTableOrderContext(tableId, existing);
      return;
    }
    try {
      const created = await createTableSession({ tableIds: [tableId], guestsCount: 2, orderMode: "table" });
      openTableOrderContext(tableId, created);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo abrir mesa.");
    }
  };

  const getSessionStateLabel = (session: TableSession | undefined) => {
    if (!session) return "Libre";
    if (session.status === "sent_to_kitchen") return "En cocina";
    if (session.status === "partially_paid") return "Parcial";
    return "Ocupada";
  };

  const getTableLabel = useCallback((tableId: number | null) => restaurantTables.find((table) => table.id === tableId)?.name ?? "Mesa", [restaurantTables]);

  const handleMergeWithTable = async (targetTableId: number) => {
    if (!mergeMode.active || !mergeMode.sourceTableId || targetTableId === mergeMode.sourceTableId) return;
    const targetSession = sessionByTableId.get(targetTableId);
    const sourceSession = mergeMode.sessionId ? tableSessions.find((session) => session.id === mergeMode.sessionId) ?? null : sessionByTableId.get(mergeMode.sourceTableId) ?? null;
    if (targetSession && targetSession.id !== sourceSession?.id) { toast.error("No se puede unir una mesa ocupada con otra cuenta activa."); return; }
    if (!sourceSession) {
      const sourceCapacity = Number(restaurantTables.find((table) => table.id === mergeMode.sourceTableId)?.capacity || 1);
      const targetCapacity = Number(restaurantTables.find((table) => table.id === targetTableId)?.capacity || 1);
      setMergeSetupDialog({ open: true, sourceTableId: mergeMode.sourceTableId, targetTableId, guests: Math.max(1, sourceCapacity + targetCapacity), orderMode: "per_person", notes: "" });
      return;
    }
    setTableConfirmDialog({ open: true, type: "merge", sourceTableId: mergeMode.sourceTableId, targetTableId, session: null });
  };

  const confirmMergeWithTable = async (sourceTableId: number, targetTableId: number) => {
    const targetSession = sessionByTableId.get(targetTableId);
    const sourceSession = mergeMode.sessionId ? tableSessions.find((session) => session.id === mergeMode.sessionId) ?? null : sessionByTableId.get(sourceTableId) ?? null;
    if (targetSession && targetSession.id !== sourceSession?.id) { toast.error("No se puede unir una mesa ocupada con otra cuenta activa."); return; }
    try {
      if (sourceSession) {
        await mergeTableSessionTables(sourceSession.id, [targetTableId]);
      } else {
        await createTableSession({ tableIds: [sourceTableId, targetTableId], guestsCount: 2, orderMode: "table" });
      }
      toast.success("Mesas unidas correctamente.");
      setMergeMode({ active: false, sessionId: null, sourceTableId: null });
      await refreshTableSessions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo unir la mesa.");
    }
  };

  const confirmMergeSetup = async () => {
    if (!mergeSetupDialog.sourceTableId || !mergeSetupDialog.targetTableId || isStartingTableSession) return;
    setIsStartingTableSession(true);
    try {
      await createTableSession({
        tableIds: [mergeSetupDialog.sourceTableId, mergeSetupDialog.targetTableId],
        guestsCount: Math.max(1, mergeSetupDialog.guests),
        orderMode: mergeSetupDialog.orderMode,
        notes: mergeSetupDialog.notes || undefined,
      });
      toast.success("Mesas unidas correctamente.");
      setMergeSetupDialog({ open: false, sourceTableId: null, targetTableId: null, guests: 2, orderMode: "per_person", notes: "" });
      setMergeMode({ active: false, sessionId: null, sourceTableId: null });
      await refreshTableSessions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo unir la mesa.");
    } finally {
      setIsStartingTableSession(false);
    }
  };

  const handleMoveToTable = async (targetTableId: number) => {
    if (!transferMode.active || !transferMode.sessionId) return;
    const targetSession = sessionByTableId.get(targetTableId);
    if (targetSession) {
      toast.error("Selecciona una mesa libre como destino.");
      return;
    }
    if (!transferMode.sourceTableId) return;
    setTableConfirmDialog({ open: true, type: "move", sourceTableId: transferMode.sourceTableId, targetTableId, session: null });
  };

  const confirmMoveToTable = async (sourceTableId: number, targetTableId: number) => {
    try {
      if (!transferMode.sessionId) return;
      await moveTableSessionTable(transferMode.sessionId, { targetTableId, sourceTableId });
      toast.success("Mesa movida correctamente.");
      setTransferMode({ active: false, sessionId: null, sourceTableId: null });
      setSelectedOpsTableId(targetTableId);
      await refreshTableSessions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo mover la mesa.");
    }
  };

  const openTableBill = async (tableId: number, session: TableSession) => {
    if (!session.primaryOrder) {
      toast.error("La mesa no tiene orden activa.");
      return;
    }
    setPosMode("tables");
    setTableBillGuestFilter("all");
    setTableBillStatusFilter("all");
    setTableBillDialog({ open: true, loading: true, tableId, session, order: null, payments: [] });
    try {
      const paymentsPromise = canCollectTablePayments ? getPaymentsByOrder(session.primaryOrder) : Promise.resolve([] as Payment[]);
      const [order, payments] = await Promise.all([getOrderById(session.primaryOrder), paymentsPromise]);
      setTableBillDialog({ open: true, loading: false, tableId, session, order, payments });
    } catch (error) {
      setTableBillDialog({ open: false, loading: false, tableId: null, session: null, order: null, payments: [] });
      toast.error(error instanceof Error ? error.message : "No se pudo cargar la cuenta.");
    }
  };

  const handlePaymentDialogOpenChange = (open: boolean) => {
    setIsPaymentOpen(open);
    if (open) return;
    tablePaymentOpenRequestRef.current += 1;
    setIsOpeningTablePayment(false);
    const returnTarget = tablePaymentReturn;
    setSelectedPaymentMethodCode("");
    setPaymentMethodAutoSelectedFromOrderType(false);
    setShowCashPanel(false);
    setActiveTenderField(null);
    if (tablePaymentScope) {
      setActiveOrder(null);
      setCart([]);
      setCheckoutDraft(null);
      setCreatedOrderId(null);
      setCreatedOrderNumber(null);
      setSplitEnabled(false);
      setParts([]);
      setActivePartId(null);
      setTablePaymentScope(null);
      setPosMode("tables");
      if (returnTarget?.reopenBill) {
        window.setTimeout(() => {
          void openTableBill(returnTarget.tableId, returnTarget.session);
        }, 0);
      }
    }
    setTablePaymentReturn(null);
  };

  const handleReleaseTableSession = async (session: TableSession) => {
    const sourceTableId = session.tableIds[0] ?? selectedOpsTableId;
    if (!sourceTableId) {
      toast.error("No se pudo identificar la mesa.");
      return;
    }
    let hasBalance = false;
    try {
      if (session.primaryOrder) {
        const order = await getOrderById(session.primaryOrder);
        hasBalance = Number(order.remaining ?? 0) > 0;
      }
    } catch {
      hasBalance = Number(session.totalCached ?? 0) > 0;
    }
    if (hasBalance) {
      const requiresPin = !(user?.isSuperuser || user?.role === "superadmin" || user?.role === "admin");
      setForceReleaseDialog({ open: true, session, reason: "", pin: "", requiresPin, loading: false });
      return;
    }
    setTableConfirmDialog({ open: true, type: "release", sourceTableId, targetTableId: null, session });
  };

  const confirmReleaseTableSession = async (session: TableSession) => {
    try {
      await releaseTableSession(session.id);
      toast.success("Mesa liberada.");
      await refreshTableSessions();
      setSelectedOpsTableId(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo liberar la mesa.");
    }
  };

  const confirmForceReleaseTableSession = async () => {
    const session = forceReleaseDialog.session;
    if (!session || forceReleaseDialog.loading) return;
    if (!forceReleaseDialog.reason.trim()) {
      toast.error("Ingresa un motivo.");
      return;
    }
    if (forceReleaseDialog.requiresPin && !forceReleaseDialog.pin.trim()) {
      toast.error("Ingresa PIN de admin o superadmin.");
      return;
    }
    setForceReleaseDialog((prev) => ({ ...prev, loading: true }));
    try {
      await forceReleaseTableSession(session.id, { reason: forceReleaseDialog.reason.trim(), authorizationPin: forceReleaseDialog.pin.trim() || undefined });
      toast.success("Mesa liberada y cuenta pendiente cancelada.");
      setForceReleaseDialog({ open: false, session: null, reason: "", pin: "", requiresPin: false, loading: false });
      await refreshTableSessions();
      setSelectedOpsTableId(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo liberar la mesa.");
      setForceReleaseDialog((prev) => ({ ...prev, loading: false }));
    }
  };

  const handleSplitTableSession = (session: TableSession, tableId: number) => {
    setTableConfirmDialog({ open: true, type: "split", sourceTableId: tableId, targetTableId: null, session });
  };

  const confirmSplitTableSession = async (session: TableSession, tableId: number) => {
    try {
      await splitTableSessionTable(session.id, tableId);
      toast.success("Mesa separada correctamente.");
      await refreshTableSessions();
      setSelectedOpsTableId(tableId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo separar la mesa.");
    }
  };

  const beginSessionFromDialog = async () => {
    if (!newSessionDialog.tableId || isStartingTableSession) return;
    const tableId = newSessionDialog.tableId;
    const existing = sessionByTableId.get(tableId);
    if (existing?.primaryOrder) {
      setNewSessionDialog({ open: false, tableId: null, guests: 2, orderMode: "per_person", notes: "" });
      openTableOrderContext(tableId, existing);
      return;
    }
    setIsStartingTableSession(true);
    try {
      const created = await createTableSession({ tableIds: [tableId], guestsCount: Math.max(1, newSessionDialog.guests), orderMode: newSessionDialog.orderMode, notes: newSessionDialog.notes || undefined });
      setNewSessionDialog({ open: false, tableId: null, guests: 2, orderMode: "per_person", notes: "" });
      openTableOrderContext(tableId, created);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo iniciar orden de mesa.");
    } finally {
      setIsStartingTableSession(false);
    }
  };

  useEffect(() => {
    if (!opsContextMenu.open && !mergeMode.active && !transferMode.active) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpsContextMenu({ open: false, x: 0, y: 0, tableId: null });
      setMergeMode({ active: false, sessionId: null, sourceTableId: null });
      setTransferMode({ active: false, sessionId: null, sourceTableId: null });
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [opsContextMenu.open, mergeMode.active, transferMode.active]);

  const fitTableMapToViewport = useCallback((markManual = false) => {
    const viewport = tableMapViewportRef.current;
    if (!viewport || restaurantTables.length === 0) return;
    const rect = viewport.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const bounds = restaurantTables.reduce(
      (acc, table) => {
        const rotation = Math.abs(Number(table.rotation || 0) % 180);
        const rotated = rotation > 2 && rotation < 178;
        const extra = rotated ? Math.max(table.width, table.height) * 0.24 : 0;
        return {
          minX: Math.min(acc.minX, table.x - extra),
          minY: Math.min(acc.minY, table.y - extra),
          maxX: Math.max(acc.maxX, table.x + table.width + extra),
          maxY: Math.max(acc.maxY, table.y + table.height + extra),
        };
      },
      { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity }
    );
    const contentWidth = Math.max(1, bounds.maxX - bounds.minX);
    const contentHeight = Math.max(1, bounds.maxY - bounds.minY);
    const centerX = bounds.minX + contentWidth / 2;
    const centerY = bounds.minY + contentHeight / 2;
    const padding = Math.min(100, Math.max(48, Math.min(rect.width, rect.height) * 0.12));
    const usableWidth = Math.max(240, rect.width - padding * 2);
    const usableHeight = Math.max(240, rect.height - padding * 2);
    const nextScale = Math.min(1.12, Math.max(0.35, Math.min(usableWidth / contentWidth, usableHeight / contentHeight)));
    setTableMapTransform({
      scale: nextScale,
      x: rect.width / 2 - centerX * nextScale,
      y: rect.height / 2 - centerY * nextScale,
    });
    if (markManual) tableMapUserAdjustedRef.current = false;
  }, [restaurantTables]);

  useLayoutEffect(() => {
    if (!tableMapEnabled || posMode !== "tables") return;
    if (!tableMapUserAdjustedRef.current) fitTableMapToViewport();
  }, [fitTableMapToViewport, posMode, restaurantTables, tableMapEnabled, tableSessions]);

  useEffect(() => {
    if (!tableMapEnabled || posMode !== "tables" || !tableMapViewportRef.current) return;
    const observer = new ResizeObserver(() => {
      if (!tableMapUserAdjustedRef.current) fitTableMapToViewport();
    });
    observer.observe(tableMapViewportRef.current);
    return () => observer.disconnect();
  }, [fitTableMapToViewport, posMode, tableMapEnabled]);

  useEffect(() => {
    if (!opsContextMenu.open) return;
    const handleResize = () => setViewportReflowTick((tick) => tick + 1);
    window.addEventListener("resize", handleResize);
    window.addEventListener("orientationchange", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("orientationchange", handleResize);
    };
  }, [opsContextMenu.open]);

  useLayoutEffect(() => {
    if (!opsContextMenu.open) return;
    const safe = 16;
    const menuWidth = Math.min(340, Math.max(280, window.innerWidth - safe * 2));
    const isSheet = window.innerWidth < 520;
    const maxHeight = Math.max(280, window.innerHeight - safe * 2);
    if (isSheet) {
      const sheetHeight = Math.min(Math.round(window.innerHeight * 0.76), maxHeight);
      setOpsMenuPosition({
        left: Math.max(safe, Math.round((window.innerWidth - menuWidth) / 2)),
        top: Math.max(safe, window.innerHeight - sheetHeight - safe),
        maxHeight: sheetHeight,
        width: menuWidth,
        isSheet: true,
      });
      requestAnimationFrame(() => opsMenuRef.current?.focus());
      return;
    }
    const menuRect = opsMenuRef.current?.getBoundingClientRect();
    const measuredWidth = Math.min(Math.max(menuRect?.width || menuWidth, 280), menuWidth);
    const menuHeight = Math.min(menuRect?.height || 560, maxHeight);
    const preferredLeft = opsContextMenu.x + 12;
    const preferredTop = opsContextMenu.y + 8;
    const left = Math.max(safe, Math.min(preferredLeft, window.innerWidth - measuredWidth - safe));
    const top = Math.max(safe, Math.min(preferredTop, window.innerHeight - menuHeight - safe));
    setOpsMenuPosition({ left, top, maxHeight, width: measuredWidth, isSheet: false });
    requestAnimationFrame(() => opsMenuRef.current?.focus());
  }, [opsContextMenu.open, opsContextMenu.x, opsContextMenu.y, opsContextMenu.tableId, viewportReflowTick]);

  useEffect(() => {
    if (isWaiterRole) {
      setPendingOrdersCount(0);
      setIsPendingChoiceOpen(false);
      return;
    }
    const pendingOrderId = Number(searchParams.get("pending_order_id") || "0");
    const mode = String(searchParams.get("mode") || "").trim().toLowerCase();
    const cameFromPendingParams = pendingOrderId > 0 && Number.isFinite(pendingOrderId);
    const cameFromOpenOrdersNavigation = Boolean((location.state as { fromOpenOrders?: boolean } | null)?.fromOpenOrders);
    const shouldSuppressPendingChoice = cameFromPendingParams || mode === "edit" || mode === "pay" || cameFromOpenOrdersNavigation;
    getPendingOrders({ branchId: selectedBranchId || undefined })
      .then((res) => {
        setPendingOrdersCount(res.count);
        if (canShowOpenOrdersChoice && !shouldSuppressPendingChoice) {
          setIsPendingChoiceOpen(res.count > 0);
        } else {
          setIsPendingChoiceOpen(false);
        }
      })
      .catch(() => {
        setPendingOrdersCount(0);
      });
  }, [canShowOpenOrdersChoice, isWaiterRole, location.state, searchParams, selectedBranchId]);

  useEffect(() => {
    const state = location.state as { tableSession?: TableSession; tableId?: number } | null;
    if (!state?.tableSession || !state.tableId) return;
    setContextFromTableSession(state.tableId, state.tableSession);
  }, [location.state, restaurantTables, setContextFromTableSession]);

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
        const navState = location.state as { tableSession?: TableSession; tableId?: number } | null;
        const isTableEditHydration = Boolean(navState?.tableSession) && mode !== "pay";
        const restoredCart = isTableEditHydration
          ? mapOrderPendingItemsToCart(order)
          : (order.items || []).map((item) => mapOrderItemToCartItem(item));
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
        setTablePaymentScope(null);
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
  }, [location.state, navigate, searchParams, serviceType, taxRate, products, serviceTypes]);

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
    if (isOpeningTablePayment || tablePaymentScope) return;
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
  }, [cart, dteDocumentType, isOpeningTablePayment, ivaExempt, posDraftStorageKey, selectedCustomerId, selectedDiscount, serviceType, tablePaymentScope, whatsappClientCountry, whatsappClientInput]);

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
    if (isOpeningTablePayment || tablePaymentScope) return;
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
  }, [isOpeningTablePayment, products, serviceType, tablePaymentScope]);

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
    if (isOpeningTablePayment || tablePaymentScope) return;
    void loadActiveDiscounts();
  }, [isOpeningTablePayment, itemsGross, serviceType, tablePaymentScope]);

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

  const filteredProducts = useMemo(() => products.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch && product.available;
  }), [products, searchQuery, selectedCategory]);

  const cartAvailabilityItems = useMemo(() => {
    const grouped = new Map<number, number>();
    cart.forEach((item) => {
      if (item.productId) grouped.set(item.productId, (grouped.get(item.productId) ?? 0) + item.quantity);
    });
    return Array.from(grouped.entries()).map(([productId, quantity]) => ({ productId, quantity }));
  }, [cart]);
  const cartAvailabilitySignature = useMemo(
    () => cartAvailabilityItems.map((item) => `${item.productId}:${item.quantity}`).join("|"),
    [cartAvailabilityItems]
  );
  const candidateProductIds = useMemo(() => filteredProducts.map((product) => product.id), [filteredProducts]);
  const candidateProductIdsSignature = useMemo(() => candidateProductIds.join(","), [candidateProductIds]);
  const shouldCheckCartInventory = posMode === "pos" && !isPaymentOpen;

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
    if (!shouldCheckCartInventory) {
      setCartAvailability({});
      return;
    }
    if (!cartAvailabilityItems.length && !candidateProductIds.length) {
      setCartAvailability({});
      return;
    }
    const timeout = window.setTimeout(() => {
      void checkCartInventoryAvailability({ cartItems: cartAvailabilityItems, candidateProductIds })
        .then((result) => setCartAvailability(Object.fromEntries(result.items.map((item) => [item.productId, item]))))
        .catch((error) => console.error("Failed to check cart inventory", error));
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [cartAvailabilityItems, cartAvailabilitySignature, candidateProductIds, candidateProductIdsSignature, shouldCheckCartInventory]);

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
    setTablePaymentScope(null);
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
    const assignedGuestName = tableOrderContext?.orderMode === "per_person" ? tableOrderContext.activeGuestLabel ?? undefined : undefined;
    const assignedGuestId = tableOrderContext?.orderMode === "per_person" ? tableOrderContext.activeGuestId ?? null : null;

    const existingItemIndex = cart.findIndex(
      (item) =>
        item.productId === product.id &&
        (item.tableGuestId ?? null) === assignedGuestId &&
        (item.assignedName || "") === (assignedGuestName || "") &&
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
          assignedName: assignedGuestName,
          tableGuestId: assignedGuestId,
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

  const canonicalDueCents = tablePaymentScope
    ? tablePaymentScope.remainingCents
    : activeOrder
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
  const checkoutSummaryTotal = tablePaymentScope ? paymentTotal : checkoutDraftPricing?.total ?? activeOrder?.totalPayable ?? paymentTotal;
  const checkoutDiscountLines = checkoutDraftPricing?.discountLines ?? cartPricing.discountLines;
  const paymentDialogItems = useMemo(() => {
    if (!activeOrder?.items?.length) return null;
    if (!tablePaymentScope) return activeOrder.items;
    return activeOrder.items.filter((item) => tablePaymentScope.orderItemIds.includes(item.id));
  }, [activeOrder, tablePaymentScope]);
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
          tableGuestId: item.tableGuestId ?? null,
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
    setTablePaymentScope(null);
    setIsPaymentOpen(true);
  };

  const requestOpenSession = (postAction?: () => Promise<void>, resolver?: (opened: boolean) => void) => {
    if (!canManageCashOperations) {
      toast.error("El rol Mesero no puede abrir caja.");
      resolver?.(false);
      return;
    }
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
    if (!canManageCashOperations) {
      toast.error("Mesero no puede cobrar.");
      return false;
    }
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
    if (!canManageCashOperations) {
      toast.error("Mesero no puede cobrar.");
      return;
    }
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
    if (!canManageCashOperations) {
      setCashSnapshot({ open: false, hasOpenCashSession: false, canOpenCash: false, canCloseCash: false });
      setCashTransactions([]);
      setIsOpenSessionModalOpen(false);
      setIsCashGateLoading(false);
      return;
    }
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
      setPendingOrdersCount(Number(snapshot.pendingOpenOrdersCount ?? 0));
      if ((snapshot.cashAutoClose?.closed ?? 0) > 0) {
        toast.success("Caja olvidada cerrada automáticamente por horario de atención con conteo en 0.");
      }
      if ((snapshot.cashAutoClose?.skipped ?? 0) > 0) {
        toast.warning("Cierre automático omitido: existen cuentas abiertas.");
      }
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
    getRuntimeFeatureSettings().then((settings) => {
      const canUseTableMap = settings.tableMapEnabled && settings.operationMode !== "quick_pos";
      const shouldUseQuickPos = isQuickPosRequested && settings.operationMode === "both";
      const shouldForceTablesForWaiter = isWaiterRole && canUseTableMap;
      setInventoryStockPolicy(settings.inventoryStockPolicy);
      setPosProductImagesEnabled(settings.posProductImagesEnabled);
      setOperationMode(settings.operationMode);
      setAllowTableMerge(settings.allowTableMerge);
      setAllowTableTransfer(settings.allowTableTransfer);
      setAllowSplitByGuest(settings.allowSplitByGuest);
      setAllowSplitByItem(settings.allowSplitByItem);
      setTableMapEnabled(canUseTableMap);
      setPosMode(shouldForceTablesForWaiter || (canUseTableMap && !shouldUseQuickPos && settings.defaultPosEntry === "table_map") ? "tables" : "pos");
      if (isWaiterRole && isQuickPosRequested && !waiterQuickRedirectShownRef.current) {
        waiterQuickRedirectShownRef.current = true;
        toast.info("Tu usuario puede tomar órdenes en mesas, pero no cobrar en POS rápido.");
        if (canUseTableMap) {
          navigate("/pos", { replace: true });
        }
      }
      setQuickSalesMode(settings.posQuickSalesButtonMode);
      setQuickSalesHistoryScope(settings.posQuickSalesHistoryScope);
      setQuickSalesHistoryWindowMinutes(settings.posQuickSalesHistoryWindowMinutes);
      setRuntimeSettingsLoaded(true);
    }).catch(() => {
      setRuntimeSettingsLoaded(true);
    });
    if (canManageCashOperations) {
      setIsCashGateLoading(true);
      loadCashData().catch(() => undefined);
    } else {
      setCashSnapshot({ open: false, hasOpenCashSession: false, canOpenCash: false, canCloseCash: false });
      setCashTransactions([]);
      setIsOpenSessionModalOpen(false);
      setIsCashGateLoading(false);
    }
    const forceCashGate = () => {
      if (!canManageCashOperations) return;
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
  }, [canManageCashOperations, cashCloseFlowState, isQuickPosRequested, isWaiterRole, navigate]);

  const refreshPaymentMethods = useCallback(() => {
    if (!canCollectTablePayments) {
      setPaymentMethods([]);
      return;
    }
    getPaymentMethods().then((methods) => {
      setPaymentMethods(methods.filter((method) => method.isActive !== false));
    }).catch(() => undefined);
  }, [canCollectTablePayments]);

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
    if (isWaiterRole) {
      setCustomers([]);
      setDefaultConsumerCustomer(null);
      setSelectedCustomerId("");
      setDepartments([]);
      setActivities([]);
      return;
    }
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
  }, [isWaiterRole]);

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
    if (!canManageCashOperations) {
      toast.error("El rol Mesero no puede abrir caja.");
      openSessionResolverRef.current?.(false);
      return;
    }
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
            toast.success("La caja ya estaba abierta.");
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
    if (cashCloseBlockedByOpenAccounts) {
      toast.error(cashCloseOpenAccountsMessage);
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
        tableGuestId: item.tableGuestId ?? null,
      modifiers: item.modifiers.map((mod) => ({ id: mod.id, name: mod.name, price: mod.price })),
    }));

  const getTablePersistenceCart = (pendingItems: CartItem[], order: Order) => {
    if (!tableOrderContext) return pendingItems;
    const pendingSourceIds = new Set(
      pendingItems
        .map((item) => item.sourceOrderItemId)
        .filter((id): id is number => typeof id === "number" && Number.isFinite(id))
    );
    const lockedItems = (order.items || [])
      .filter((item) => !isPendingKitchenItem(item))
      .filter((item) => !pendingSourceIds.has(item.id))
      .map((item) => mapOrderItemToCartItem(item));
    return [...lockedItems, ...pendingItems];
  };

  const cartSignature = (items: CartItem[]) => JSON.stringify(
    items.map((item) => ({
      id: item.id,
      sourceOrderItemId: item.sourceOrderItemId ?? null,
      productId: item.productId,
      quantity: item.quantity,
      price: getItemBaseEffective(item),
      guestId: item.tableGuestId ?? null,
      assignedName: item.assignedName ?? "",
      modifiers: item.modifiers.map((modifier) => `${modifier.id ?? ""}:${modifier.name}:${modifier.price}`),
    }))
  );

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
        tableGuestId: item.tableGuestId ?? null,
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

  const syncExistingOpenOrder = async (order: Order, itemsOverride?: CartItem[]) => {
    const itemsToPersist = itemsOverride ?? cart;
    const persistenceCart = getTablePersistenceCart(itemsToPersist, order);
    const pricing = calculatePosPricing({
      items: persistenceCart.map((item) => ({ productId: item.productId, quantity: item.quantity, unitTotal: getItemUnitTotal(item) })),
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
      items: persistenceCart.length,
      subtotal_front: pricing.subtotal,
      discount_front: pricing.discountTotal,
      fees_front: pricing.disposableTotal,
    });
    const saved = await setOrderPending(order.id, {
      isPending: true,
      pendingState: order.paymentStatus === "paid" ? "paid_pending_delivery" : "pending_payment",
      pendingReference: pendingReferenceDraft.trim() || order.pendingReference || "",
      authorizationPin: pendingEditAuthorizationPin,
      items: buildPendingPayloadItems(persistenceCart),
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

  useEffect(() => {
    if (!tableOrderContext || !activeOrder || isSendingToPending) return;
    const signature = cartSignature(cart);
    if (signature === tableAutoSaveSignatureRef.current) return;
    if (tableAutoSaveTimeoutRef.current) window.clearTimeout(tableAutoSaveTimeoutRef.current);
    tableAutoSaveTimeoutRef.current = window.setTimeout(() => {
      void (async () => {
        try {
          const saved = await syncExistingOpenOrder(activeOrder, cart);
          const nextCart = mapOrderPendingItemsToCart(saved);
          tableAutoSaveSignatureRef.current = cartSignature(nextCart);
          setActiveOrder(saved);
          setCart(nextCart);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "No se pudo guardar el pedido de mesa.");
        }
      })();
    }, 650);
    return () => {
      if (tableAutoSaveTimeoutRef.current) window.clearTimeout(tableAutoSaveTimeoutRef.current);
    };
  }, [activeOrder, cart, isSendingToPending, tableOrderContext]);

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
            tableGuestId: item.tableGuestId ?? null,
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
        throw new Error("La orden no quedó guardada como cuenta abierta.");
      }
      toast.success("Orden guardada en cuentas abiertas");
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
      toast.error(error instanceof Error ? error.message : "No se pudo guardar la orden en cuentas abiertas.");
    } finally {
      setIsSendingToPending(false);
    }
  };

  const resetTableOrderDraft = () => {
    setCart([]);
    setCheckoutDraft(null);
    setSelectedDiscount(null);
    clearPersistedDraft();
  };

  const saveTableOrder = async ({ returnToMap }: { returnToMap: boolean }) => {
    if (!tableOrderContext || isSendingToPending) return;
    if (!activeOrder) {
      toast.error("No hay una orden de mesa activa.");
      return;
    }
    setIsSendingToPending(true);
    try {
      const saved = await syncExistingOpenOrder(activeOrder);
      setActiveOrder(saved);
      tableAutoSaveSignatureRef.current = cartSignature(mapOrderPendingItemsToCart(saved));
      toast.success("Pendientes guardados en mesa.");
      await refreshTableSessions();
      if (returnToMap) {
        resetTableOrderDraft();
        setTableOrderContext(null);
        setPosMode("tables");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar la orden de mesa.");
    } finally {
      setIsSendingToPending(false);
    }
  };

  const sendCurrentTableOrderToKitchen = async (scope: "guest" | "table") => {
    if (!tableOrderContext || !activeOrder || isSendingToPending) return;
    const guestId = tableOrderContext.orderMode === "per_person" ? tableOrderContext.activeGuestId : null;
    if (scope === "guest" && visibleCart.length === 0) {
      toast.info("No hay productos pendientes para enviar.");
      return;
    }
    setTableKitchenSendDialog({ open: false, pendingGuestCount: 0 });
    setIsSendingToPending(true);
    try {
      const savedBeforeSend = await syncExistingOpenOrder(activeOrder, cart);
      setActiveOrder(savedBeforeSend);
      const session = await sendTableSessionToKitchen(tableOrderContext.sessionId, {
        scope,
        guestId: scope === "guest" ? guestId : null,
        guestNumber: scope === "guest" ? activeTableGuestNumber : null,
      });
      upsertTableSession(session);
      const refreshed = await getOrderById(savedBeforeSend.id);
      const nextCart = mapOrderPendingItemsToCart(refreshed);
      tableAutoSaveSignatureRef.current = cartSignature(nextCart);
      setActiveOrder(refreshed);
      setCart(nextCart);
      await refreshTableSessions();
      toast.success(session.detail || (session.sentCount === 0 ? "No hay productos pendientes para enviar." : `${session.sentCount ?? 0} productos enviados a cocina.`));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo enviar a cocina.");
    } finally {
      setIsSendingToPending(false);
    }
  };

  const requestSendCurrentTableOrderToKitchen = () => {
    if (!tableOrderContext) return;
    if (visibleCart.length === 0) {
      toast.info("No hay productos pendientes para enviar.");
      return;
    }
    if (tableOrderContext.orderMode === "per_person" && pendingGuestCount > 1) {
      setTableKitchenSendDialog({ open: true, pendingGuestCount });
      return;
    }
    void sendCurrentTableOrderToKitchen(tableOrderContext.orderMode === "per_person" ? "guest" : "table");
  };

  const returnToTables = (force = false) => {
    if (!force && tableOrderContext && cart.length > 0) {
      setTableBackDialogOpen(true);
      return;
    }
    resetTableOrderDraft();
    setTableOrderContext(null);
    setPosMode("tables");
    void refreshTableSessions();
  };

  const openKitchenSummary = async () => {
    setKitchenSummaryDialog({ open: true, loading: true, sessions: [] });
    try {
      const sessions = await getTableKitchenSummary();
      setKitchenSummaryDialog({ open: true, loading: false, sessions });
    } catch (error) {
      setKitchenSummaryDialog({ open: false, loading: false, sessions: [] });
      toast.error(error instanceof Error ? error.message : "No se pudo cargar cocina.");
    }
  };

  const refreshKitchenSummary = async () => {
    const sessions = await getTableKitchenSummary();
    setKitchenSummaryDialog({ open: true, loading: false, sessions });
  };

  const updateKitchenItemStatus = async (itemId: number, target: "ready" | "delivered") => {
    try {
      if (target === "ready") await markTableKitchenItemReady(itemId);
      else await markTableKitchenItemDelivered(itemId);
      await refreshKitchenSummary();
      await refreshTableReadySummaries();
      await refreshTableSessions();
      toast.success(target === "ready" ? "Producto marcado terminado." : "Producto marcado servido.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo actualizar cocina.");
    }
  };

  const openReadyServeDialog = (tableId: number, summary: TableReadySummary) => {
    setSelectedOpsTableId(tableId);
    setOpsContextMenu({ open: false, x: 0, y: 0, tableId: null });
    setReadyServeDialog({ open: true, tableId, summary, loading: false });
  };

  const openTableActions = (tableId: number, x: number, y: number, forceOptions = false) => {
    const readySummary = readySummaryByTableId.get(tableId);
    if (!forceOptions && readySummary && readySummary.readyCount > 0) {
      openReadyServeDialog(tableId, readySummary);
      return;
    }
    setSelectedOpsTableId(tableId);
    setOpsContextMenu({ open: true, x, y, tableId });
  };

  const refreshReadyServeDialog = async (tableId: number | null, sessionId: number | null) => {
    const summaries = await refreshTableReadySummaries();
    const nextSummary = summaries.find((summary) => (sessionId != null && summary.sessionId === sessionId) || (tableId != null && summary.tableIds.includes(tableId)));
    if (nextSummary && nextSummary.readyCount > 0) {
      setReadyServeDialog((prev) => ({ ...prev, summary: nextSummary, loading: false }));
    } else {
      setReadyServeDialog({ open: false, tableId: null, summary: null, loading: false });
      toast.success("Todos los productos listos fueron servidos.");
    }
  };

  const serveReadyItem = async (itemId: number) => {
    const tableId = readyServeDialog.tableId;
    const sessionId = readyServeDialog.summary?.sessionId ?? null;
    setReadyServeDialog((prev) => ({ ...prev, loading: true }));
    try {
      await markTableKitchenItemDelivered(itemId);
      await Promise.all([refreshTableSessions(), refreshReadyServeDialog(tableId, sessionId)]);
      if (tableBillDialog.open && tableBillDialog.session && tableBillDialog.tableId) {
        void openTableBill(tableBillDialog.tableId, tableBillDialog.session);
      }
    } catch (error) {
      setReadyServeDialog((prev) => ({ ...prev, loading: false }));
      toast.error(error instanceof Error ? error.message : "No se pudo marcar como servido.");
    }
  };

  const serveAllReadyItems = async () => {
    const tableId = readyServeDialog.tableId;
    const sessionId = readyServeDialog.summary?.sessionId;
    if (!sessionId) return;
    setReadyServeDialog((prev) => ({ ...prev, loading: true }));
    try {
      await serveTableSessionReadyItems(sessionId);
      await Promise.all([refreshTableSessions(), refreshReadyServeDialog(tableId, sessionId)]);
      if (tableBillDialog.open && tableBillDialog.session && tableBillDialog.tableId) {
        void openTableBill(tableBillDialog.tableId, tableBillDialog.session);
      }
    } catch (error) {
      setReadyServeDialog((prev) => ({ ...prev, loading: false }));
      toast.error(error instanceof Error ? error.message : "No se pudieron servir los productos.");
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
    setTablePaymentScope(null);
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
    const remainingOrderAmount = tablePaymentScope ? tablePaymentScope.remainingCents / 100 : Math.max(0, toNumber(activeOrder?.remaining) || checkoutTotal);
    const splitPartAmount = splitEnabled ? (activeSplitPart?.amountCents ?? expectedPaymentCents) / 100 : null;
    const paymentAmountForApi = splitEnabled ? (splitPartAmount ?? expectedPaymentCents / 100) : tablePaymentScope ? expectedPaymentCents / 100 : remainingOrderAmount;

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
      let amountForApi = Math.min(paymentAmountForApi, latestRemaining);
      if (!splitEnabled && !tablePaymentScope && paymentMethod === "cash") {
        amountForApi = latestRemaining;
      }
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
        paymentScope: tablePaymentScope?.kind === "guest" ? "guest" : tablePaymentScope ? "custom" : "order",
        tableSessionId: tablePaymentScope?.tableSessionId ?? null,
        tableGuestId: tablePaymentScope?.tableGuestId ?? null,
        guestNumber: tablePaymentScope?.guestNumber ?? null,
        guestLabel: tablePaymentScope?.guestLabel ?? "",
        orderItemIds: tablePaymentScope?.orderItemIds ?? [],
        inventoryWarningConfirmed,
      });
      setLastPaymentId(paymentResult.id);
      setLastPaymentAutoPrint(selectedPaymentAutoPrint);
      if (shouldOpenCashDrawer(paymentMethod, selectedPaymentMethodCode)) {
        await triggerDrawerOpen({ showSuccessToast: false });
      }
      const refreshed = await getOrderById(orderId);
      setActiveOrder(refreshed);
      let nextUnpaidPart: SplitPart | undefined;
      if (splitEnabled) {
        const paidPartId = activeSplitPart?.id;
        const nextParts = parts.map((part) => (part.id === paidPartId ? { ...part, isPaid: true, locked: true } : part));
        setParts(nextParts);
        nextUnpaidPart = nextParts.find((part) => !part.isPaid);
        setActivePartId(nextUnpaidPart?.id ?? nextParts[0]?.id ?? null);
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
        if (refreshed.isPending && !tablePaymentScope) {
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
        if (tablePaymentScope) {
          const paidScope = tablePaymentScope;
          await refreshTableSessions();
          toast.success("Pago registrado. Mesa liberada.");
          setTablePaymentReturn(null);
          finalizePaidSale();
          setTableOrderContext(null);
          setTablePaymentScope(null);
          setPosMode("tables");
          if (postSalePrintChoice || selectedPaymentAutoPrint) {
            void openPaidReceiptTicket(refreshed, paymentResult, paidScope);
          }
        } else if (isKiosk) {
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
        if (tablePaymentScope && (!splitEnabled || !nextUnpaidPart)) {
          const scope = tablePaymentScope;
          toast.success(`Pago de ${scope.guestLabel || "persona"} registrado. La mesa sigue abierta.`);
          const sessions = await refreshTableSessions();
          const latestSession = sessions.find((row) => row.id === scope.tableSessionId) ?? tableSessions.find((row) => row.id === scope.tableSessionId) ?? null;
          setIsPaymentOpen(false);
          setIsPaymentMethodOpen(false);
          setCheckoutDraft(null);
          setTablePaymentScope(null);
          setTablePaymentReturn(null);
          setTableOrderContext(null);
          setPosMode("tables");
          if (latestSession) {
            await openTableBill(scope.tableId, latestSession);
          }
          return;
        }
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

  const tableOrderPrimaryLabel = "Enviar a cocina";
  const elapsedServiceLabel = (value?: string | null) => {
    if (!value) return "Ahora";
    const time = new Date(value).getTime();
    if (!Number.isFinite(time)) return "Ahora";
    const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
    if (minutes < 1) return "Ahora";
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };
  const getKitchenStatusLabel = (status?: Order["items"][number]["kitchenStatus"]) => {
    if (status === "sent") return "En cocina";
    if (status === "ready") return "Terminado / listo para servir";
    if (status === "delivered") return "Servido";
    return "Pendiente de enviar";
  };
  const getKitchenStatusTone = (status?: Order["items"][number]["kitchenStatus"]) => {
    if (status === "sent") return "border-amber-300 bg-amber-500/10 text-amber-700 dark:text-amber-200";
    if (status === "ready") return "border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200";
    if (status === "delivered") return "border-blue-300 bg-blue-500/10 text-blue-700 dark:text-blue-200";
    return "border-sky-300 bg-sky-500/10 text-sky-700 dark:text-sky-200";
  };
  const getItemAllocatedCents = (item: Order["items"][number], payments: Payment[]) =>
    payments.reduce((sum, payment) => (
      sum + (payment.allocations || []).reduce((allocationSum, allocation) => (
        allocation.orderItemId === item.id ? allocationSum + Number(allocation.amountCents || 0) : allocationSum
      ), 0)
    ), 0);
  const isTableBillItemPaid = (item: Order["items"][number], payments: Payment[]) => getItemAllocatedCents(item, payments) >= Math.max(getOrderItemTotalCents(item) - 1, 0);
  const getTableBillItemStatusLabel = (item: Order["items"][number], payments: Payment[]) => isTableBillItemPaid(item, payments) ? "Pagado" : getKitchenStatusLabel(item.kitchenStatus);
  const getTableBillItemStatusTone = (item: Order["items"][number], payments: Payment[]) => isTableBillItemPaid(item, payments)
    ? "border-violet-300 bg-violet-500/10 text-violet-700 dark:text-violet-200"
    : getKitchenStatusTone(item.kitchenStatus);
  const formatTicketQuantity = (quantity: number) => {
    const value = Number(quantity || 0);
    return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
  };
  const getTicketItemUnitPrice = (item: Order["items"][number]) => Number(item.unitPriceFinal ?? item.price ?? 0);
  const getTicketItemLineSubtotal = (item: Order["items"][number]) => Number(item.quantity || 0) * getTicketItemUnitPrice(item);
  const wrapTicketText = (value: string, chars: number, indent = "") => {
    const maxWidth = Math.max(8, chars - indent.length);
    const words = String(value || "").trim().split(/\s+/).filter(Boolean);
    const lines: string[] = [];
    let current = "";
    words.forEach((rawWord) => {
      let word = rawWord;
      while (word.length > maxWidth) {
        if (current) {
          lines.push(`${indent}${current}`);
          current = "";
        }
        lines.push(`${indent}${word.slice(0, maxWidth)}`);
        word = word.slice(maxWidth);
      }
      if (!current) {
        current = word;
      } else if (`${current} ${word}`.length <= maxWidth) {
        current = `${current} ${word}`;
      } else {
        lines.push(`${indent}${current}`);
        current = word;
      }
    });
    if (current) lines.push(`${indent}${current}`);
    return lines.length ? lines : [indent.trimEnd()];
  };
  const appendTicketItemLines = (
    lines: string[],
    item: Order["items"][number],
    chars: number,
    row: (left: string, right?: string) => string,
    payments?: Payment[],
  ) => {
    wrapTicketText(`${formatTicketQuantity(item.quantity)}x ${item.productName}`, chars).forEach((line) => lines.push(line));
    lines.push(row(`  P.Unit ${formatMoney(getTicketItemUnitPrice(item))}`, formatMoney(getTicketItemLineSubtotal(item))));
    if (payments) lines.push(`  ${getTableBillItemStatusLabel(item, payments)}`.slice(0, chars));
    getOrderItemModifiers(item).forEach((modifier) => {
      wrapTicketText(`+ ${modifier}`, chars, "  ").forEach((line) => lines.push(line));
    });
  };

  const buildTableAccountTicketText = (order: Order, session: TableSession | null, payments: Payment[], tableLabel: string, width: "58mm" | "80mm") => {
    const chars = width === "58mm" ? 32 : 42;
    const rule = "-".repeat(chars);
    const center = (value: string) => {
      const text = value.slice(0, chars);
      const pad = Math.max(0, Math.floor((chars - text.length) / 2));
      return `${" ".repeat(pad)}${text}`;
    };
    const row = (left: string, right = "") => {
      const safeRight = right.slice(0, Math.min(12, chars));
      const safeLeft = left.slice(0, Math.max(1, chars - safeRight.length - 1));
      return `${safeLeft}${" ".repeat(Math.max(1, chars - safeLeft.length - safeRight.length))}${safeRight}`;
    };
    const lines: string[] = [
      center("CUENTA DE MESA"),
      center("Ticket para revisión"),
      center("Cuenta no pagada"),
      center("NO VÁLIDO COMO COMPROBANTE FISCAL"),
      rule,
      row("Mesa", tableLabel),
      row("Personas", String(session?.guestsCount ?? 1)),
      row("Fecha", formatDateTimeSV(new Date().toISOString())),
      rule,
    ];
    const groups = new Map<string, { label: string; seat: number; items: Order["items"]; total: number; paidCents: number }>();
    (order.items || []).forEach((item) => {
      const label = item.tableGuestLabel || item.assignedName || "Mesa completa";
      const seat = item.tableGuestSeatNumber ?? item.guestNumber ?? 999;
      const key = item.tableGuestId ? `guest-${item.tableGuestId}` : label;
      const group = groups.get(key) ?? { label, seat, items: [], total: 0, paidCents: 0 };
      group.items.push(item);
      group.total += getOrderItemTotal(item);
      group.paidCents += getItemAllocatedCents(item, payments);
      groups.set(key, group);
    });
    Array.from(groups.values()).sort((a, b) => a.seat - b.seat || a.label.localeCompare(b.label)).forEach((group) => {
      lines.push(group.label.toUpperCase(), row("Subtotal", formatMoney(group.total)));
      group.items.forEach((item) => {
        appendTicketItemLines(lines, item, chars, row, payments);
      });
      lines.push(rule);
    });
    lines.push(
      row("Total", formatMoney(order.totalPayable ?? order.total)),
      row("Pagado", formatMoney(order.totalPaid)),
      row("Pendiente", formatMoney(order.remaining)),
      rule,
      center("Pendiente de pago"),
    );
    return lines.join("\n");
  };

  const buildPaidReceiptTicketText = (order: Order, payment: Payment, scope: TablePaymentScope, tableLabel: string, width: "58mm" | "80mm") => {
    const chars = width === "58mm" ? 32 : 42;
    const rule = "-".repeat(chars);
    const center = (value: string) => {
      const text = value.slice(0, chars);
      const pad = Math.max(0, Math.floor((chars - text.length) / 2));
      return `${" ".repeat(pad)}${text}`;
    };
    const row = (left: string, right = "") => {
      const safeRight = right.slice(0, Math.min(12, chars));
      const safeLeft = left.slice(0, Math.max(1, chars - safeRight.length - 1));
      return `${safeLeft}${" ".repeat(Math.max(1, chars - safeLeft.length - safeRight.length))}${safeRight}`;
    };
    const paidItems = (order.items || []).filter((item) => scope.orderItemIds.includes(item.id));
    const received = payment.cashReceived ?? payment.amount;
    const change = Math.max(received - payment.amount - (payment.tipAmount || 0), 0);
    const lines: string[] = [
      center("RECIBO DE PAGO"),
      center("Cuenta pagada"),
      rule,
      row("Mesa", tableLabel),
      row("Alcance", scope.kind === "guest" ? scope.guestLabel || "Persona" : "Cuenta completa"),
      row("Fecha", formatDateTimeSV(new Date().toISOString())),
      row("Pedido", order.orderNumber ? `#${order.orderNumber}` : `#${order.id}`),
      rule,
    ];
    paidItems.forEach((item) => {
      appendTicketItemLines(lines, item, chars, row);
    });
    lines.push(
      rule,
      row("Metodo", payment.method),
      row("Pagado", formatMoney(payment.amount)),
      payment.cashReceived != null ? row("Recibido", formatMoney(received)) : "",
      change > 0 ? row("Cambio", formatMoney(change)) : "",
      row("Total pagado", formatMoney(payment.amount)),
      rule,
      center("Gracias por su visita"),
    );
    return lines.filter(Boolean).join("\n");
  };

  const openTableLocalTicket = async () => {
    if (!tableBillDialog.order) return;
    let logoUrl: string | null = null;
    try {
      logoUrl = (await getTicketSettings()).ticketLogoUrl;
    } catch {
      logoUrl = null;
    }
    const tableLabel = restaurantTables.find((table) => table.id === tableBillDialog.tableId)?.name ?? "Mesa";
    setThermalTicket({
      open: true,
      title: "Vista previa de ticket",
      subtitle: "Cuenta local 58mm/80mm. No marca la mesa como pagada.",
      text: buildTableAccountTicketText(tableBillDialog.order, tableBillDialog.session, tableBillDialog.payments, tableLabel, thermalTicketWidth),
      logoUrl,
    });
  };

  const openPaidReceiptTicket = async (order: Order, payment: Payment, scope: TablePaymentScope) => {
    let logoUrl: string | null = null;
    try {
      logoUrl = (await getTicketSettings()).ticketLogoUrl;
    } catch {
      logoUrl = null;
    }
    const tableLabel = restaurantTables.find((table) => table.id === scope.tableId)?.name ?? "Mesa";
    setThermalTicket({
      open: true,
      title: "Vista previa de recibo",
      subtitle: "Recibo de pago 58mm/80mm. Cuenta pagada.",
      text: buildPaidReceiptTicketText(order, payment, scope, tableLabel, thermalTicketWidth),
      logoUrl,
    });
  };
  const handleTableMapWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!tableMapEnabled || posMode !== "tables") return;
    tableMapUserAdjustedRef.current = true;
    const rect = event.currentTarget.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const zoomFactor = event.deltaY > 0 ? 0.92 : 1.08;
    setTableMapTransform((current) => {
      const nextScale = Math.max(0.35, Math.min(1.8, current.scale * zoomFactor));
      const worldX = (pointerX - current.x) / current.scale;
      const worldY = (pointerY - current.y) / current.scale;
      return {
        scale: nextScale,
        x: pointerX - worldX * nextScale,
        y: pointerY - worldY * nextScale,
      };
    });
  };
  const handleTableMapPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest("button")) return;
    tableMapUserAdjustedRef.current = true;
    tableMapDragRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: tableMapTransform.x, originY: tableMapTransform.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const handleTableMapPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = tableMapDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setTableMapTransform((current) => ({ ...current, x: drag.originX + event.clientX - drag.startX, y: drag.originY + event.clientY - drag.startY }));
  };
  const handleTableMapPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (tableMapDragRef.current?.pointerId === event.pointerId) tableMapDragRef.current = null;
  };

  if (isCashGateLoading) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Verificando estado de caja...</div>
      </div>
    );
  }

  if (tableMapEnabled && posMode === "tables") {
    const opsTables = restaurantTables;
    const freeCount = restaurantTables.filter((t) => !sessionByTableId.get(t.id)).length;
    const kitchenCount = restaurantTables.filter((t) => sessionByTableId.get(t.id)?.status === "sent_to_kitchen").length;
    const occupiedCount = restaurantTables.filter((t) => !!sessionByTableId.get(t.id)).length;
    const selectionSourceLabel = getTableLabel(mergeMode.sourceTableId ?? transferMode.sourceTableId);
    const selectionMessage = mergeMode.active
      ? `Selecciona la mesa que deseas unir con ${selectionSourceLabel}`
      : transferMode.active
        ? "Selecciona la mesa destino"
        : "";
    const joinedSessions = tableSessions
      .filter((session) => session.tableIds.length > 1)
      .sort((a, b) => {
        const groupA = a.groupNumber ?? Number.MAX_SAFE_INTEGER;
        const groupB = b.groupNumber ?? Number.MAX_SAFE_INTEGER;
        const openedA = a.openedAt ? new Date(a.openedAt).getTime() : 0;
        const openedB = b.openedAt ? new Date(b.openedAt).getTime() : 0;
        return groupA - groupB || openedA - openedB || a.id - b.id;
      });
    const fallbackGroupNumbers = new Map<number, number>();
    joinedSessions.forEach((session, index) => {
      fallbackGroupNumbers.set(session.id, index + 1);
    });
    const joinedGroupNumberBySessionId = new Map(joinedSessions.map((session) => [session.id, session.groupNumber ?? fallbackGroupNumbers.get(session.id) ?? 1]));
    const groupColorFor = (groupNumber: number) => `hsl(${(groupNumber * 68) % 360} 72% 46%)`;

    return (
      <div className="h-[100dvh] overflow-hidden bg-background">
        <Button
          className="fixed left-3 top-3 z-50 h-9 gap-2 border-border bg-popover/95 px-3 text-popover-foreground shadow-lg backdrop-blur hover:bg-muted"
          variant="outline"
          onClick={() => navigate("/")}
          title="Volver al menú principal"
          aria-label="Volver al menú principal"
        >
          <Home className="h-4 w-4" />
          <span>Menú</span>
        </Button>
        {operationMode === "both" && !isWaiterRole ? (
          <Button
            className="fixed left-3 top-14 z-50 h-9 gap-2 border-border bg-popover/95 px-3 text-popover-foreground shadow-lg backdrop-blur hover:bg-muted"
            variant="outline"
            onClick={() => {
              resetTableOrderDraft();
              setTableOrderContext(null);
              setIsPendingChoiceOpen(false);
              setPosMode("pos");
              navigate("/pos?mode=quick");
            }}
            title="Abrir POS rápido"
            aria-label="Abrir POS rápido"
          >
            <ShoppingCart className="h-4 w-4" />
            <span>POS rápido</span>
          </Button>
        ) : null}

        <div
          ref={tableMapViewportRef}
          className="relative h-full touch-none overflow-hidden text-foreground"
          onWheel={handleTableMapWheel}
          onPointerDown={handleTableMapPointerDown}
          onPointerMove={handleTableMapPointerMove}
          onPointerUp={handleTableMapPointerUp}
          onPointerCancel={handleTableMapPointerUp}
          onDoubleClick={() => fitTableMapToViewport(true)}
          style={{
            background: "radial-gradient(circle at top left, color-mix(in srgb, var(--color-primary-surface) 36%, transparent), transparent 32%), linear-gradient(135deg, hsl(var(--background)), hsl(var(--muted)) 58%, hsl(var(--card)))",
          }}
        >
          <div className="pointer-events-none absolute right-3 top-3 z-30 flex max-w-[calc(100vw-5rem)] flex-wrap justify-end gap-2">
            <div className="pointer-events-auto flex flex-wrap justify-end gap-2 rounded-lg border border-border bg-popover/85 px-3 py-2 text-xs font-semibold text-popover-foreground shadow-lg backdrop-blur">
              <span>Libres: {freeCount}</span>
              <span>Ocupadas: {occupiedCount}</span>
              <button type="button" className="rounded px-1 underline-offset-2 hover:underline" onClick={() => void openKitchenSummary()}>En cocina: {kitchenCount}</button>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="pointer-events-auto h-8 gap-2 border-border bg-popover/90 px-2 text-xs text-popover-foreground shadow-lg backdrop-blur hover:bg-muted"
              onClick={() => fitTableMapToViewport(true)}
              title="Ajustar mapa a pantalla"
              aria-label="Ajustar mapa a pantalla"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Ajustar
            </Button>
          </div>
          {selectionMessage ? (
            <div className="pointer-events-none absolute left-0 right-0 top-14 z-30 flex justify-center px-3">
              <div className="pointer-events-auto flex max-w-[calc(100vw-1.5rem)] items-center gap-3 rounded-lg border border-[var(--color-primary-border)] bg-popover/90 px-4 py-3 text-sm font-medium text-popover-foreground shadow-xl backdrop-blur">
                <span>{selectionMessage}</span>
                <Button className="h-8" size="sm" variant="outline" onClick={() => { setMergeMode({ active: false, sessionId: null, sourceTableId: null }); setTransferMode({ active: false, sessionId: null, sourceTableId: null }); }}>Cancelar</Button>
              </div>
            </div>
          ) : null}
          <div
            className="absolute left-0 top-0 h-[1400px] w-[2200px] will-change-transform"
            style={{ transform: `translate3d(${tableMapTransform.x}px, ${tableMapTransform.y}px, 0) scale(${tableMapTransform.scale})`, transformOrigin: "0 0" }}
          >
            {opsTables.map((table) => {
                  const session = sessionByTableId.get(table.id);
                  const selected = selectedOpsTableId === table.id;
                  const stateLabel = getSessionStateLabel(session);
                  const isJoined = Boolean(session && session.tableIds.length > 1);
                  const groupNumber = session ? joinedGroupNumberBySessionId.get(session.id) ?? null : null;
                  const groupColor = groupNumber ? groupColorFor(groupNumber) : null;
                  const readySummary = readySummaryByTableId.get(table.id);
                  const readyCount = readySummary?.readyCount ?? 0;
                  const canSelectForMerge = mergeMode.active && table.id !== mergeMode.sourceTableId && (!session || session.id === mergeMode.sessionId);
                  const canSelectForMove = transferMode.active && table.id !== transferMode.sourceTableId && !session;
                  const tableTone = session?.status === "sent_to_kitchen"
                    ? "color-mix(in srgb, hsl(var(--warning)) 34%, hsl(var(--card)))"
                    : session?.status === "partially_paid"
                      ? "color-mix(in srgb, hsl(var(--primary)) 22%, hsl(var(--card)))"
                      : session
                        ? "color-mix(in srgb, hsl(var(--destructive)) 18%, hsl(var(--card)))"
                        : "color-mix(in srgb, var(--color-primary-surface) 76%, hsl(var(--card)))";
                  const tableBorder = canSelectForMerge || canSelectForMove
                    ? "var(--color-primary)"
                    : session?.status === "sent_to_kitchen"
                      ? "color-mix(in srgb, hsl(var(--warning)) 78%, hsl(var(--border)))"
                      : session?.status === "partially_paid"
                        ? "color-mix(in srgb, hsl(var(--primary)) 78%, hsl(var(--border)))"
                        : session
                          ? "color-mix(in srgb, hsl(var(--destructive)) 58%, hsl(var(--border)))"
                          : table.color || "var(--color-primary-border)";
                  return (
                    <button key={table.id} onContextMenu={(e)=>{ e.preventDefault(); openTableActions(table.id, e.clientX, e.clientY); }} onPointerDown={(e)=>{ if (longPressOpsRef.current) window.clearTimeout(longPressOpsRef.current); const x = e.clientX; const y = e.clientY; longPressOpsRef.current = window.setTimeout(()=>openTableActions(table.id, x, y),900); }} onPointerUp={()=>{ if (longPressOpsRef.current) window.clearTimeout(longPressOpsRef.current); }} onClick={(e) => { if (mergeMode.active) { void handleMergeWithTable(table.id); return; } if (transferMode.active) { void handleMoveToTable(table.id); return; } openTableActions(table.id, e.clientX, e.clientY); }} className={cn("absolute border-2 shadow-xl transition hover:scale-[1.02] focus:outline-none", selected && "ring-2 ring-white/80", isJoined && "border-4 shadow-2xl", (canSelectForMerge || canSelectForMove) && "ring-4 ring-[var(--color-primary)]", (mergeMode.active || transferMode.active) && !(canSelectForMerge || canSelectForMove) && "opacity-45", table.shape === "round" && "rounded-full", table.shape === "square" && "rounded-md", table.shape === "rectangle" && "rounded-lg", table.shape === "booth" && "rounded-xl", table.shape === "bar" && "rounded-sm")} style={{ left: table.x, top: table.y, width: table.width, height: table.height, transform: `rotate(${table.rotation}deg)`, backgroundColor: table.color && !session ? `${table.color}33` : tableTone, borderColor: tableBorder, boxShadow: groupColor ? `0 0 0 4px color-mix(in srgb, ${groupColor} 28%, transparent), 0 18px 36px color-mix(in srgb, ${groupColor} 22%, transparent)` : undefined }}>
                      {readyCount > 0 ? (
                        <span className="absolute -right-3 -top-3 z-10 flex h-8 min-w-8 items-center justify-center rounded-full border-2 border-background bg-red-600 px-2 text-sm font-black text-white shadow-xl">
                          {readyCount}
                        </span>
                      ) : null}
                      <div className="flex h-full w-full flex-col items-center justify-center px-1 text-center text-foreground">
                        <p className="max-w-full truncate text-sm font-semibold">{table.name}</p>
                        {Math.min(table.width, table.height) > 80 ? <p className="text-[11px] opacity-90">Cap. {table.capacity}</p> : null}
                        <span className="mt-1 rounded bg-background/70 px-1 text-[10px] shadow-sm">{stateLabel}</span>
                        {session ? <span className="mt-1 rounded bg-background/60 px-1 text-[10px] shadow-sm">{session.guestsCount} pers.</span> : null}
                        {isJoined ? <span className="mt-1 rounded px-1 text-[10px]" style={{ backgroundColor: groupColor ?? "var(--color-primary)", color: getReadableTextColor(groupColor ?? undefined) ?? "var(--color-primary-contrast)" }}>Grupo {groupNumber}</span> : null}
                      </div>
                    </button>
                  );
                })}
          </div>
        </div>

        <Dialog open={readyServeDialog.open} onOpenChange={(open) => {
          if (!open) setReadyServeDialog({ open: false, tableId: null, summary: null, loading: false });
        }}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[min(94vw,42rem)] flex-col overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b bg-background px-5 py-4">
              <DialogTitle>Pedidos listos para servir</DialogTitle>
              <DialogDescription>
                {readyServeDialog.summary?.groupLabel || readyServeDialog.summary?.tableName || "Mesa"} · {readyServeDialog.summary?.readyCount ?? 0} productos listos
              </DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              {readyServeDialog.summary?.items.length ? (
                <div className="space-y-3">
                  {readyServeDialog.summary.items.map((item) => (
                    <div key={item.id} className="rounded-lg border bg-card p-3 shadow-sm">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-red-600 text-white">Listo para servir</Badge>
                            <Badge variant="outline">x{item.quantity}</Badge>
                            <span className="text-xs font-semibold text-muted-foreground">{elapsedServiceLabel(item.kitchenReadyAt || item.kitchenCompletedAt)}</span>
                          </div>
                          <p className="break-words text-lg font-black text-foreground">{item.productName}</p>
                          <p className="text-sm font-medium text-muted-foreground">{item.guestLabel || item.tableGuestLabel || item.assignedName || "Mesa completa"}</p>
                          {item.modifiers.length ? <p className="text-xs text-muted-foreground">Modificadores: {item.modifiers.join(", ")}</p> : null}
                        </div>
                        <Button className="min-h-11 shrink-0" disabled={readyServeDialog.loading} onClick={() => void serveReadyItem(item.id)}>
                          Servir
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                  No hay pedidos listos para esta mesa.
                </div>
              )}
            </div>
            <DialogFooter className="shrink-0 flex-wrap gap-2 border-t bg-background px-5 py-4">
              <Button variant="outline" disabled={readyServeDialog.loading} onClick={() => setReadyServeDialog({ open: false, tableId: null, summary: null, loading: false })}>Cerrar</Button>
              {readyServeDialog.tableId ? (
                <Button variant="outline" disabled={readyServeDialog.loading} onClick={() => {
                  const tableId = readyServeDialog.tableId!;
                  setReadyServeDialog({ open: false, tableId: null, summary: null, loading: false });
                  openTableActions(tableId, window.innerWidth / 2, window.innerHeight / 2, true);
                }}>
                  Más opciones
                </Button>
              ) : null}
              <Button disabled={readyServeDialog.loading || !readyServeDialog.summary?.items.length} onClick={() => void serveAllReadyItems()}>
                {readyServeDialog.loading ? "Sirviendo..." : "Servir todo"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {opsContextMenu.open ? (
          <div className="fixed inset-0 z-50" onClick={() => setOpsContextMenu({ open:false, x:0, y:0, tableId:null })}>
            <Card
              ref={opsMenuRef}
              role={opsMenuPosition.isSheet ? "dialog" : "menu"}
              tabIndex={-1}
              className={cn(
                "fixed z-50 overflow-y-auto overscroll-contain rounded-xl border-border bg-popover/95 p-2 text-popover-foreground shadow-2xl outline-none backdrop-blur scrollbar-thin"
              )}
              style={{
                left: opsMenuPosition.left,
                top: opsMenuPosition.top,
                width: opsMenuPosition.width,
                maxWidth: "calc(100vw - 32px)",
                maxHeight: opsMenuPosition.isSheet ? `${opsMenuPosition.maxHeight}px` : `min(560px, ${opsMenuPosition.maxHeight}px)`,
                scrollbarWidth: "thin",
              }}
              onClick={(e)=>e.stopPropagation()}
            >
              {(() => {
                const table = restaurantTables.find((t) => t.id === opsContextMenu.tableId);
                const session = table ? sessionByTableId.get(table.id) : null;
                if (!table) return null;
                const close = () => setOpsContextMenu({ open:false, x:0, y:0, tableId:null });
                const isJoined = Boolean(session && session.tableIds.length > 1);
                const balance = Number(session?.totalCached ?? 0);
                const hasOrder = Boolean(session?.primaryOrder);
                const canCollect = hasOrder;
                const groupLabel = session?.tableIds?.map((id) => getTableLabel(id)).join(" + ") || table.name;
                const menuButton = (label: string, icon: JSX.Element, onClick: () => void, disabled = false) => (
                  <Button type="button" className="h-auto min-h-11 w-full justify-start gap-2 whitespace-normal px-3 py-2 text-left text-popover-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50" variant="ghost" disabled={disabled} onClick={(event) => { event.stopPropagation(); onClick(); }}>
                    <span className="shrink-0">{icon}</span>
                    <span className="min-w-0 break-words">{label}</span>
                  </Button>
                );
                return (
                  <div className="space-y-1">
                    <div className="sticky top-0 z-10 border-b border-border bg-popover/95 pb-2 backdrop-blur">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-semibold">{table.name}</div>
                          <div className="text-xs text-muted-foreground">{session ? `${getSessionStateLabel(session)} · ${session.guestsCount} personas` : "Libre"}</div>
                          {isJoined ? <div className="mt-1 text-xs font-medium text-popover-foreground">Grupo: {groupLabel}</div> : null}
                        </div>
                        {isJoined ? <Badge className="bg-[var(--color-primary)] text-[var(--color-primary-contrast)]">Unida</Badge> : null}
                      </div>
                      {session ? <div className="mt-1 text-xs text-muted-foreground">Total: {formatMoney(balance)}</div> : null}
                    </div>
                    {!session ? menuButton("Nueva orden", <Utensils className="h-4 w-4" />, () => { setSelectedOpsTableId(table.id); setNewSessionDialog({ open:true, tableId: table.id, guests: Math.max(2, Number(table.capacity || 2)), orderMode:"per_person", notes:"" }); close(); }) : null}
                    {!session && allowTableMerge && canManageTableStructure ? menuButton("Unir mesa", <Link2 className="h-4 w-4" />, () => { setMergeMode({ active:true, sessionId: null, sourceTableId: table.id }); toast.message(`Selecciona la mesa que deseas unir con ${table.name}`); close(); }) : null}
                    {session ? menuButton(isJoined ? "Agregar productos" : "Agregar productos", <Plus className="h-4 w-4" />, () => { void openTableSession(table.id); close(); }) : null}
                    {session ? menuButton(isJoined ? "Ver cuenta conjunta" : "Ver cuenta", <Eye className="h-4 w-4" />, () => { void openTableBill(table.id, session); close(); }) : null}
                    {session && canCollectTablePayments ? menuButton(isJoined ? "Cobrar grupo" : "Cobrar", <CreditCard className="h-4 w-4" />, () => { close(); void openTablePayment(table.id, session); }, !canCollect || isOpeningTablePayment || isPaymentOpen) : null}
                    {session && allowTableTransfer && canManageTableStructure ? menuButton(isJoined ? "Mover grupo" : "Mover mesa", <MoveRight className="h-4 w-4" />, () => { setTransferMode({ active:true, sessionId: session.id, sourceTableId: table.id }); toast.message("Selecciona la mesa destino"); close(); }) : null}
                    {session && allowTableMerge && canManageTableStructure ? menuButton("Unir mesa", <Link2 className="h-4 w-4" />, () => { setMergeMode({ active:true, sessionId: session.id, sourceTableId: table.id }); toast.message(`Selecciona la mesa que deseas unir con ${table.name}`); close(); }) : null}
                    {session && isJoined && canManageTableStructure ? menuButton("Separar mesa", <SplitSquareHorizontal className="h-4 w-4" />, () => { handleSplitTableSession(session, table.id); close(); }) : null}
                    {session && canManageTableStructure ? menuButton(isJoined ? "Liberar grupo" : "Liberar mesa", <DoorOpen className="h-4 w-4" />, () => { void handleReleaseTableSession(session); close(); }) : null}
                  </div>
                );
              })()}
            </Card>
          </div>
        ) : null}
        <AlertDialog open={tableConfirmDialog.open} onOpenChange={(open) => {
          if (!open) setTableConfirmDialog({ open: false, type: null, sourceTableId: null, targetTableId: null, session: null });
        }}>
          <AlertDialogContent className="max-w-lg">
            <AlertDialogHeader>
              <AlertDialogTitle>
                {tableConfirmDialog.open && tableConfirmDialog.type === "merge"
                  ? "Unir mesas"
                  : tableConfirmDialog.open && tableConfirmDialog.type === "move"
                    ? "Mover mesa"
                    : tableConfirmDialog.open && tableConfirmDialog.type === "split"
                      ? "Separar mesa"
                      : "Liberar mesa"}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {tableConfirmDialog.open && tableConfirmDialog.type === "merge"
                  ? `¿Deseas unir ${getTableLabel(tableConfirmDialog.sourceTableId)} con ${getTableLabel(tableConfirmDialog.targetTableId)}?`
                  : tableConfirmDialog.open && tableConfirmDialog.type === "move"
                    ? `¿Deseas mover la orden de ${getTableLabel(tableConfirmDialog.sourceTableId)} a ${getTableLabel(tableConfirmDialog.targetTableId)}?`
                    : tableConfirmDialog.open && tableConfirmDialog.type === "split"
                      ? `${getTableLabel(tableConfirmDialog.sourceTableId)} saldrá del grupo. La cuenta conjunta se mantiene en las mesas restantes.`
                      : "Esta mesa quedará disponible."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  if (!tableConfirmDialog.open) return;
                  const current = tableConfirmDialog;
                  setTableConfirmDialog({ open: false, type: null, sourceTableId: null, targetTableId: null, session: null });
                  if (current.type === "merge" && current.targetTableId) void confirmMergeWithTable(current.sourceTableId, current.targetTableId);
                  if (current.type === "move" && current.targetTableId) void confirmMoveToTable(current.sourceTableId, current.targetTableId);
                  if (current.type === "split") void confirmSplitTableSession(current.session, current.sourceTableId);
                  if (current.type === "release") void confirmReleaseTableSession(current.session);
                }}
              >
                {tableConfirmDialog.open && tableConfirmDialog.type === "merge"
                  ? "Unir mesas"
                  : tableConfirmDialog.open && tableConfirmDialog.type === "move"
                    ? "Mover"
                    : tableConfirmDialog.open && tableConfirmDialog.type === "split"
                      ? "Separar"
                      : "Liberar"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <Dialog open={mergeSetupDialog.open} onOpenChange={(open) => { if (!isStartingTableSession) setMergeSetupDialog((prev) => ({ ...prev, open })); }}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-xl flex-col overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b px-5 py-4">
              <DialogTitle>Unir mesas</DialogTitle>
              <DialogDescription>
                {mergeSetupDialog.sourceTableId && mergeSetupDialog.targetTableId
                  ? `Configura el grupo ${getTableLabel(mergeSetupDialog.sourceTableId)} + ${getTableLabel(mergeSetupDialog.targetTableId)}.`
                  : "Configura el grupo de mesas."}
              </DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
              <div>
                <Label>Personas del grupo</Label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {[2,3,4,5,6,8].map((n) => (
                    <Button key={n} type="button" variant={mergeSetupDialog.guests === n ? "default" : "outline"} onClick={() => setMergeSetupDialog((prev) => ({ ...prev, guests: n }))}>{n}</Button>
                  ))}
                  <div className="inline-flex items-center gap-1 rounded-lg border px-2 py-1">
                    <Button type="button" size="sm" variant="ghost" onClick={() => setMergeSetupDialog((prev) => ({ ...prev, guests: Math.max(1, prev.guests - 1) }))}>-</Button>
                    <span className="min-w-8 text-center font-semibold">{mergeSetupDialog.guests}</span>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setMergeSetupDialog((prev) => ({ ...prev, guests: Math.min(99, prev.guests + 1) }))}>+</Button>
                  </div>
                </div>
              </div>
              <div>
                <Label>Modo de orden</Label>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button type="button" variant={mergeSetupDialog.orderMode === "per_person" ? "default" : "outline"} onClick={() => setMergeSetupDialog((prev) => ({ ...prev, orderMode: "per_person" }))}>Orden por persona</Button>
                  <Button type="button" variant={mergeSetupDialog.orderMode === "table" ? "default" : "outline"} onClick={() => setMergeSetupDialog((prev) => ({ ...prev, orderMode: "table" }))}>Orden en grupo</Button>
                </div>
              </div>
              <div>
                <Label>Notas</Label>
                <Textarea value={mergeSetupDialog.notes} onChange={(event) => setMergeSetupDialog((prev) => ({ ...prev, notes: event.target.value }))} />
              </div>
            </div>
            <DialogFooter className="shrink-0 border-t px-5 py-4">
              <Button variant="outline" disabled={isStartingTableSession} onClick={() => setMergeSetupDialog({ open: false, sourceTableId: null, targetTableId: null, guests: 2, orderMode: "per_person", notes: "" })}>Cancelar</Button>
              <Button disabled={isStartingTableSession} onClick={() => void confirmMergeSetup()}>{isStartingTableSession ? "Uniendo..." : "Unir mesas"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog open={newSessionDialog.open} onOpenChange={(open) => { if (!isStartingTableSession) setNewSessionDialog((prev) => ({ ...prev, open })); }}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-xl flex-col overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b px-5 py-4">
              <DialogTitle>Nueva orden</DialogTitle>
              <DialogDescription>Configura personas, modo de pedido y notas antes de abrir la orden de mesa.</DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
              <div><Label>Personas</Label><div className="mt-2 flex flex-wrap gap-2">{[1,2,3,4,5,6].map((n)=><Button key={n} type="button" variant={newSessionDialog.guests===n?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,guests:n}))}>{n}</Button>)}<div className="ml-2 inline-flex items-center gap-1 rounded-lg border px-2 py-1"><Button type="button" size="sm" variant="ghost" onClick={()=>setNewSessionDialog((p)=>({...p,guests:Math.max(1,p.guests-1)}))}>-</Button><span className="min-w-8 text-center font-semibold">{newSessionDialog.guests}</span><Button type="button" size="sm" variant="ghost" onClick={()=>setNewSessionDialog((p)=>({...p,guests:Math.min(99,p.guests+1)}))}>+</Button></div></div></div>{(() => { const table = restaurantTables.find((t) => t.id === newSessionDialog.tableId); const cap = Number(table?.capacity || 0); return cap > 0 && newSessionDialog.guests > cap ? <p className="text-xs text-amber-500">Sobre capacidad sugerida de la mesa.</p> : null; })()}
              <div><Label>Modo de orden</Label><div className="mt-2 flex flex-wrap gap-2"><Button type="button" variant={newSessionDialog.orderMode==="table"?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,orderMode:"table"}))}>Orden completa</Button><Button type="button" variant={newSessionDialog.orderMode==="per_person"?"default":"outline"} onClick={()=>setNewSessionDialog((p)=>({...p,orderMode:"per_person"}))}>Por persona</Button></div></div>
              <div><Label>Notas</Label><Textarea value={newSessionDialog.notes} onChange={(e)=>setNewSessionDialog((p)=>({...p,notes:e.target.value}))} /></div>
            </div>
            <DialogFooter className="shrink-0 border-t px-5 py-4">
              <Button variant="outline" disabled={isStartingTableSession} onClick={()=>setNewSessionDialog({ open:false, tableId:null, guests:2, orderMode:"per_person", notes:"" })}>Cancelar</Button>
              <Button disabled={isStartingTableSession} onClick={() => void beginSessionFromDialog()}>{isStartingTableSession ? "Iniciando..." : "Iniciar orden"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog open={tableBillDialog.open} onOpenChange={(open) => setTableBillDialog((prev) => ({ ...prev, open }))}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-[48rem] flex-col overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b bg-background px-4 py-3">
              <DialogTitle>Cuenta de mesa</DialogTitle>
              <DialogDescription>Productos por persona, estados y pagos aplicados.</DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
              {tableBillDialog.loading ? (
                <div className="py-8 text-sm text-muted-foreground">Cargando cuenta...</div>
              ) : tableBillDialog.order ? (() => {
                const order = tableBillDialog.order;
                const session = tableBillDialog.session;
                const selectedGuest = tableBillGuestFilter.startsWith("guest:")
                  ? (session?.guests ?? []).find((guest) => guest.id === Number(tableBillGuestFilter.replace("guest:", ""))) ?? null
                  : null;
                const selectedGuestItems = selectedGuest ? getGuestItems(order, selectedGuest) : [];
                const selectedGuestItemIds = selectedGuest ? new Set(selectedGuestItems.map((item) => item.id)) : null;
                const statusFilterLabel = TABLE_BILL_STATUS_OPTIONS.find((option) => option.value === tableBillStatusFilter)?.label ?? "Todos";
                const matchesStatusFilter = (item: Order["items"][number]) => {
                  const paid = isTableBillItemPaid(item, tableBillDialog.payments);
                  if (tableBillStatusFilter === "all") return true;
                  if (tableBillStatusFilter === "paid") return paid;
                  if (paid) return false;
                  const status = item.kitchenStatus ?? "pending";
                  if (tableBillStatusFilter === "pending") return status === "pending";
                  if (tableBillStatusFilter === "in_kitchen") return status === "sent";
                  if (tableBillStatusFilter === "completed") return status === "ready";
                  if (tableBillStatusFilter === "served") return status === "delivered";
                  return true;
                };
                const filterItem = (item: Order["items"][number]) => {
                  if (selectedGuestItemIds && !selectedGuestItemIds.has(item.id)) return false;
                  return matchesStatusFilter(item);
                };
                const visibleItems = order.items.filter(filterItem);
                const selectedTotal = visibleItems.reduce((sum, item) => sum + getOrderItemTotal(item), 0);
                const selectedGuestTotal = selectedGuest ? selectedGuestItems.reduce((sum, item) => sum + getOrderItemTotal(item), 0) : 0;
                const selectedPaidCents = selectedGuest ? getGuestPaidCents(tableBillDialog.payments, selectedGuest) : 0;
                const selectedPendingCents = selectedGuest ? Math.max(toCents(selectedGuestTotal) - selectedPaidCents, 0) : 0;
                const renderItem = (item: Order["items"][number]) => {
                  const modifiers = getOrderItemModifiers(item);
                  return (
                    <div key={item.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b px-3 py-2.5 last:border-b-0">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium text-foreground">{item.productName}</p>
                          <Badge variant="outline" className={cn(getTableBillItemStatusTone(item, tableBillDialog.payments))}>{getTableBillItemStatusLabel(item, tableBillDialog.payments)}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {(item.tableGuestLabel || item.assignedName || "Mesa completa")} · Cantidad {item.quantity} · {formatMoney(item.unitPriceFinal ?? item.price)} c/u
                        </p>
                        {modifiers.length ? <p className="text-xs text-muted-foreground">Modificadores: {modifiers.join(", ")}</p> : null}
                      </div>
                      <p className="whitespace-nowrap text-right font-semibold">{formatMoney(getOrderItemTotal(item))}</p>
                    </div>
                  );
                };
                return (
                  <div className="space-y-3">
                    <div className="rounded-lg border bg-muted/20 px-3 py-2.5 text-sm">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-foreground">{restaurantTables.find((table) => table.id === tableBillDialog.tableId)?.name ?? "Mesa"}</p>
                          <p className="text-xs text-muted-foreground">{session?.guestsCount ?? 1} personas · {getSessionStateLabel(session ?? undefined)}</p>
                        </div>
                        <div className="flex flex-wrap justify-end gap-x-3 gap-y-1 text-xs font-semibold text-foreground sm:text-sm">
                          <span>Total: {formatMoney(order.totalPayable ?? order.total)}</span>
                          <span>Pagado: {formatMoney(order.totalPaid)}</span>
                          <span>Pendiente: {formatMoney(order.remaining)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex max-h-20 flex-wrap gap-2 overflow-y-auto pr-1">
                        <Button type="button" size="sm" variant={tableBillGuestFilter === "all" ? "default" : "outline"} onClick={() => setTableBillGuestFilter("all")}>Todos</Button>
                        {(session?.guests ?? []).map((guest) => (
                          <Button key={guest.id} type="button" size="sm" variant={tableBillGuestFilter === `guest:${guest.id}` ? "default" : "outline"} onClick={() => setTableBillGuestFilter(`guest:${guest.id}`)}>
                            {guest.label}
                          </Button>
                        ))}
                      </div>
                      <div className="grid gap-2 rounded-lg border bg-card px-3 py-2 sm:grid-cols-[minmax(0,1fr)_14rem] sm:items-center">
                        <p className="text-xs text-muted-foreground">
                          Total filtro: <span className="font-semibold text-foreground">{formatMoney(selectedTotal)}</span>
                        </p>
                        <Select value={tableBillStatusFilter} onValueChange={(value) => setTableBillStatusFilter(value as TableBillStatusFilter)}>
                          <SelectTrigger className="h-9">
                            <span className="truncate">Estado: {statusFilterLabel}</span>
                          </SelectTrigger>
                          <SelectContent>
                            {TABLE_BILL_STATUS_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    {selectedGuest ? (
                      <div className="rounded-lg border border-[color:var(--app-border-strong)] bg-[var(--app-surface)] px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold">{selectedGuest.label}</span>
                          <span className="font-medium">Total: {formatMoney(selectedGuestTotal)} · Pagado: {formatMoney(selectedPaidCents / 100)} · Pendiente: {formatMoney(selectedPendingCents / 100)}</span>
                        </div>
                      </div>
                    ) : null}
                    <div className="overflow-hidden rounded-lg border">
                      {visibleItems.length ? (
                        tableBillGuestFilter === "all" ? (() => {
                          const groups = new Map<string, { label: string; seat: number; items: Order["items"]; total: number; paidCents: number }>();
                          visibleItems.forEach((item) => {
                            const label = item.tableGuestLabel || item.assignedName || "Mesa completa";
                            const seat = item.tableGuestSeatNumber ?? item.guestNumber ?? 999;
                            const key = item.tableGuestId ? `guest-${item.tableGuestId}` : label;
                            const group = groups.get(key) ?? { label, seat, items: [], total: 0, paidCents: 0 };
                            group.items.push(item);
                            group.total += getOrderItemTotal(item);
                            group.paidCents += getItemAllocatedCents(item, tableBillDialog.payments);
                            groups.set(key, group);
                          });
                          return Array.from(groups.values()).sort((a, b) => a.seat - b.seat || a.label.localeCompare(b.label)).map((group) => (
                            <div key={group.label} className="border-b last:border-b-0">
                              <div className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-muted/80 px-3 py-2 text-sm font-semibold backdrop-blur">
                                <span>{group.label}</span>
                                <span className="whitespace-nowrap">{formatMoney(group.total)} · pagado {formatMoney(group.paidCents / 100)}</span>
                              </div>
                              {group.items.map(renderItem)}
                            </div>
                          ));
                        })() : (
                          <>
                            {visibleItems.map(renderItem)}
                            <div className="bg-muted/40 px-3 py-2 text-right text-sm font-semibold">Total filtro: {formatMoney(selectedTotal)}</div>
                          </>
                        )
                      ) : <div className="p-4 text-sm text-muted-foreground">No hay productos para este filtro.</div>}
                    </div>
                    {tableBillDialog.payments.length ? (
                      <div className="rounded-lg border p-3 text-sm">
                        <p className="mb-2 font-medium">Pagos realizados</p>
                        {tableBillDialog.payments.map((payment) => (
                          <div key={payment.id} className="flex flex-wrap justify-between gap-2 border-b py-2 last:border-b-0">
                            <span className="capitalize text-muted-foreground">
                              {payment.method}
                              {payment.allocations?.length ? ` · ${payment.allocations.map((allocation) => allocation.guestLabel || "Cuenta").join(", ")}` : ""}
                            </span>
                            <span className="font-semibold">{formatMoney(payment.amount)}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })() : null}
            </div>
            <DialogFooter className="shrink-0 gap-2 border-t bg-background px-4 py-3">
              <Button variant="outline" onClick={() => setTableBillDialog({ open: false, loading: false, tableId: null, session: null, order: null, payments: [] })}>Cerrar</Button>
              {tableBillDialog.order ? <Button variant="outline" onClick={() => void openTableLocalTicket()}><Printer className="mr-2 h-4 w-4" />Imprimir cuenta local</Button> : null}
              {tableBillDialog.order ? <Button variant="outline" onClick={() => { setTableBillDialog({ open: false, loading: false, tableId: null, session: null, order: null, payments: [] }); void openTableSession(tableBillDialog.tableId ?? 0); }}>Agregar productos</Button> : null}
              {canCollectTablePayments && tableBillDialog.order && tableBillDialog.session && tableBillDialog.tableId && tableBillGuestFilter.startsWith("guest:") ? (() => {
                const guest = tableBillDialog.session.guests.find((row) => row.id === Number(tableBillGuestFilter.replace("guest:", "")));
                if (!guest) return null;
                const scope = buildGuestPaymentScope(tableBillDialog.tableId!, tableBillDialog.session!, tableBillDialog.order!, tableBillDialog.payments, guest);
                return (
                  <Button type="button" variant="outline" disabled={scope.remainingCents <= 0 || isOpeningTablePayment || isPaymentOpen} onClick={() => void openTablePayment(tableBillDialog.tableId!, tableBillDialog.session!, { guest, returnToBill: true, order: tableBillDialog.order, payments: tableBillDialog.payments })}>
                    {scope.remainingCents <= 0 ? "Persona pagada" : `Cobrar ${guest.label}`}
                  </Button>
                );
              })() : null}
              {canCollectTablePayments && tableBillDialog.order ? <Button type="button" disabled={isOpeningTablePayment || isPaymentOpen} onClick={() => { const session = tableBillDialog.session; const tableId = tableBillDialog.tableId; const order = tableBillDialog.order; const payments = tableBillDialog.payments; if (session && tableId) void openTablePayment(tableId, session, { returnToBill: true, order, payments }); }}>Cobrar</Button> : null}
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <ThermalTicketDialog
          open={thermalTicket.open}
          title={thermalTicket.title || "Vista previa de ticket"}
          subtitle={thermalTicket.subtitle}
          ticketText={thermalTicket.text}
          logoUrl={thermalTicket.logoUrl}
          width={thermalTicketWidth}
          onWidthChange={setThermalTicketWidth}
          onOpenChange={(open) => setThermalTicket((prev) => ({ ...prev, open }))}
        />
        <Dialog open={forceReleaseDialog.open} onOpenChange={(open) => !forceReleaseDialog.loading && setForceReleaseDialog((prev) => ({ ...prev, open }))}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-lg flex-col overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b px-5 py-4">
              <DialogTitle>Liberar mesa con saldo pendiente</DialogTitle>
              <DialogDescription>Esta acción cancelará la cuenta pendiente y dejará la mesa disponible. Los pagos existentes se conservan.</DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
              <div className="rounded-lg border bg-muted/20 p-3 text-sm">
                <div className="flex justify-between"><span>Saldo a cancelar</span><span className="font-semibold">{formatMoney(forceReleaseDialog.session?.totalCached ?? 0)}</span></div>
                <div className="mt-1 text-xs text-muted-foreground">{forceReleaseDialog.requiresPin ? "Requiere PIN de admin o superadmin." : "Tu rol permite autorizar esta liberación."}</div>
              </div>
              <div>
                <Label>Motivo obligatorio</Label>
                <Textarea value={forceReleaseDialog.reason} onChange={(event) => setForceReleaseDialog((prev) => ({ ...prev, reason: event.target.value }))} placeholder="Ej: cliente se retiró, error operativo, cambio de mesa" />
              </div>
              {forceReleaseDialog.requiresPin ? (
                <div>
                  <Label>PIN admin/superadmin</Label>
                  <Input value={forceReleaseDialog.pin} onChange={(event) => setForceReleaseDialog((prev) => ({ ...prev, pin: event.target.value.replace(/\D/g, "").slice(0, 6) }))} inputMode="numeric" type="password" autoComplete="off" />
                </div>
              ) : null}
            </div>
            <DialogFooter className="shrink-0 border-t px-5 py-4">
              <Button variant="outline" disabled={forceReleaseDialog.loading} onClick={() => setForceReleaseDialog({ open: false, session: null, reason: "", pin: "", requiresPin: false, loading: false })}>Cancelar</Button>
              <Button disabled={forceReleaseDialog.loading} onClick={() => void confirmForceReleaseTableSession()}>{forceReleaseDialog.loading ? "Liberando..." : "Liberar mesa"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog open={kitchenSummaryDialog.open} onOpenChange={(open) => setKitchenSummaryDialog((prev) => ({ ...prev, open }))}>
          <DialogContent className="max-h-[92dvh] max-w-4xl overflow-hidden p-0">
            <DialogHeader className="border-b px-5 py-4">
              <DialogTitle>Órdenes en cocina</DialogTitle>
              <DialogDescription>Resumen por mesa, persona y estado de productos.</DialogDescription>
            </DialogHeader>
            <div className="max-h-[70dvh] overflow-y-auto px-5 py-4">
              {kitchenSummaryDialog.loading ? (
                <div className="py-8 text-sm text-muted-foreground">Cargando cocina...</div>
              ) : kitchenSummaryDialog.sessions.length ? (
                <div className="space-y-4">
                  {kitchenSummaryDialog.sessions.map((session) => (
                    <div key={session.sessionId} className="rounded-lg border bg-card p-3">
                      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">{session.tableLabel || "Mesa"}</p>
                          <p className="text-xs text-muted-foreground">{session.guestsCount} personas · Total {formatMoney(session.total)} · Pendiente {formatMoney(session.remaining)}</p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => { const tableId = tableSessions.find((row) => row.id === session.sessionId)?.tableIds[0] ?? 0; const tableSession = tableSessions.find((row) => row.id === session.sessionId); if (tableSession) void openTableBill(tableId, tableSession); }}>Ver cuenta</Button>
                          {canCollectTablePayments ? <Button type="button" size="sm" variant="outline" disabled={isOpeningTablePayment || isPaymentOpen} onClick={() => { const tableId = tableSessions.find((row) => row.id === session.sessionId)?.tableIds[0] ?? 0; const tableSession = tableSessions.find((row) => row.id === session.sessionId); if (tableSession) void openTablePayment(tableId, tableSession); }}>Cobrar</Button> : null}
                        </div>
                      </div>
                      <div className="space-y-3">
                        {(session.people.length ? session.people : [{ label: "Cuenta general", total: session.total, items: session.items }]).map((person) => (
                          <div key={person.label} className="rounded-md border bg-muted/10 p-2">
                            <div className="mb-2 flex justify-between text-sm font-medium"><span>{person.label}</span><span>{formatMoney(person.total)}</span></div>
                            <div className="space-y-2">
                              {person.items.map((item) => (
                                <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-background p-2 text-sm">
                                  <div>
                                    <p className="font-medium">{item.productName}</p>
                                    <p className="text-xs text-muted-foreground">x{item.quantity} · {item.kitchenStatus === "pending" ? "Pendiente de enviar" : item.kitchenStatus === "sent" ? "En cocina" : item.kitchenStatus === "ready" ? "Terminado" : "Servido"}</p>
                                  </div>
                                  <div className="flex gap-2">
                                    {canCompleteKitchenItems ? <Button size="sm" variant="outline" disabled={item.kitchenStatus === "ready" || item.kitchenStatus === "delivered"} onClick={() => void updateKitchenItemStatus(item.id, "ready")}>Terminado</Button> : null}
                                    <Button size="sm" variant="outline" disabled={item.kitchenStatus !== "ready"} onClick={() => void updateKitchenItemStatus(item.id, "delivered")}>Servido</Button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-sm text-muted-foreground">No hay órdenes de mesa activas.</div>
              )}
            </div>
            <DialogFooter className="border-t px-5 py-3">
              <Button variant="outline" onClick={() => setKitchenSummaryDialog({ open: false, loading: false, sessions: [] })}>Cerrar</Button>
              <Button onClick={() => void refreshKitchenSummary()}>Actualizar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Dialog open={isPaymentOpen} onOpenChange={handlePaymentDialogOpenChange}>
          <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-3xl flex-col overflow-hidden p-0">
            <div className="flex min-h-0 flex-1 flex-col">
              <DialogHeader className="border-b px-4 py-3 sm:px-6">
                <DialogTitle>{tablePaymentScope?.kind === "guest" ? `Cobrando ${tablePaymentScope.guestLabel || "persona"}` : tablePaymentScope ? "Cobrando cuenta completa" : "Cobrar pedido"}</DialogTitle>
                <DialogDescription>{tablePaymentScope ? "Pago de mesa. La mesa sigue abierta hasta saldar todo el saldo." : "Confirma el pago y envía a cocina"}</DialogDescription>
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
                          {(paymentDialogItems?.length ? paymentDialogItems : checkoutDraft.items.map((item) => ({
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
                                  <div className="text-[11px] gp-primary-text">
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
                              <div key={`checkout-table-${line.source}-${line.id}`} className="flex justify-between gp-primary-text">
                                <span>Descuento ({line.name})</span>
                                <span>-{formatMoney(line.amount)}</span>
                              </div>
                            ))
                          : checkoutSummaryDiscount > 0
                            ? <div className="flex justify-between gp-primary-text"><span>Descuento</span><span>-{formatMoney(checkoutSummaryDiscount)}</span></div>
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
                      <Button type="button" variant="outline" className="h-12 flex-1 text-sm" onClick={() => handlePaymentDialogOpenChange(false)}>Cerrar</Button>
                      <Button className="h-12 flex-1 text-sm" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || !selectedPaymentMethodCode || (selectedPaymentIsCash && showCashPanel && paymentAmountValue <= 0) || (splitEnabled && !splitValidation.isValid)}>
                        {isProcessingPayment ? "Procesando..." : "Continuar con el pago"}
                      </Button>
                    </div>
                  </div>
                </>
              ) : isOpeningTablePayment ? (
                <div className="flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <div>
                    <p className="font-medium text-foreground">Preparando cobro de mesa...</p>
                    <p>Estamos cargando el saldo y los pagos previos.</p>
                  </div>
                </div>
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

        <Dialog
          open={isCustomerDteOpen}
          onOpenChange={(open) => {
            setIsCustomerDteOpen(open);
            if (!open) setIsCustomerPickerOpen(false);
          }}
        >
          <DialogContent className="w-[95vw] max-w-xl">
            <DialogHeader>
              <DialogTitle>{dteEnabled ? "Cliente / DTE" : "Cliente"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              {dteEnabled ? (
                <div className="space-y-2">
                  <Label>Tipo DTE</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CF" ? "default" : "outline"} onClick={() => setDteDocumentType("CF")}>CF</Button>
                    <Button type="button" className="h-12 w-full min-w-0 text-sm sm:h-14 sm:text-base" variant={dteDocumentType === "CCF" ? "default" : "outline"} onClick={() => setDteDocumentType("CCF")}>CCF</Button>
                  </div>
                </div>
              ) : null}
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
                    className="h-12 w-full min-w-[132px] shrink-0 text-sm sm:h-14 sm:w-auto sm:px-5 sm:text-base"
                    disabled={!defaultConsumerCustomer}
                    onClick={() => {
                      if (defaultConsumerCustomer) setSelectedCustomerId(String(defaultConsumerCustomer.id));
                    }}
                  >
                    Consumidor final
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
                <div className="rounded-md border gp-primary-border gp-primary-soft p-3 text-sm">
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

        <Dialog open={isCustomerPickerOpen} onOpenChange={setIsCustomerPickerOpen}>
          <DialogContent className="w-[92vw] max-w-lg rounded-2xl p-5">
            <DialogHeader>
              <DialogTitle>Seleccionar cliente</DialogTitle>
              <DialogDescription>Busca por nombre, email, teléfono o documento.</DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              placeholder="Buscar cliente..."
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
            {filteredCustomers.length > visibleCustomers.length ? (
              <p className="text-xs text-muted-foreground">
                Refina tu búsqueda (mostrando 4 de {filteredCustomers.length})
              </p>
            ) : null}
            {!normalizedCustomerSearch && customersByDte.length > visibleCustomers.length ? (
              <p className="text-xs text-muted-foreground">Mostrando 4 de {customersByDte.length}</p>
            ) : null}
          </DialogContent>
        </Dialog>
        <Dialog open={isSplitConfigOpen} onOpenChange={setIsSplitConfigOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Dividir cuenta</DialogTitle>
              <DialogDescription>Define partes de la cuenta antes de cobrar con uno o varios métodos de pago.</DialogDescription>
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
      </div>
    );
  }

  return (
    <div className="h-[100dvh] overflow-x-hidden overflow-y-hidden bg-background">
      <div className={cn("h-full min-h-0 px-2 pb-4 pt-4 lg:px-4", requiresCashOpen && "pointer-events-none select-none opacity-80")}>
        <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[60%_40%]">
          {/* Products Section */}
          <div className="flex h-full min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
            {tableOrderContext ? (
              <Card className="shrink-0 border-[var(--color-primary-border)] bg-[var(--color-primary-surface)] p-3 text-[var(--color-primary-text)]">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs font-extrabold uppercase tracking-wide text-[var(--color-primary-text)]">Orden de mesa</p>
                    <h2 className="text-lg font-extrabold text-[var(--color-primary-text)]">{tableOrderContext.tableLabel}</h2>
                  </div>
                  {tableOrderContext.orderMode === "per_person" && tableOrderContext.guests.length ? (
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      {tableOrderContext.guests.map((guest) => (
                        <Button
                          key={guest.id}
                          type="button"
                          size="sm"
                          variant={tableOrderContext.activeGuestId === guest.id ? "default" : "outline"}
                          onPointerDown={(event) => startGuestLongPress(guest, event)}
                          onPointerUp={clearGuestLongPressTimer}
                          onPointerLeave={clearGuestLongPressTimer}
                          onPointerCancel={clearGuestLongPressTimer}
                          onContextMenu={(event) => handleGuestContextMenu(guest, event)}
                          onClick={() => selectTableGuest(guest)}
                        >
                          {guest.label}
                        </Button>
                      ))}
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setTableOrderContext((previous) => {
                            if (!previous || !previous.guests.length) return previous;
                            const currentIndex = previous.guests.findIndex((guest) => guest.id === previous.activeGuestId);
                            const nextGuest = previous.guests[(currentIndex + 1) % previous.guests.length];
                            return { ...previous, activeGuestId: nextGuest.id, activeGuestLabel: nextGuest.label };
                          });
                        }}
                      >
                        Siguiente persona
                      </Button>
                    </div>
                  ) : null}
                  <Button variant="outline" onClick={() => returnToTables()}>Volver a mesas</Button>
                </div>
              </Card>
            ) : null}

            <Dialog
              open={guestNameDialog.open}
              onOpenChange={(open) => {
                if (guestNameDialog.loading) return;
                setGuestNameDialog(open ? (previous) => ({ ...previous, open }) : { open: false, guest: null, name: "", loading: false });
              }}
            >
              <DialogContent className="w-[min(92vw,24rem)] rounded-2xl p-5">
                <DialogHeader>
                  <DialogTitle>Nombre de persona</DialogTitle>
                </DialogHeader>
                <Input
                  autoFocus
                  value={guestNameDialog.name}
                  placeholder="Ej: Carlos, Niño, Mesa jefe"
                  maxLength={40}
                  onChange={(event) => setGuestNameDialog((previous) => ({ ...previous, name: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void saveGuestName(guestNameDialog.name);
                  }}
                />
                <DialogFooter className="grid grid-cols-2 gap-2 sm:flex sm:justify-end">
                  <Button type="button" variant="outline" disabled={guestNameDialog.loading} onClick={() => void saveGuestName("")}>
                    Borrar
                  </Button>
                  <Button type="button" disabled={guestNameDialog.loading} onClick={() => void saveGuestName(guestNameDialog.name)}>
                    {guestNameDialog.loading ? "Guardando..." : "Asignar"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Search & Filters */}
            <Card className="p-4">
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  {!tableOrderContext ? (
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
                  ) : null}
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
                            decoding="async"
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
                        <Badge className="mb-1 max-w-full truncate gp-primary-bg">
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
                  {!tableOrderContext ? <ClockSV className="px-3 py-2" timeClassName="text-base sm:text-lg" /> : <div />}
                  <h2 className="text-xl font-bold text-center">Pedido Actual</h2>
                  <div className="flex items-center justify-end gap-2">
                    {!tableOrderContext ? (
                      <>
                        <TooltipProvider delayDuration={120}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button type="button" variant="outline" size="icon" title="Producto manual" aria-label="Producto manual" className="h-11 w-11 rounded-xl gp-primary-border" onClick={() => privilegedGuard.requirePrivilege("manualProduct", () => setIsManualProductOpen(true))}>
                                <Plus className="h-5 w-5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Producto manual</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                        <TooltipProvider delayDuration={120}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="outline" size="icon" title="Descuentos" aria-label="Descuentos" className="h-11 w-11 rounded-xl" onClick={() => privilegedGuard.requirePrivilege("discounts", () => setIsDiscountDialogOpen(true))}>
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
                                <Button variant="outline" size="icon" title={quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"} aria-label={quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"} className="h-11 w-11 rounded-xl gp-primary-border gp-primary-text" onClick={quickSalesMode === "last_sale" ? handleLastSaleQuickAction : openRecentSalesActions} disabled={isQuickSaleProcessing}>
                                  {quickSalesMode === "last_sale" ? <PrinterCheck className="h-5 w-5" /> : <History className="h-5 w-5" />}
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>{quickSalesMode === "last_sale" ? "Reimprimir última venta" : "Historial de ventas"}</TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        ) : null}
                        <TooltipProvider delayDuration={120}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="outline" size="icon" title="Transacciones de caja" aria-label="Transacciones de caja" className="h-11 w-11 rounded-xl" onClick={() => privilegedGuard.requirePrivilege("cashTransactions", () => { setIsCashDialogOpen(true); loadCashData().catch(() => undefined); })}>
                                <Wallet className="h-5 w-5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Transacciones de caja</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                        <TooltipProvider delayDuration={120}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="outline" size="icon" title="Refrescar" aria-label="Refrescar" className="h-11 w-11 rounded-xl" onClick={() => hardReloadPos("toolbar_refresh")}>
                                <RefreshCw className="h-5 w-5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Refrescar</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>

            </div>

            {!tableOrderContext ? <div className="flex-none border-b px-4 py-3">
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
            </div> : null}

            <div ref={cartItemsScrollRef} className="min-h-0 flex-1 overflow-y-auto p-4">
              {visibleCart.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <ShoppingCart className="h-16 w-16 mb-3 opacity-50" />
                  <p>{tableOrderContext ? "Sin productos pendientes" : "Carrito vacío"}</p>
                  <p className="text-sm">{tableOrderContext ? "Agrega productos para esta persona" : "Agrega productos para empezar"}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {visibleCart.map((item) => (
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
                  <div key={`${line.source}-${line.id}`} className="flex justify-between gp-primary-text">
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
                {!tableOrderContext ? (
                  <Button variant="outline" className="h-14 w-14 p-0" onClick={() => void handleQuickPrintTicket()} title="Imprimir ticket" aria-label="Imprimir ticket">
                    <Printer className="h-5 w-5" />
                  </Button>
                ) : null}
                <Button
                  variant="secondary"
                  className="h-14 w-14 p-0"
                  onClick={() => {
                    if (tableOrderContext) {
                      const session = tableSessions.find((row) => row.id === tableOrderContext.sessionId);
                      const tableId = session?.tableIds[0] ?? selectedOpsTableId ?? 0;
                      if (session && activeOrder) {
                        void (async () => {
                          try {
                            if (cart.length > 0) {
                              const saved = await syncExistingOpenOrder(activeOrder);
                              setActiveOrder(saved);
                            }
                            await openTableBill(tableId, session);
                          } catch (error) {
                            toast.error(error instanceof Error ? error.message : "No se pudo abrir la cuenta.");
                          }
                        })();
                      } else if (session) {
                        void openTableBill(tableId, session);
                      }
                      return;
                    }
                    const isCurrentOrderEmpty = cart.length === 0;
                    if (isCurrentOrderEmpty) {
                      navigate("/open-orders");
                      return;
                    }
                    void handleSendOrderToPending();
                  }}
                  disabled={isSendingToPending}
                  title={tableOrderContext ? "Ver cuenta" : cart.length === 0 ? "Órdenes guardadas" : "Guardar orden"}
                  aria-label={tableOrderContext ? "Ver cuenta" : cart.length === 0 ? "Órdenes guardadas" : "Guardar orden"}
                >
                  {tableOrderContext ? <ReceiptText className="h-5 w-5" /> : <Save className="h-5 w-5" />}
                </Button>
                <Button
                  variant="default"
                  className="h-14 flex-1 text-base font-bold"
                  size="lg"
                  disabled={(tableOrderContext ? visibleCart.length === 0 : cart.length === 0) || isProcessingPayment || requiresCashOpen || (!tableOrderContext && !canManageCashOperations)}
                  onClick={() => {
                    if (!tableOrderContext && !canManageCashOperations) {
                      toast.error("Mesero no puede cobrar.");
                      return;
                    }
                    if (tableOrderContext) void requestSendCurrentTableOrderToKitchen();
                    else void handleCheckout();
                  }}
                  title={!tableOrderContext && !canManageCashOperations ? "Mesero no puede cobrar." : undefined}
                >
                  <span className="flex flex-col leading-tight">
                    <span className="text-base font-semibold">{tableOrderContext ? tableOrderPrimaryLabel : isWaiterRole ? "Mesero no puede cobrar." : "Cobrar"}</span>
                    <span className="text-sm font-medium opacity-90">{formatMoney(total)}</span>
                  </span>
                </Button>
                <Button
                  variant="outline"
                  className="h-14 w-14 p-0"
                  onClick={() => {
                    if (tableOrderContext) setCart((previous) => previous.filter((item) => !tableGuestMatchesActive(item)));
                    else setCart([]);
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
            <DialogDescription>Ingresa una referencia para enviar la orden a cuentas abiertas.</DialogDescription>
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

      <Dialog open={tableBackDialogOpen} onOpenChange={setTableBackDialogOpen}>
        <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-xl flex-col overflow-hidden p-0">
          <DialogHeader className="shrink-0 border-b px-5 py-4">
            <DialogTitle>Productos sin guardar</DialogTitle>
            <DialogDescription>Tienes productos sin guardar. ¿Deseas guardar antes de volver a mesas?</DialogDescription>
          </DialogHeader>
          <DialogFooter className="shrink-0 border-t px-5 py-4">
            <Button variant="outline" onClick={() => setTableBackDialogOpen(false)}>Cancelar</Button>
            <Button variant="outline" onClick={() => { setTableBackDialogOpen(false); returnToTables(true); }}>Volver sin guardar</Button>
            <Button className="whitespace-normal text-center" onClick={() => { setTableBackDialogOpen(false); void saveTableOrder({ returnToMap: true }); }}>
              Guardar pendientes y volver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={tableKitchenSendDialog.open} onOpenChange={(open) => setTableKitchenSendDialog((prev) => ({ ...prev, open }))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar a cocina</DialogTitle>
            <DialogDescription>Hay productos pendientes en varias personas.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 sm:grid-cols-2">
            <Button className="h-14 text-base font-semibold" onClick={() => void sendCurrentTableOrderToKitchen("guest")}>
              Solo {tableOrderContext?.activeGuestLabel || "persona actual"}
            </Button>
            <Button className="h-14 text-base font-semibold" variant="secondary" onClick={() => void sendCurrentTableOrderToKitchen("table")}>
              Toda la mesa
            </Button>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTableKitchenSendDialog({ open: false, pendingGuestCount: 0 })}>Cancelar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isPendingChoiceOpen && canShowOpenOrdersChoice} onOpenChange={(open) => setIsPendingChoiceOpen(open)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Órdenes abiertas detectadas</DialogTitle>
            <DialogDescription>
              Hay {pendingOrdersCount} órdenes abiertas. ¿Deseas continuar en POS o revisar órdenes guardadas?
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={() => setIsPendingChoiceOpen(false)}>Continuar en POS</Button>
            <Button onClick={() => navigate("/open-orders")}>Órdenes guardadas</Button>
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
        <DialogContent className="flex max-h-[88dvh] w-[min(94vw,760px)] max-w-3xl flex-col overflow-hidden gp-primary-border bg-zinc-950 text-zinc-50 p-0">
          <DialogHeader className="border-b gp-primary-border px-5 py-4">
            <DialogTitle className="flex items-center gap-2 gp-primary-text"><ReceiptText className="h-5 w-5" /> Ventas recientes</DialogTitle>
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
                  <div key={`${sale.id}-${sale.paymentId}`} className="rounded-xl border gp-primary-border bg-zinc-900/80 p-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold gp-primary-text">{sale.orderNumber}</span>
                          <Badge variant="outline" className="gp-primary-border gp-primary-text">{sale.status}</Badge>
                          <span className="text-sm font-semibold">{formatMoney(sale.total)}</span>
                        </div>
                        <div className="text-xs text-zinc-400">{formatDateTimeSV(sale.createdAt)} · {sale.customerName} · {sale.paymentMethod}</div>
                        {dteEnabled ? <div className="truncate text-xs text-zinc-500">DTE: {sale.controlNumber || "No disponible"}</div> : null}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="gp-primary-border" onClick={() => void handleRecentSalePrint(sale)} disabled={recentSalesPrintingId === sale.paymentId}>
                          <Printer className="mr-1 h-4 w-4" /> {recentSalesPrintingId === sale.paymentId ? "Imprimiendo..." : "Ticket"}
                        </Button>
                        {dteEnabled ? (
                          <Button size="sm" className="gp-primary-button" onClick={() => void handleRecentSaleSendDte(sale)} disabled={recentSalesSendingId === sale.id || !sale.canSendDte}>
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
                    {cashCloseBlockedByOpenAccounts ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
                        {cashCloseOpenAccountsMessage}
                      </div>
                    ) : null}
                    <Button
                      className="h-14 w-full text-base font-semibold bg-red-600 text-white hover:bg-red-700 active:bg-red-800 disabled:bg-red-300 disabled:text-red-50 dark:bg-red-700 dark:hover:bg-red-600 dark:active:bg-red-500 dark:disabled:bg-red-900 dark:disabled:text-red-200"
                      onClick={() => setCloseCashStep("bills")}
                      disabled={cashCloseBlockedByOpenAccounts}
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
                    {cashCloseBlockedByOpenAccounts ? (
                      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-300">
                        {cashCloseOpenAccountsMessage}
                      </div>
                    ) : null}
                    {openAccountsCount > 0 && allowCloseWithPendingOrders ? (
                      <div className="rounded-md border border-blue-500/30 bg-blue-500/10 p-2 text-sm text-blue-700 dark:text-blue-300">
                        Hay {openAccountsCount} cuentas abiertas, pero el cierre con pendientes está habilitado por configuración.
                      </div>
                    ) : null}
                    <div className="sticky bottom-0 z-10 -mx-3 flex items-center gap-2 border-t bg-background/95 p-3 backdrop-blur">
                      <Button variant="outline" className="h-14 flex-1 text-base font-semibold" onClick={() => setCloseCashStep("pedidosYa")}>Atrás</Button>
                      <Button variant="destructive" className="h-14 flex-1 text-base font-semibold" onClick={handleCloseCashSession} disabled={isSavingCashAction || cashCloseBlockedByOpenAccounts}>{isSavingCashAction ? "Cerrando..." : "Confirmar cierre"}</Button>
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

      <Dialog open={isPaymentOpen} onOpenChange={handlePaymentDialogOpenChange}>
        <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-3xl flex-col overflow-hidden p-0">
          <div className="flex min-h-0 flex-1 flex-col">
            <DialogHeader className="border-b px-4 py-3 sm:px-6">
              <DialogTitle>{tablePaymentScope?.kind === "guest" ? `Cobrando ${tablePaymentScope.guestLabel || "persona"}` : tablePaymentScope ? "Cobrando cuenta completa" : "Cobrar pedido"}</DialogTitle>
              <DialogDescription>{tablePaymentScope ? "Pago de mesa. La mesa sigue abierta hasta saldar todo el saldo." : "Confirma el pago y envía a cocina"}</DialogDescription>
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
                        {(paymentDialogItems?.length ? paymentDialogItems : checkoutDraft.items.map((item) => ({
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
                                <div className="text-[11px] gp-primary-text">
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
                            <div key={`checkout-${line.source}-${line.id}`} className="flex justify-between gp-primary-text">
                              <span>Descuento ({line.name})</span>
                              <span>-{formatMoney(line.amount)}</span>
                            </div>
                          ))
                        : checkoutSummaryDiscount > 0
                          ? <div className="flex justify-between gp-primary-text"><span>Descuento</span><span>-{formatMoney(checkoutSummaryDiscount)}</span></div>
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
                    <Button type="button" variant="outline" className="h-12 flex-1 text-sm" onClick={() => handlePaymentDialogOpenChange(false)}>Cerrar</Button>
                    <Button className="h-12 flex-1 text-sm" onClick={handleSubmitPayment} disabled={isProcessingPayment || checkoutTotal <= 0 || !selectedPaymentMethodCode || (selectedPaymentIsCash && showCashPanel && paymentAmountValue <= 0) || (splitEnabled && !splitValidation.isValid)}>
                      {isProcessingPayment ? "Procesando..." : "Continuar con el pago"}
                    </Button>
                  </div>
                </div>
              </>
            ) : isOpeningTablePayment ? (
              <div className="flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin" />
                <div>
                  <p className="font-medium text-foreground">Preparando cobro de mesa...</p>
                  <p>Estamos cargando el saldo y los pagos previos.</p>
                </div>
              </div>
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
              <div className="rounded-md border gp-primary-border gp-primary-soft p-3 text-sm">
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
            <DialogDescription>Define partes de la cuenta antes de cobrar con uno o varios métodos de pago.</DialogDescription>
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
        <DialogContent className="flex max-h-[90vh] w-[96vw] max-w-3xl flex-col overflow-hidden rounded-2xl gp-primary-border p-0">
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
              <div className="rounded-xl border gp-primary-border p-3 sm:col-span-2">
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
