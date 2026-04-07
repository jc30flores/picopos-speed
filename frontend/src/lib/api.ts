import { fromCents, toCents } from "@/lib/money";
export const API_BASE_URL = import.meta.env.VITE_API_BASE ?? "/api";
const AUTH_DEBUG = String(import.meta.env.VITE_AUTH_DEBUG ?? "").toLowerCase() === "true";

export type Category = {
  id: number;
  name: string;
  image?: string | null;
  imagePath?: string | null;
  imageUrl?: string | null;
  isActive?: boolean;
  isHidden?: boolean;
  position?: number;
};

export type Modifier = {
  id: number;
  name: string;
  price: number;
  isActive?: boolean;
  sortOrder?: number;
  image?: string | null;
  imagePath?: string | null;
  imageUrl?: string | null;
};

export type ModifierGroup = {
  id: number;
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  image?: string | null;
  imagePath?: string | null;
  imageUrl?: string | null;
  modifiers: Modifier[];
};

export type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  effectivePrice?: number;
  originalPrice?: number;
  isSpecialPriceActiveNow?: boolean;
  appliedSpecialPriceRuleId?: number | null;
  appliedSpecialPriceRuleName?: string | null;
  sortOrder?: number;
  category: string;
  categoryName?: string | null;
  categoryId: number;
  image_url?: string | null;
  image_path?: string | null;
  image?: string | null;
  imagePath?: string | null;
  imageUrl?: string | null;
  available: boolean;
  isArchived?: boolean;
  disposableFee?: number;
  disposableApplyTo?: string[];
  requiresKitchen: boolean;
  modifierGroups: number[];
  modifierGroupsPos?: number[];
  modifierGroupLinks?: Array<{ groupId: number; showInPos: boolean }>;
};

export const resolveImageUrl = (imagePath?: string | null): string | null => {
  if (!imagePath) return null;
  if (/^https?:\/\//i.test(imagePath)) return imagePath;
  const base = API_BASE_URL.replace(/\/api\/?$/, "");
  const trimmedPath = imagePath.replace(/^\/+/, "");
  const normalizedPath = `/${trimmedPath}`;
  if (normalizedPath.startsWith("/api/")) {
    return normalizedPath.replace(/^\/api/, "");
  }
  if (normalizedPath.startsWith("/menu_image/")) {
    return normalizedPath.replace("/menu_image/", "/media/menu_image/", 1);
  }
  if (normalizedPath.startsWith("/media/")) {
    return normalizedPath;
  }
  return normalizedPath;
};

const normalizeMediaPath = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;

  const normalized = trimmed
    .replace(/^\/+/, "")
    .replace(/^media\/menu_image\/menu_image\//, "media/menu_image/")
    .replace(/^menu_image\/menu_image\//, "menu_image/");

  if (normalized.startsWith("media/")) return `/${normalized}`;
  if (normalized.startsWith("menu_image/")) return `/media/${normalized}`;
  return `/${normalized}`;
};

const normalizeImageUrl = (item: {
  image_url?: string | null;
  imageUrl?: string | null;
  image_path?: string | null;
  imagePath?: string | null;
  image?: string | null;
}): string | null => {
  const direct = item.image_url ?? item.imageUrl ?? null;
  if (typeof direct === "string" && direct.trim()) {
    return normalizeMediaPath(direct);
  }

  const path = item.image_path ?? item.imagePath ?? null;
  if (typeof path === "string" && path.trim()) {
    return normalizeMediaPath(path);
  }

  return null;
};

export type Discount = {
  id: number;
  name: string;
  description?: string;
  type: "percent" | "fixed" | "bxgy";
  value: number;
  appliesTo: "order" | "categories" | "products";
  targetCategoryIds?: number[];
  targetProductIds?: number[];
  daysOfWeek?: number[];
  startTime?: string | null;
  endTime?: string | null;
  serviceTypes?: string[];
  minAmount?: number | null;
  autoApply: boolean;
  isActive: boolean;
  priority?: number;
  stackable?: boolean;
  bxgyConfig?: Record<string, unknown>;
  availableNow?: boolean;
  hasConditions?: boolean;
  scope?: "order" | "categories" | "products";
};

export type ServiceType = {
  id: number;
  key: string;
  label: string;
  isActive?: boolean;
  sortOrder?: number;
  disposablesEnabled?: boolean;
};



export type ProductSpecialPriceRule = {
  id: number;
  productId?: number;
  name?: string;
  isActive: boolean;
  priority: number;
  discountType: "FIXED_PRICE" | "PERCENT_OFF";
  fixedPrice?: number | null;
  percentOff?: number | null;
  daysOfWeek: number[];
  startTime?: string | null;
  endTime?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  appliesToAllOrderTypes: boolean;
  orderTypeIds: number[];
};
export type TaxConfig = {
  rate: number;
  taxIncluded: boolean;
};

export type FeatureFlag = {
  id: number;
  key: string;
  label: string;
  description?: string;
  isEnabled: boolean;
};

export type OrderItem = {
  id: number;
  productName: string;
  productId?: number | null;
  isCustom?: boolean;
  type?: "menu" | "manual";
  code?: string;
  quantity: number;
  modifiers: string[];
  price: number;
  unitPriceList?: number | null;
  unitPriceSpecial?: number | null;
  unitPriceBeforeDiscount?: number;
  discountAmount?: number;
  discountPercent?: number;
  unitPriceFinal?: number;
  lineTotalBeforeDiscount?: number;
  lineTotalDiscount?: number;
  lineTotalFinal?: number;
  pricingMetadata?: Record<string, unknown> | null;
  unitPriceOverride?: number | null;
  assignedName?: string;
};

export type Order = {
  id: number;
  orderNumber: number;
  items: OrderItem[];
  total: number;
  status: "new" | "preparing" | "ready" | "delivered" | "canceled";
  serviceType: string | null;
  createdAt: Date;
  prepTime: number;
  customerName?: string;
  customerId?: number;
  dteDocumentType?: "CF" | "CCF" | "SX";
  ivaExempt?: boolean;
  ivaExemptDiscount?: number;
  paymentStatus: "unpaid" | "partial" | "paid";
  financialStatus: "open" | "paid" | "refunded_partial" | "refunded_full" | "voided";
  totalPaid: number;
  remaining: number;
  amountDueCents?: number;
  remainingCents?: number;
  refundTotal: number;
  netPaid: number;
  discountSnapshot?: Record<string, unknown> | null;
  requiresKitchen?: boolean;
  sendToKitchen?: boolean;
  subtotalBeforeDiscounts?: number;
  subtotalAfterDiscounts?: number;
  taxTotal?: number;
  totalPayable?: number;
};

export type EmployeeStats = {
  totalEmployees: number;
  activeEmployees: number;
  inactiveEmployees: number;
  attendanceTodayCount: number;
  lateTodayCount: number;
};

export type PaymentMethod = "cash" | "card" | "transfer";

export type BranchOption = {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
  is_default?: boolean;
  is_primary?: boolean;
  is_default_branch?: boolean;
};

export type Customer = {
  id: number;
  fullName: string;
  companyName?: string;
  clientType: "CF" | "CCF" | "SX";
  dui?: string;
  nit?: string;
  nrc?: string;
  phone?: string;
  email?: string | null;
  direccion?: string;
  departmentCode?: string;
  municipalityCode?: string;
  activityCode?: string;
  activityDescription?: string;
  isConsumerFinal: boolean;
  isDeleted: boolean;
  // legacy
  name?: string;
  tipoDocumento?: string;
  numDocumento?: string;
  codActividad?: string | null;
  descActividad?: string | null;
  direccionDepartamento?: string;
  direccionMunicipio?: string;
  direccionComplemento?: string;
  telefono?: string;
  correo?: string | null;
  isDefaultConsumerFinal?: boolean;
};

export type PaymentMethodOption = {
  id: number;
  code: "cash" | "card" | "transfer" | "pedidos_ya" | "paypal" | string;
  name: string;
  isCash: boolean;
  sortOrder: number;
};

export type CashSessionSnapshot = {
  open: boolean;
  session?: {
    id: number;
    openingCash: number;
    openedAt: string;
    status: "open" | "closed";
  };
  summary?: {
    openingCash: number;
    totalCashSales: number;
    totalCashOut: number;
    expectedCashInDrawer: number;
    countedCash: number;
    overShortCash: number;
    methods: { cash: number; card: number; cardDebit: number; cardCredit: number; transfer: number; pedidosYa: number; payPal: number; cashIn: number };
  };
};

export type CashTransaction = {
  id: number;
  type: "cash_out" | "cash_in" | "expense" | "payout";
  amount: number;
  description: string;
  createdAt: string;
};

export type CategoryDeleteConflictError = Error & {
  status?: number;
  activeProducts?: string[];
};


export type Payment = {
  id: number;
  orderId: number;
  method: PaymentMethod;
  cardType?: "debit" | "credit";
  amount: number;
  cashReceived?: number;
  tipAmount: number;
  reference?: string;
  receivedBy?: string | null;
  createdAt: Date;
  printed?: boolean;
  printError?: string | null;
  drawerOpened?: boolean;
  drawerError?: string | null;
};

export type PrintJob = {
  id: number;
  orderId: number | null;
  type: "kitchen" | "customer" | "closeout" | "refund" | "void";
  status: "queued" | "rendered" | "printed" | "failed";
  contentText: string;
  contentHtml?: string;
  createdAt: Date;
  printedAt?: Date | null;
};

export type SalesReportRow = {
  paymentId: number;
  orderId: number;
  orderNumber: number;
  serviceType: Order["serviceType"] | string;
  serviceTypeLabel: string;
  createdAt: Date;
  total: number;
  status: Order["status"];
  customerName: string;
  controlNumber: string;
  paymentMethodCode: string;
  paymentMethodLabel: string;
  financialStatus: Order["financialStatus"];
};

export type SalesReportAggregates = {
  countOrders: number;
  sumSubtotal: number;
  sumTax: number;
  sumTotal: number;
  sumDiscountTotal: number;
  grossTotal: number;
  refundTotal: number;
  netTotal: number;
  paymentMethods: {
    cash: number;
    card: number;
    transfer: number;
  };
  tipsTotal: number;
  tipsNet: number;
  cashTotal: number;
  nonCashTotal: number;
  refundsCount: number;
  ordersPaid: number;
  ordersVoided: number;
  refundsByMethod: {
    cash: number;
    card: number;
    transfer: number;
  };
};

export type ReportsGranularity = "hours" | "week" | "month" | "year";
export type ReportsComparisonMode = "none" | "previous_period" | "previous_year";

export type SalesTimeseriesPoint = {
  bucket: string;
  currentTotal: number;
  comparisonTotal: number;
};

export type SalesTimeseriesResponse = {
  points: SalesTimeseriesPoint[];
  current: { totalSales: number; transactions: number; avgTicket: number };
  comparison?: { totalSales: number; transactions: number; avgTicket: number } | null;
};

export type SalesBreakdownDimension = "category" | "product" | "service_type" | "payment_method" | "modifier";
export type SalesBreakdownRow = {
  key: string;
  label: string;
  total: number;
  percentage: number;
  transactions: number;
};

export type Refund = {
  id: number;
  orderId: number;
  originalPaymentId?: number | null;
  cashSessionId?: number | null;
  method: PaymentMethod;
  amount: number;
  tipRefunded: number;
  reason: string;
  approvedBy?: string | null;
  createdBy?: string | null;
  createdAt: Date;
};

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  role: "admin" | "manager" | "cashier" | "kitchen" | "kiosk" | "worker" | "accountant";
  isSuperuser: boolean;
  isStaff: boolean;
  redirectTo?: string;
};

type AuthPayload = AuthUser & {
  is_superuser?: boolean;
  is_staff?: boolean;
  redirect_to?: string;
  user?: Partial<AuthUser> & { is_superuser?: boolean; is_staff?: boolean };
  profile?: { role?: AuthUser["role"]; redirect_to?: string; redirectTo?: string };
};

const buildApiUrl = (path: string) => {
  const base = API_BASE_URL.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
};

const authDebugLog = (...args: unknown[]) => {
  if (!AUTH_DEBUG) return;
  // eslint-disable-next-line no-console
  console.info("[auth-debug]", ...args);
};

export class ApiRequestError extends Error {
  code?: string;
  status?: number;
  isNetworkError: boolean;

  constructor(message: string, options?: { code?: string; status?: number; isNetworkError?: boolean }) {
    super(message);
    this.name = "ApiRequestError";
    this.code = options?.code;
    this.status = options?.status;
    this.isNetworkError = Boolean(options?.isNetworkError);
  }
}

export const isNetworkApiError = (error: unknown): boolean => error instanceof ApiRequestError && error.isNetworkError;

export const isApiStatusError = (error: unknown, statuses: number[]): boolean =>
  error instanceof ApiRequestError && typeof error.status === "number" && statuses.includes(error.status);

const getCsrfToken = () => {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
};

const buildEmptyAttendanceState = (): AttendanceState => ({
  employee: { id: 0, name: "—", role: "worker" },
  date: new Date().toISOString().slice(0, 10),
  clockIn: null,
  breakStart: null,
  breakEnd: null,
  clockOut: null,
  canClockIn: false,
  canBreakStart: false,
  canBreakEnd: false,
  canClockOut: false,
});

const request = async (path: string, options: RequestInit = {}) => {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedPathKey = normalizedPath.endsWith("/") ? normalizedPath.slice(0, -1) : normalizedPath;

  if (!isFormData && !headers.has("Content-Type") && method !== "GET") {
    headers.set("Content-Type", "application/json");
  }

  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrfToken = getCsrfToken();
    if (csrfToken && !headers.has("X-CSRFToken")) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  let response: Response;
  try {
    response = await fetch(buildApiUrl(path), {
      credentials: "include",
      ...options,
      headers,
    });
  } catch (error) {
    authDebugLog("network_error", { path, method, error: error instanceof Error ? error.message : String(error) });
    throw new ApiRequestError("NETWORK_ERROR", { code: "NETWORK_ERROR", isNetworkError: true });
  }
  const authBypassUnauthorizedEvent = new Set([
    "/auth/csrf",
    "/auth/login",
    "/auth/pin-login",
    "/auth/logout",
    "/auth/me",
  ]);
  if ((response.status === 401 || response.status === 403) && !authBypassUnauthorizedEvent.has(normalizedPathKey)) {
    window.dispatchEvent(new CustomEvent("auth:unauthorized"));
  }
  return response;
};

const handleJson = async <T>(response: Response): Promise<T> => {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!response.ok) {
    if (isJson) {
      const errorPayload = await response.json().catch(() => null);
      const errorCode = errorPayload && typeof errorPayload.code === "string" ? String(errorPayload.code) : undefined;
      const detailText = String((errorPayload && (errorPayload.detail || errorPayload.error)) || "");
      const shouldRequireCashGate =
        errorCode === "CASH_SESSION_REQUIRED" ||
        ((response.status === 401 || response.status === 403 || response.status === 409) &&
          /caja|cash session|required/i.test(detailText));
      if (shouldRequireCashGate) {
        window.dispatchEvent(new CustomEvent("cash:required"));
      }
      const message =
        detailText ||
        (errorPayload ? JSON.stringify(errorPayload) : "");
      throw new ApiRequestError(message || `Error del servidor (${response.status}). Revisa el backend.`, {
        code: errorCode,
        status: response.status,
      });
    }
    await response.text().catch(() => "");
    throw new ApiRequestError(`Error del servidor (${response.status}). Revisa el backend.`, { status: response.status });
  }

  if (!isJson) {
    const text = await response.text();
    throw new ApiRequestError(text ? `Unexpected response: ${text.slice(0, 200)}` : "Unexpected response");
  }

  return response.json() as Promise<T>;
};

const normalizeAuthPayload = (raw: AuthPayload): AuthUser => {
  const nestedUser = raw.user ?? {};
  const nestedProfile = raw.profile ?? {};
  return {
    id: Number(raw.id ?? nestedUser.id ?? 0),
    username: String(raw.username ?? nestedUser.username ?? ""),
    email: String(raw.email ?? nestedUser.email ?? ""),
    role: (raw.role ?? nestedProfile.role ?? "cashier") as AuthUser["role"],
    isSuperuser: Boolean(raw.isSuperuser ?? raw.is_superuser ?? nestedUser.isSuperuser ?? nestedUser.is_superuser),
    isStaff: Boolean(raw.isStaff ?? raw.is_staff ?? nestedUser.isStaff ?? nestedUser.is_staff),
    redirectTo: (raw.redirectTo ?? raw.redirect_to ?? nestedProfile.redirectTo ?? nestedProfile.redirect_to) as string | undefined,
  };
};

export const getCSRF = async (): Promise<void> => {
  const response = await request("/auth/csrf/");
  await handleJson(response);
};

export const login = async (payload: {
  email?: string;
  username?: string;
  password: string;
}): Promise<AuthUser> => {
  const response = await request("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const raw = await handleJson<AuthPayload>(response);
  const normalized = normalizeAuthPayload(raw);
  authDebugLog("login.response", { status: response.status, keys: Object.keys(raw ?? {}), username: normalized.username });
  return normalized;
};

export const pinLogin = async (payload: { pin: string }): Promise<AuthUser> => {
  const response = await request("/auth/pin-login/", {
    method: "POST",
    body: JSON.stringify({ pin: String(payload.pin) }),
  });
  authDebugLog("pin_login.response", { status: response.status, ok: response.ok });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json().catch(() => null) : null;
    const detail = body?.detail ? String(body.detail) : "";
    if (response.status === 401) throw new ApiRequestError("PIN_INVALID", { code: "PIN_INVALID", status: response.status });
    if (response.status === 409) throw new ApiRequestError("PIN_DUPLICATE", { code: "PIN_DUPLICATE", status: response.status });
    if (response.status === 429) throw new ApiRequestError(detail || "PIN_THROTTLED", { code: "PIN_THROTTLED", status: response.status });
    if (response.status === 403) throw new ApiRequestError("PIN_FORBIDDEN", { code: "PIN_FORBIDDEN", status: response.status });
    throw new ApiRequestError(detail || `PIN_LOGIN_ERROR_${response.status}`, { status: response.status });
  }
  const raw = await handleJson<AuthPayload>(response);
  const normalized = normalizeAuthPayload(raw);
  authDebugLog("pin_login.payload_keys", Object.keys(raw ?? {}));
  return normalized;
};

export const logout = async (): Promise<void> => {
  const response = await request("/auth/logout/", { method: "POST" });
  if (!response.ok && response.status !== 204 && response.status !== 401 && response.status !== 403) {
    const message = await response.text();
    throw new Error(message || "Logout failed");
  }
};

export const me = async (): Promise<AuthUser> => {
  const response = await request("/auth/me/");
  const raw = await handleJson<AuthPayload>(response);
  const normalized = normalizeAuthPayload(raw);
  authDebugLog("me.response", { status: response.status, user: normalized?.username, role: normalized?.role, keys: Object.keys(raw ?? {}) });
  return normalized;
};

export const verifyPrivilegedPin = async (pin: string): Promise<{ ok: boolean; role: "ADMIN" | "GERENTE"; userId: number }> => {
  const response = await request("/auth/verify-privileged-pin/", {
    method: "POST",
    body: JSON.stringify({ pin }),
  });
  const data = await handleJson<{ ok: boolean; role: "ADMIN" | "MANAGER" | "GERENTE"; user_id: number }>(response);
  return {
    ok: Boolean(data.ok),
    role: data.role === "MANAGER" ? "GERENTE" : (data.role as "ADMIN" | "GERENTE"),
    userId: data.user_id,
  };
};

let cachedTaxConfig: TaxConfig | null = null;

export const getCategories = async (query?: string): Promise<Category[]> => {
  const params = query ? `?q=${encodeURIComponent(query)}` : "";
  const response = await request(`/menu/categories/${params}`);
  const data = await handleJson<Array<{ id: number; name: string; image?: string | null; image_url?: string | null; image_path?: string | null; is_active: boolean; is_hidden?: boolean; position?: number }>>(response);
  // NOTE: backend ordering by `position` is the source of truth for categories.
  // Do not re-sort on the client; preserve API order exactly.
  return data
    .map((item) => ({
      id: item.id,
      name: item.name,
      image: item.image ?? null,
      imagePath: item.image_path ?? null,
      imageUrl: normalizeImageUrl(item),
      isActive: item.is_active,
      isHidden: Boolean(item.is_hidden),
      position: Number(item.position ?? 0),
    }))
    .filter((item) => !item.isHidden && !item.name.toUpperCase().includes("SIN CATEGORÍA"));
};

export const getFeatureFlags = async (): Promise<FeatureFlag[]> => {
  const response = await request("/core/feature-flags/");
  const data = await handleJson<
    Array<{
      id: number;
      key: string;
      label: string;
      description: string;
      is_enabled: boolean;
    }>
  >(response);
  return data.map((flag) => ({
    id: flag.id,
    key: flag.key,
    label: flag.label,
    description: flag.description,
    isEnabled: flag.is_enabled,
  }));
};

export const updateFeatureFlag = async (
  id: number,
  payload: { isEnabled: boolean }
): Promise<FeatureFlag> => {
  const response = await request(`/core/feature-flags/${id}/`, {
    method: "PATCH",
    body: JSON.stringify({ is_enabled: payload.isEnabled }),
  });
  const data = await handleJson<{
    id: number;
    key: string;
    label: string;
    description: string;
    is_enabled: boolean;
  }>(response);
  return {
    id: data.id,
    key: data.key,
    label: data.label,
    description: data.description,
    isEnabled: data.is_enabled,
  };
};

export const createCategory = async (payload: string | { name: string; image?: File | null }): Promise<Category> => {
  const normalizedPayload = typeof payload === "string" ? { name: payload, image: null } : payload;
  const formData = new FormData();
  formData.append("name", normalizedPayload.name);
  if (normalizedPayload.image) {
    formData.append("image", normalizedPayload.image);
  }

  const response = await request("/menu/categories/", {
    method: "POST",
    body: formData,
  });
  const data = await handleJson<{ id: number; name: string; image?: string | null; image_url?: string | null; image_path?: string | null; is_active: boolean; is_hidden?: boolean; position?: number }>(response);
  return {
    id: data.id,
    name: data.name,
    image: data.image ?? null,
    imagePath: data.image_path ?? null,
    imageUrl: normalizeImageUrl(data),
    isActive: data.is_active,
    isHidden: Boolean(data.is_hidden),
    position: Number(data.position ?? 0),
  };
};

export const updateCategory = async (
  categoryId: number,
  payload: string | { name?: string; image?: File | null; removeImage?: boolean }
): Promise<Category> => {
  const normalizedPayload = typeof payload === "string" ? { name: payload, image: null, removeImage: false } : payload;
  const formData = new FormData();
  if (normalizedPayload.name !== undefined) {
    formData.append("name", normalizedPayload.name);
  }
  if (normalizedPayload.image) {
    formData.append("image", normalizedPayload.image);
  }
  if (normalizedPayload.removeImage) {
    formData.append("remove_image", "1");
  }

  const response = await request(`/menu/categories/${categoryId}/`, {
    method: "PATCH",
    body: formData,
  });
  const data = await handleJson<{ id: number; name: string; image?: string | null; image_url?: string | null; image_path?: string | null; is_active: boolean; is_hidden?: boolean; position?: number }>(response);
  return {
    id: data.id,
    name: data.name,
    image: data.image ?? null,
    imagePath: data.image_path ?? null,
    imageUrl: normalizeImageUrl(data),
    isActive: data.is_active,
    isHidden: Boolean(data.is_hidden),
    position: Number(data.position ?? 0),
  };
};

export const deleteCategory = async (categoryId: number): Promise<void> => {
  const response = await request(`/menu/categories/${categoryId}/`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    if (response.status === 404) {
      return;
    }
    const data = await response.json().catch(() => ({ detail: "No se pudo eliminar la categoría" }));
    const error = new Error(data.detail || "No se pudo eliminar la categoría") as CategoryDeleteConflictError;
    error.status = response.status;
    if (Array.isArray(data.active_products)) {
      error.activeProducts = data.active_products.filter((name: unknown): name is string => typeof name === "string");
    }
    throw error;
  }
};

export const getProducts = async (options?: {
  search?: string;
  categoryId?: number;
  page?: number;
  limit?: number;
  ids?: number[];
  orderTypeId?: number;
  at?: string;
}): Promise<Product[]> => {
  const params = new URLSearchParams();
  if (options?.search) params.set("search", options.search);
  if (options?.categoryId) params.set("category_id", String(options.categoryId));
  if (options?.page) params.set("page", String(options.page));
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.ids?.length) params.set("ids", options.ids.join(","));
  if (options?.orderTypeId) params.set("order_type_id", String(options.orderTypeId));
  if (options?.at) params.set("at", options.at);
  const query = params.toString();
  const response = await request(`/menu/products/${query ? `?${query}` : ""}`);
  const data = await handleJson<Array<{
    id: number;
    name: string;
    description: string;
    price: string;
    original_price?: string | null;
    effective_price?: string | null;
    is_special_price_active_now?: boolean;
    applied_special_price_rule_id?: number | null;
    applied_special_price_rule_name?: string | null;
    sort_order?: number;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    is_archived?: boolean;
    disposable_fee?: string;
    disposable_apply_to?: string[];
    requires_kitchen: boolean;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
  }>>(response);
  return data.map((item) => {
    const normalizedImageUrl = normalizeImageUrl(item);
    return {
      id: item.id,
      name: item.name,
      description: item.description,
      price: Number(item.price),
      originalPrice: item.original_price != null ? Number(item.original_price) : Number(item.price),
      effectivePrice: item.effective_price != null ? Number(item.effective_price) : Number(item.price),
      isSpecialPriceActiveNow: Boolean(item.is_special_price_active_now ?? item.applied_special_price_rule_id != null),
      appliedSpecialPriceRuleId: item.applied_special_price_rule_id ?? null,
      appliedSpecialPriceRuleName: item.applied_special_price_rule_name ?? null,
      sortOrder: Number(item.sort_order ?? 0),
      category: item.category,
      categoryName: item.category_name ?? item.category,
      categoryId: item.category_id_display ?? 0,
      image_url: normalizedImageUrl,
      image_path: item.image_path ?? null,
      image: item.image,
      imagePath: item.image_path ?? null,
      imageUrl: normalizedImageUrl,
      available: item.available,
      isArchived: Boolean(item.is_archived),
      disposableFee: Number(item.disposable_fee ?? 0),
      disposableApplyTo: Array.isArray(item.disposable_apply_to) ? item.disposable_apply_to : [],
      requiresKitchen: Boolean(item.requires_kitchen),
      modifierGroups: item.modifier_groups,
      modifierGroupsPos: item.modifier_groups_pos ?? [],
      modifierGroupLinks: (item.modifier_group_links ?? []).map((link) => ({
        groupId: link.group_id,
        showInPos: Boolean(link.show_in_pos),
      })),
    };
  });
};

export const createProduct = async (payload: {
  name: string;
  description: string;
  price: number;
  categoryId: number;
  image?: File | null;
  available: boolean;
  requiresKitchen: boolean;
  disposableFee?: number;
  disposableApplyTo?: string[];
  modifierGroupIds?: number[];
}): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
  formData.append("requires_kitchen", payload.requiresKitchen ? "true" : "false");
  formData.append("disposable_fee", String(payload.disposableFee ?? 0));
  formData.append("disposable_apply_to", JSON.stringify(payload.disposableApplyTo ?? []));
  if (payload.image) {
    formData.append("image", payload.image);
  }
  if (payload.modifierGroupIds?.length) {
    payload.modifierGroupIds.forEach((id) => formData.append("modifier_group_ids", id.toString()));
  }

  const response = await request("/menu/products/", {
    method: "POST",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    original_price?: string | null;
    effective_price?: string | null;
    is_special_price_active_now?: boolean;
    applied_special_price_rule_id?: number | null;
    applied_special_price_rule_name?: string | null;
    sort_order?: number;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    is_archived?: boolean;
    disposable_fee?: string;
    disposable_apply_to?: string[];
    requires_kitchen: boolean;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    originalPrice: data.original_price != null ? Number(data.original_price) : Number(data.price),
    effectivePrice: data.effective_price != null ? Number(data.effective_price) : Number(data.price),
    isSpecialPriceActiveNow: Boolean(data.is_special_price_active_now ?? data.applied_special_price_rule_id != null),
    appliedSpecialPriceRuleId: data.applied_special_price_rule_id ?? null,
    appliedSpecialPriceRuleName: data.applied_special_price_rule_name ?? null,
    sortOrder: Number(data.sort_order ?? 0),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? payload.categoryId,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    disposableFee: Number(data.disposable_fee ?? 0),
    disposableApplyTo: Array.isArray(data.disposable_apply_to) ? data.disposable_apply_to : [],
    requiresKitchen: Boolean(data.requires_kitchen),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
  };
};

export const updateProduct = async (
  productId: number,
  payload: {
    name: string;
    description: string;
    price: number;
    categoryId: number;
    image?: File | null;
    available: boolean;
    is_archived?: boolean;
    requiresKitchen: boolean;
    disposableFee?: number;
    disposableApplyTo?: string[];
    modifierGroupIds?: number[];
  }
): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
  formData.append("requires_kitchen", payload.requiresKitchen ? "true" : "false");
  formData.append("disposable_fee", String(payload.disposableFee ?? 0));
  formData.append("disposable_apply_to", JSON.stringify(payload.disposableApplyTo ?? []));
  if (payload.image) {
    formData.append("image", payload.image);
  }
  if (payload.modifierGroupIds?.length) {
    payload.modifierGroupIds.forEach((id) => formData.append("modifier_group_ids", id.toString()));
  }

  const response = await request(`/menu/products/${productId}/`, {
    method: "PATCH",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    original_price?: string | null;
    effective_price?: string | null;
    is_special_price_active_now?: boolean;
    applied_special_price_rule_id?: number | null;
    applied_special_price_rule_name?: string | null;
    sort_order?: number;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    requires_kitchen: boolean;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    originalPrice: data.original_price != null ? Number(data.original_price) : Number(data.price),
    effectivePrice: data.effective_price != null ? Number(data.effective_price) : Number(data.price),
    isSpecialPriceActiveNow: Boolean(data.is_special_price_active_now ?? data.applied_special_price_rule_id != null),
    appliedSpecialPriceRuleId: data.applied_special_price_rule_id ?? null,
    appliedSpecialPriceRuleName: data.applied_special_price_rule_name ?? null,
    sortOrder: Number(data.sort_order ?? 0),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? payload.categoryId,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    requiresKitchen: Boolean(data.requires_kitchen),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
  };
};

export const changeProductPrice = async (productId: number, payload: { code: string; newPrice?: number; validateOnly?: boolean }): Promise<{
  success: boolean;
  validated?: boolean;
  productId?: number;
  oldPrice?: number;
  newPrice?: number;
  updatedAt?: string;
}> => {
  const response = await request(`/menu/products/${productId}/change-price/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code: payload.code,
      validate_only: Boolean(payload.validateOnly),
      new_price: payload.newPrice,
    }),
  });
  const data = await handleJson<any>(response);
  return {
    success: Boolean(data.success),
    validated: data.validated,
    productId: data.product_id,
    oldPrice: data.old_price != null ? Number(data.old_price) : undefined,
    newPrice: data.new_price != null ? Number(data.new_price) : undefined,
    updatedAt: data.updated_at,
  };
};

export const deleteProduct = async (productId: number): Promise<{ detail?: string }> => {
  const response = await request(`/menu/products/${productId}/`, { method: "DELETE" });
  if (response.status === 204) return {};
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "No se pudo eliminar el producto");
  }
  return data;
};

export const updateProductModifierGroups = async (
  productId: number,
  modifierGroupIds: number[],
  modifierGroupLinks?: Array<{ groupId: number; showInPos: boolean }>,
): Promise<Product> => {
  const response = await request(`/menu/products/${productId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modifier_group_ids: modifierGroupIds,
      modifier_group_links: (modifierGroupLinks ?? []).map((link) => ({
        group_id: link.groupId,
        show_in_pos: link.showInPos,
      })),
    }),
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    sort_order?: number;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    is_archived?: boolean;
    disposable_fee?: string;
    disposable_apply_to?: string[];
    requires_kitchen: boolean;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    sortOrder: Number(data.sort_order ?? 0),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? 0,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    disposableFee: Number(data.disposable_fee ?? 0),
    disposableApplyTo: Array.isArray(data.disposable_apply_to) ? data.disposable_apply_to : [],
    requiresKitchen: Boolean(data.requires_kitchen),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
  };
};

export const reorderProductModifierGroups = async (
  productId: number,
  orderedIds: number[],
): Promise<void> => {
  await request(`/menu/products/${productId}/modifier-groups/reorder/`, {
    method: "PATCH",
    body: JSON.stringify({ ordered_ids: orderedIds }),
  }).then(handleJson);
};

export const updateProductAvailability = async (
  productId: number,
  available: boolean,
): Promise<Product> => {
  const formData = new FormData();
  formData.append("available", available ? "true" : "false");
  const response = await request(`/menu/products/${productId}/`, {
    method: "PATCH",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    sort_order?: number;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    is_archived?: boolean;
    requires_kitchen: boolean;
    modifier_groups: number[];
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    sortOrder: Number(data.sort_order ?? 0),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? 0,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    requiresKitchen: Boolean(data.requires_kitchen),
    modifierGroups: data.modifier_groups,
  };
};

export const getModifierGroups = async (): Promise<ModifierGroup[]> => {
  const response = await request("/menu/modifier-groups/");
  const data = await handleJson<Array<{
    id: number;
    name: string;
    required: boolean;
    min_selection: number;
    max_selection: number;
    modifiers: Array<{ id: number; name: string; price: string; is_active: boolean; sort_order?: number; image?: string | null; image_path?: string | null; image_url?: string | null }>;
    image?: string | null;
    image_path?: string | null;
    image_url?: string | null;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    required: item.required,
    minSelection: item.min_selection,
    maxSelection: item.max_selection,
    image: item.image ?? null,
    imagePath: item.image_path ?? null,
    imageUrl: normalizeImageUrl(item),
    modifiers: item.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      price: Number(modifier.price),
      isActive: modifier.is_active,
      sortOrder: modifier.sort_order ?? 0,
      image: modifier.image ?? null,
      imagePath: modifier.image_path ?? null,
      imageUrl: normalizeImageUrl(modifier),
    })),
  }));
};

export const reorderModifierGroupOptions = async (groupId: number, orderedIds: number[]): Promise<void> => {
  await request(`/menu/modifier-groups/${groupId}/options/reorder/`, {
    method: "PATCH",
    body: JSON.stringify({ ordered_ids: orderedIds }),
  }).then(handleJson);
};

export const createModifierGroup = async (payload: {
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  image?: File | null;
  modifiers: Array<{ name: string; price: number; isActive?: boolean; image?: File | null }>;
}): Promise<ModifierGroup> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("required", payload.required ? "true" : "false");
  formData.append("min_selection", String(payload.minSelection));
  formData.append("max_selection", String(payload.maxSelection));
  formData.append(
    "modifiers",
    JSON.stringify(
      payload.modifiers.map((modifier) => ({
        name: modifier.name,
        price: modifier.price,
        is_active: modifier.isActive ?? true,
      }))
    )
  );
  if (payload.image) formData.append("group_image", payload.image);
  payload.modifiers.forEach((modifier, index) => {
    if (modifier.image) {
      formData.append(`option_image_${index}`, modifier.image);
    }
  });

  const response = await request("/menu/modifier-groups/", {
    method: "POST",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    required: boolean;
    min_selection: number;
    max_selection: number;
    image?: string | null;
    image_path?: string | null;
    image_url?: string | null;
    modifiers: Array<{ id: number; name: string; price: string; is_active: boolean; image?: string | null; image_path?: string | null; image_url?: string | null }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    required: data.required,
    minSelection: data.min_selection,
    maxSelection: data.max_selection,
    image: data.image ?? null,
    imagePath: data.image_path ?? null,
    imageUrl: normalizeImageUrl(data),
    modifiers: data.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      price: Number(modifier.price),
      isActive: modifier.is_active,
      image: modifier.image ?? null,
      imagePath: modifier.image_path ?? null,
      imageUrl: normalizeImageUrl(modifier),
    })),
  };
};


export const updateModifierGroup = async (
  groupId: number,
  payload: {
    name: string;
    required: boolean;
    minSelection: number;
    maxSelection: number;
    modifiers: Array<{ id?: number; name: string; price: number; isActive?: boolean }>;
  }
): Promise<ModifierGroup> => {
  const response = await request(`/menu/modifier-groups/${groupId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      required: payload.required,
      min_selection: payload.minSelection,
      max_selection: payload.maxSelection,
      modifiers: payload.modifiers.map((modifier) => ({
        ...(modifier.id ? { id: modifier.id } : {}),
        name: modifier.name,
        price: modifier.price,
        is_active: modifier.isActive ?? true,
      })),
    }),
  });
  const data = await handleJson<{
    id: number;
    name: string;
    required: boolean;
    min_selection: number;
    max_selection: number;
    image?: string | null;
    image_path?: string | null;
    image_url?: string | null;
    modifiers: Array<{ id: number; name: string; price: string; is_active: boolean; image?: string | null; image_path?: string | null; image_url?: string | null }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    required: data.required,
    minSelection: data.min_selection,
    maxSelection: data.max_selection,
    image: data.image ?? null,
    imagePath: data.image_path ?? null,
    imageUrl: normalizeImageUrl(data),
    modifiers: data.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      price: Number(modifier.price),
      isActive: modifier.is_active,
      image: modifier.image ?? null,
      imagePath: modifier.image_path ?? null,
      imageUrl: normalizeImageUrl(modifier),
    })),
  };
};

export const uploadModifierGroupImage = async (groupId: number, image: File): Promise<void> => {
  const formData = new FormData();
  formData.append("image", image);
  await request(`/menu/modifier-groups/${groupId}/image/`, {
    method: "PATCH",
    body: formData,
  }).then(handleJson);
};

export const uploadModifierOptionImage = async (optionId: number, image: File): Promise<void> => {
  const formData = new FormData();
  formData.append("image", image);
  await request(`/menu/modifiers/${optionId}/image/`, {
    method: "PATCH",
    body: formData,
  }).then(handleJson);
};


export const deleteModifierGroup = async (groupId: number): Promise<void> => {
  const response = await request(`/menu/modifier-groups/${groupId}/`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    if (response.status === 404) {
      return;
    }
    const data = await response.json().catch(() => ({ detail: "No se pudo eliminar el grupo" }));
    throw new Error(data.detail || "No se pudo eliminar el grupo");
  }
};

export const getDiscounts = async (): Promise<Discount[]> => {
  const response = await request("/menu/discounts/");
  const data = await handleJson<Array<{
    id: number;
    name: string;
    description: string;
    type: Discount["type"];
    value: string;
    applies_to: Discount["appliesTo"];
    target_category_ids_display: number[];
    target_product_ids_display: number[];
    days_of_week: number[];
    start_time: string | null;
    end_time: string | null;
    service_types: string[];
    min_amount: string | null;
    auto_apply: boolean;
    is_active: boolean;
    priority?: number;
    stackable?: boolean;
    bxgy_config?: Record<string, unknown>;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description,
    type: item.type,
    value: Number(item.value),
    appliesTo: item.applies_to,
    targetCategoryIds: item.target_category_ids_display ?? [],
    targetProductIds: item.target_product_ids_display ?? [],
    daysOfWeek: item.days_of_week ?? [],
    startTime: item.start_time ?? undefined,
    endTime: item.end_time ?? undefined,
    serviceTypes: item.service_types ?? [],
    minAmount: item.min_amount ? Number(item.min_amount) : null,
    autoApply: item.auto_apply,
    isActive: item.is_active,
    priority: item.priority ?? 100,
    stackable: Boolean(item.stackable),
    bxgyConfig: item.bxgy_config ?? undefined,
  }));
};

export const getActiveDiscounts = async (params?: {
  serviceType?: string | null;
  subtotal?: number;
}): Promise<Discount[]> => {
  const query = new URLSearchParams();
  if (params?.serviceType) query.set("service_type", params.serviceType);
  if (typeof params?.subtotal === "number") query.set("subtotal", String(params.subtotal));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await request(`/menu/discounts/active/${suffix}`);
  const data = await handleJson<Array<{
    id: number;
    name: string;
    type: Discount["type"];
    value: string;
    scope: Discount["appliesTo"];
    target_category_ids: number[];
    target_product_ids: number[];
    auto_apply: boolean;
    is_active: boolean;
    has_conditions: boolean;
    available_now: boolean;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    type: item.type,
    value: Number(item.value ?? 0),
    appliesTo: item.scope,
    scope: item.scope,
    targetCategoryIds: item.target_category_ids ?? [],
    targetProductIds: item.target_product_ids ?? [],
    autoApply: Boolean(item.auto_apply),
    isActive: Boolean(item.is_active),
    hasConditions: Boolean(item.has_conditions),
    availableNow: Boolean(item.available_now),
  }));
};

export const getServiceTypes = async (): Promise<ServiceType[]> => {
  const response = await request("/core/service-types/");
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean }>>(response);
  return data.map((item) => ({
    id: item.id,
    key: item.key,
    label: item.label,
    isActive: item.is_active,
    sortOrder: item.sort_order ?? 0,
    disposablesEnabled: item.disposables_enabled === true,
  }));
};

export const listOrderTypes = async (): Promise<ServiceType[]> => {
  const response = await request('/core/order-types/');
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean }>>(response);
  return data.map((item) => ({ id: item.id, key: item.key, label: item.label, isActive: item.is_active, sortOrder: item.sort_order ?? 0, disposablesEnabled: item.disposables_enabled === true }));
};

export const createOrderType = async (payload: { key: string; label: string; isActive: boolean; sortOrder: number; disposablesEnabled?: boolean }): Promise<ServiceType> => {
  const response = await request('/core/order-types/', {
    method: 'POST',
    body: JSON.stringify({ key: payload.key, label: payload.label, is_active: payload.isActive, sort_order: payload.sortOrder, disposables_enabled: payload.disposablesEnabled === true }),
  });
  const data = await handleJson<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean }>(response);
  return { id: data.id, key: data.key, label: data.label, isActive: data.is_active, sortOrder: data.sort_order ?? 0, disposablesEnabled: data.disposables_enabled === true };
};

export const updateOrderType = async (id: number, payload: Partial<{ key: string; label: string; isActive: boolean; sortOrder: number; disposablesEnabled: boolean }>): Promise<ServiceType> => {
  const body: Record<string, unknown> = {};
  if (payload.key !== undefined) body.key = payload.key;
  if (payload.label !== undefined) body.label = payload.label;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.sortOrder !== undefined) body.sort_order = payload.sortOrder;
  if (payload.disposablesEnabled !== undefined) body.disposables_enabled = payload.disposablesEnabled;
  const response = await request(`/core/order-types/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
  const data = await handleJson<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean }>(response);
  return { id: data.id, key: data.key, label: data.label, isActive: data.is_active, sortOrder: data.sort_order ?? 0, disposablesEnabled: data.disposables_enabled === true };
};

export const deleteOrderType = async (id: number): Promise<void> => {
  await request(`/core/order-types/${id}/`, { method: 'DELETE' });
};


export const listProductSpecialPrices = async (productId: number): Promise<ProductSpecialPriceRule[]> => {
  const response = await request(`/menu/products/${productId}/special-prices/`);
  const data = await handleJson<Array<{
    id: number;
    product?: number;
    name?: string;
    is_active: boolean;
    priority: number;
    discount_type: "FIXED_PRICE" | "PERCENT_OFF";
    fixed_price?: string | null;
    percent_off?: string | null;
    days_of_week?: number[];
    start_time?: string | null;
    end_time?: string | null;
    start_date?: string | null;
    end_date?: string | null;
    applies_to_all_order_types: boolean;
    order_type_ids?: number[];
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    productId: item.product,
    name: item.name ?? "",
    isActive: item.is_active,
    priority: item.priority ?? 0,
    discountType: item.discount_type,
    fixedPrice: item.fixed_price != null ? Number(item.fixed_price) : null,
    percentOff: item.percent_off != null ? Number(item.percent_off) : null,
    daysOfWeek: item.days_of_week ?? [],
    startTime: item.start_time ?? null,
    endTime: item.end_time ?? null,
    startDate: item.start_date ?? null,
    endDate: item.end_date ?? null,
    appliesToAllOrderTypes: item.applies_to_all_order_types !== false,
    orderTypeIds: item.order_type_ids ?? [],
  }));
};

export const createProductSpecialPrice = async (productId: number, payload: Omit<ProductSpecialPriceRule, "id" | "productId">): Promise<ProductSpecialPriceRule> => {
  const response = await request(`/menu/products/${productId}/special-prices/`, {
    method: "POST",
    body: JSON.stringify({
      name: payload.name ?? "",
      is_active: payload.isActive,
      priority: payload.priority,
      discount_type: payload.discountType,
      fixed_price: payload.fixedPrice,
      percent_off: payload.percentOff,
      days_of_week: payload.daysOfWeek,
      start_time: payload.startTime,
      end_time: payload.endTime,
      start_date: payload.startDate,
      end_date: payload.endDate,
      applies_to_all_order_types: payload.appliesToAllOrderTypes,
      order_type_ids: payload.orderTypeIds,
    }),
  });
  const item = await handleJson<any>(response);
  return {
    id: item.id,
    productId: item.product,
    name: item.name ?? "",
    isActive: item.is_active,
    priority: item.priority ?? 0,
    discountType: item.discount_type,
    fixedPrice: item.fixed_price != null ? Number(item.fixed_price) : null,
    percentOff: item.percent_off != null ? Number(item.percent_off) : null,
    daysOfWeek: item.days_of_week ?? [],
    startTime: item.start_time ?? null,
    endTime: item.end_time ?? null,
    startDate: item.start_date ?? null,
    endDate: item.end_date ?? null,
    appliesToAllOrderTypes: item.applies_to_all_order_types !== false,
    orderTypeIds: item.order_type_ids ?? [],
  };
};

export const updateProductSpecialPrice = async (ruleId: number, payload: Partial<Omit<ProductSpecialPriceRule, "id" | "productId">>): Promise<ProductSpecialPriceRule> => {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.priority !== undefined) body.priority = payload.priority;
  if (payload.discountType !== undefined) body.discount_type = payload.discountType;
  if (payload.fixedPrice !== undefined) body.fixed_price = payload.fixedPrice;
  if (payload.percentOff !== undefined) body.percent_off = payload.percentOff;
  if (payload.daysOfWeek !== undefined) body.days_of_week = payload.daysOfWeek;
  if (payload.startTime !== undefined) body.start_time = payload.startTime;
  if (payload.endTime !== undefined) body.end_time = payload.endTime;
  if (payload.startDate !== undefined) body.start_date = payload.startDate;
  if (payload.endDate !== undefined) body.end_date = payload.endDate;
  if (payload.appliesToAllOrderTypes !== undefined) body.applies_to_all_order_types = payload.appliesToAllOrderTypes;
  if (payload.orderTypeIds !== undefined) body.order_type_ids = payload.orderTypeIds;

  const response = await request(`/menu/special-prices/${ruleId}/`, { method: "PATCH", body: JSON.stringify(body) });
  const item = await handleJson<any>(response);
  return {
    id: item.id,
    productId: item.product,
    name: item.name ?? "",
    isActive: item.is_active,
    priority: item.priority ?? 0,
    discountType: item.discount_type,
    fixedPrice: item.fixed_price != null ? Number(item.fixed_price) : null,
    percentOff: item.percent_off != null ? Number(item.percent_off) : null,
    daysOfWeek: item.days_of_week ?? [],
    startTime: item.start_time ?? null,
    endTime: item.end_time ?? null,
    startDate: item.start_date ?? null,
    endDate: item.end_date ?? null,
    appliesToAllOrderTypes: item.applies_to_all_order_types !== false,
    orderTypeIds: item.order_type_ids ?? [],
  };
};

export const deleteProductSpecialPrice = async (ruleId: number): Promise<void> => {
  await request(`/menu/special-prices/${ruleId}/`, { method: "DELETE" });
};

export const getActiveTaxConfig = async (): Promise<TaxConfig> => {
  if (cachedTaxConfig) return cachedTaxConfig;
  const response = await request("/core/tax-config/active/");
  const data = await handleJson<{ rate: string; tax_included?: boolean }>(response);
  cachedTaxConfig = { rate: Number(data.rate), taxIncluded: data.tax_included !== false };
  return cachedTaxConfig;
};

const mapOrder = (order: {
  id: number;
  order_number: number;
  status: Order["status"];
  customer_name: string;
  customer_id?: number;
  dte_document_type?: "CF" | "CCF" | "SX";
  iva_exempt?: boolean;
  iva_exempt_discount?: string;
  total: string;
  service_type: Order["serviceType"];
  created_at: string;
  items: Array<{
    id: number;
    product_id: number | null;
    product_name_snapshot: string;
    price_snapshot: string;
    unit_price_override?: string | null;
    snapshot_sku_or_code?: string;
    is_custom?: boolean;
    quantity: number;
    assigned_name?: string;
    unit_price_list?: string | null;
    unit_price_special?: string | null;
    unit_price_before_discount?: string;
    discount_amount?: string;
    discount_percent?: string;
    unit_price_final?: string;
    line_total_before_discount?: string;
    line_total_discount?: string;
    line_total_final?: string;
    pricing_metadata?: Record<string, unknown> | null;
    applied_modifiers: Array<{ modifier_name_snapshot: string }>;
  }>;
  payment_status: Order["paymentStatus"];
  financial_status: Order["financialStatus"];
  total_paid: string;
  remaining: string;
  amount_due_cents?: number;
  remaining_cents?: number;
  refund_total: string;
  net_paid: string;
  discount_snapshot?: Record<string, unknown> | null;
  requires_kitchen?: boolean;
  send_to_kitchen?: boolean;
  subtotal_before_discounts?: string;
  subtotal_after_discounts?: string;
  tax_total?: string;
  total_payable?: string;
}): Order => {
  const createdAt = new Date(order.created_at);
  const prepTime = Math.floor((Date.now() - createdAt.getTime()) / 60000);
  const items = Array.isArray(order.items) ? order.items : [];
  return {
    id: order.id,
    orderNumber: order.order_number,
    items: items.map((item) => ({
      id: item.id,
      productName: item.product_name_snapshot,
      productId: item.product_id ?? null,
      isCustom: Boolean(item.is_custom),
      type: item.is_custom ? "manual" : "menu",
      code: item.snapshot_sku_or_code,
      quantity: item.quantity,
      modifiers: Array.isArray(item.applied_modifiers)
        ? item.applied_modifiers.map((modifier) => modifier.modifier_name_snapshot)
        : [],
      price: Number(item.price_snapshot),
      unitPriceList: item.unit_price_list != null ? Number(item.unit_price_list) : null,
      unitPriceSpecial: item.unit_price_special != null ? Number(item.unit_price_special) : null,
      unitPriceBeforeDiscount: Number(item.unit_price_before_discount ?? item.price_snapshot),
      discountAmount: Number(item.discount_amount ?? 0),
      discountPercent: Number(item.discount_percent ?? 0),
      unitPriceFinal: Number(item.unit_price_final ?? item.price_snapshot),
      lineTotalBeforeDiscount: Number(item.line_total_before_discount ?? Number(item.price_snapshot) * item.quantity),
      lineTotalDiscount: Number(item.line_total_discount ?? 0),
      lineTotalFinal: Number(item.line_total_final ?? Number(item.price_snapshot) * item.quantity),
      pricingMetadata: item.pricing_metadata ?? null,
      unitPriceOverride: item.unit_price_override != null ? Number(item.unit_price_override) : null,
      assignedName: item.assigned_name || undefined,
    })),
    total: Number(order.total),
    status: order.status,
    serviceType: order.service_type,
    createdAt,
    prepTime,
    customerName: order.customer_name || undefined,
    customerId: order.customer_id ?? undefined,
    dteDocumentType: order.dte_document_type ?? "CF",
    ivaExempt: Boolean(order.iva_exempt),
    ivaExemptDiscount: Number(order.iva_exempt_discount ?? 0),
    paymentStatus: order.payment_status,
    financialStatus: order.financial_status,
    totalPaid: Number(order.total_paid ?? 0),
    remaining: Number(order.remaining ?? 0),
    amountDueCents:
      order.amount_due_cents !== undefined && order.amount_due_cents !== null
        ? Number(order.amount_due_cents)
        : toCents(Number(order.total_payable ?? order.total ?? 0)),
    remainingCents:
      order.remaining_cents !== undefined && order.remaining_cents !== null
        ? Number(order.remaining_cents)
        : toCents(Number(order.remaining ?? 0)),
    refundTotal: Number(order.refund_total ?? 0),
    netPaid: Number(order.net_paid ?? 0),
    discountSnapshot: order.discount_snapshot ?? null,
    requiresKitchen: Boolean(order.requires_kitchen),
    sendToKitchen: Boolean(order.send_to_kitchen),
    subtotalBeforeDiscounts: Number(order.subtotal_before_discounts ?? order.total),
    subtotalAfterDiscounts: Number(order.subtotal_after_discounts ?? order.total),
    taxTotal: Number(order.tax_total ?? 0),
    totalPayable: Number(order.total_payable ?? order.total),
  };
};

export const createOrder = async (payload: {
  serviceType: Order["serviceType"];
  customerName?: string;
  customerId?: number;
  dteDocumentType?: "CF" | "CCF" | "SX";
  ivaExempt?: boolean;
  source?: "kiosk" | "pos";
  channel?: "kiosk" | "pos";
  priceChangePin?: string;
  discountId?: number;
  discountMode?: "manual" | "auto";
  sendToKitchen?: boolean;
  items: Array<{
    productId?: number | null;
    productName: string;
    price: number;
    quantity: number;
    isCustom?: boolean;
    type?: "menu" | "manual";
    unitPriceOverride?: number | null;
    customCode?: string;
    modifiers: Array<{ id?: number; name: string; price: number }>;
    assignedName?: string;
  }>;
}): Promise<Order> => {
  const response = await request("/orders/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      service_type_key: payload.serviceType,
      customer_name: payload.customerName ?? "",
      customer_id: payload.customerId,
      dte_document_type: payload.dteDocumentType ?? "CF",
      iva_exempt: Boolean(payload.ivaExempt),
      source: payload.source,
      channel: payload.channel,
      fast_pos_mode: payload.channel === "pos",
      price_change_pin: payload.priceChangePin ?? "",
      manual_discount_id: payload.discountId ?? undefined,
      discount_id: payload.discountId ?? undefined,
      discount_mode: payload.discountMode ?? undefined,
      send_to_kitchen: Boolean(payload.sendToKitchen),
      ...(localStorage.getItem("selected_branch_id") ? { branch_id: Number(localStorage.getItem("selected_branch_id")) } : {}),
      items: payload.items.map((item) => ({
        type: item.isCustom ? "MANUAL" : "MENU",
        product_id: item.isCustom ? undefined : (item.productId ?? null),
        is_custom: Boolean(item.isCustom),
        manual_name: item.isCustom ? item.productName : undefined,
        custom_name: item.isCustom ? item.productName : undefined,
        manual_unit_price: item.isCustom ? item.price : undefined,
        unit_price: item.isCustom ? item.price : undefined,
        unit_price_override: item.unitPriceOverride ?? undefined,
        custom_code: item.isCustom ? item.customCode : undefined,
        product_name_snapshot: item.productName,
        price_snapshot: item.price,
        quantity: item.quantity,
        assigned_name: item.assignedName?.trim() || "",
        modifiers: item.modifiers.map((modifier) => ({
          id: modifier.id,
          name: modifier.name,
          price: modifier.price,
        })),
      })),
    }),
  });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("text/html")) {
      throw new Error("Error al crear orden. Revisa backend logs.");
    }
  }
  const data = await handleJson<{
    id: number;
    order_number: number;
    status: Order["status"];
    customer_name: string;
    total: string;
    service_type: Order["serviceType"];
    created_at: string;
    payment_status: Order["paymentStatus"];
    total_paid: string;
    remaining: string;
    items: Array<{
      id: number;
      product_id: number | null;
      product_name_snapshot: string;
      price_snapshot: string;
      unit_price_override?: string | null;
      snapshot_sku_or_code?: string;
      is_custom?: boolean;
      quantity: number;
      applied_modifiers: Array<{ modifier_name_snapshot: string }>;
    }>;
  }>(response);
  if (import.meta.env.DEV) {
    console.debug("[API] createOrder raw response", data);
  }
  return mapOrder(data);
};

export const validateOrderPricePin = async (pin: string): Promise<void> => {
  const response = await request("/auth/authorize-price-change/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  const data = await handleJson<{ ok?: boolean; detail?: string }>(response);
  if (!data?.ok) {
    throw new Error("Código inválido");
  }
};

export const getActiveOrders = async (params?: { branchId?: number | string; serviceType?: string }): Promise<Order[]> => {
  const qs = new URLSearchParams();
  if (params?.branchId) qs.set("branch_id", String(params.branchId));
  if (params?.serviceType) qs.set("service_type", params.serviceType);
  const response = await request(`/orders/kitchen/${qs.toString() ? `?${qs.toString()}` : ""}`);
  const data = await handleJson<
    Array<{
      id: number;
      order_number: number;
      status: Order["status"];
      customer_name: string;
      total: string;
      service_type: Order["serviceType"];
      created_at: string;
      payment_status: Order["paymentStatus"];
      financial_status: Order["financialStatus"];
      total_paid: string;
      remaining: string;
      refund_total: string;
      net_paid: string;
      items: Array<{
        id: number;
        product_id: number | null;
        product_name_snapshot: string;
        price_snapshot: string;
        snapshot_sku_or_code?: string;
        is_custom?: boolean;
        quantity: number;
        applied_modifiers: Array<{ modifier_name_snapshot: string }>;
      }>;
    }>
  >(response);
  return Array.isArray(data) ? data.map(mapOrder) : [];
};

export const updateOrderStatus = async (orderId: number, statusValue: Order["status"]): Promise<Order> => {
  const response = await request(`/orders/${orderId}/status/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: statusValue }),
  });
  const data = await handleJson<{
    id: number;
    order_number: number;
    status: Order["status"];
    customer_name: string;
    total: string;
    service_type: Order["serviceType"];
    created_at: string;
    payment_status: Order["paymentStatus"];
    financial_status: Order["financialStatus"];
    total_paid: string;
    remaining: string;
    refund_total: string;
    net_paid: string;
    items: Array<{
      id: number;
      product_id: number | null;
      product_name_snapshot: string;
      price_snapshot: string;
      snapshot_sku_or_code?: string;
      is_custom?: boolean;
      quantity: number;
      applied_modifiers: Array<{ modifier_name_snapshot: string }>;
    }>;
  }>(response);
  return mapOrder(data);
};

export const setOrderSendToKitchen = async (orderId: number, sendToKitchen: boolean): Promise<Order> => {
  const response = await request(`/orders/${orderId}/send-to-kitchen/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ send_to_kitchen: sendToKitchen }),
  });
  const data = await handleJson(response);
  return mapOrder(data);
};

export const getOrderById = async (orderId: number): Promise<Order> => {
  const response = await request(`/orders/${orderId}/`);
  const data = await handleJson<{
    id: number;
    order_number: number;
    status: Order["status"];
    customer_name: string;
    total: string;
    service_type: Order["serviceType"];
    created_at: string;
    payment_status: Order["paymentStatus"];
    financial_status: Order["financialStatus"];
    total_paid: string;
    remaining: string;
    refund_total: string;
    net_paid: string;
    items: Array<{
      id: number;
      product_id: number;
      product_name_snapshot: string;
      price_snapshot: string;
      quantity: number;
      applied_modifiers: Array<{ modifier_name_snapshot: string }>;
    }>;
  }>(response);
  return mapOrder(data);
};

export const updateOrderCustomerDte = async (
  orderId: number,
  payload: { customerId: number; dteDocumentType: "CF" | "CCF" | "SX"; ivaExempt?: boolean }
): Promise<Order> => {
  const response = await request(`/orders/${orderId}/`, {
    method: "PATCH",
    body: JSON.stringify({
      customer_id: payload.customerId,
      dte_document_type: payload.dteDocumentType,
      iva_exempt: Boolean(payload.ivaExempt),
    }),
  });
  const data = await handleJson<Parameters<typeof mapOrder>[0]>(response);
  return mapOrder(data);
};

export const getCustomerOrders = async (
  signal?: AbortSignal,
  params?: { branchId?: number | string; serviceType?: string }
): Promise<Array<{ id: number; orderNumber: number; status: "preparing" | "ready"; customerName?: string; createdAt: Date }>> => {
  const qs = new URLSearchParams();
  if (params?.branchId) qs.set("branch_id", String(params.branchId));
  if (params?.serviceType) qs.set("service_type", params.serviceType);
  const response = await request(`/orders/customer-display/${qs.toString() ? `?${qs.toString()}` : ""}`, { signal });
  const raw = await handleJson<
    | Array<{ id: number; order_number: number; status: string; customer_name?: string | null; created_at: string }>
    | { results?: Array<{ id: number; order_number: number; status: string; customer_name?: string | null; created_at: string }> }
  >(response);
  const list = Array.isArray(raw) ? raw : raw.results ?? [];
  return list
    .map((order) => {
      const normalizedStatus = String(order.status || "").toLowerCase();
      if (normalizedStatus !== "preparing" && normalizedStatus !== "ready") {
        return null;
      }
      return {
        id: order.id,
        orderNumber: order.order_number,
        status: normalizedStatus,
        customerName: order.customer_name || undefined,
        createdAt: new Date(order.created_at),
      };
    })
    .filter((order): order is { id: number; orderNumber: number; status: "preparing" | "ready"; customerName?: string; createdAt: Date } => Boolean(order));
};

export const duplicateProduct = async (productId: number): Promise<Product> => {
  const response = await request(`/menu/products/${productId}/duplicate/`, { method: "POST" });
  const data = await handleJson<any>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    sortOrder: Number(data.sort_order ?? 0),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? data.category_id,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    disposableFee: Number(data.disposable_fee ?? 0),
    disposableApplyTo: Array.isArray(data.disposable_apply_to) ? data.disposable_apply_to : [],
    requiresKitchen: Boolean(data.requires_kitchen),
    modifierGroups: data.modifier_groups ?? [],
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link: any) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
  };
};

export const getSalesReport = async (filters?: {
  dateFrom?: string;
  dateTo?: string;
  serviceType?: Order["serviceType"];
  paymentMethod?: string;
  status?: Order["status"];
  search?: string;
  today?: boolean;
}): Promise<{ rows: SalesReportRow[]; aggregates: SalesReportAggregates }> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.serviceType) params.set("service_type", filters.serviceType);
  if (filters?.paymentMethod) params.set("payment_method", filters.paymentMethod);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.search) {
    params.set("search", filters.search);
    params.set("q", filters.search);
  }
  if (filters?.today) params.set("today", "1");
  const query = params.toString();
  const response = await request(`/reports/sales/${query ? `?${query}` : ""}`);
  const data = await handleJson<{
    results: Array<{
      payment_id: number;
      order_id: number;
      order_number: number;
      service_type_code: string;
      service_type_label: string;
      created_at: string;
      total_amount: string;
      status: Order["status"];
      customer_name?: string;
      control_number?: string;
      payment_method_code?: string;
      payment_method_label?: string;
      financial_status?: Order["financialStatus"];
    }>;
    aggregates: {
      count_orders: number;
      sum_subtotal: string;
      sum_tax: string;
      sum_total: string;
      sum_discount_total: string;
      gross_total?: string;
      refund_total?: string;
      net_total?: string;
      payment_methods?: {
        cash: string;
        card?: string;
        card_debit?: string;
        card_credit?: string;
        transfer: string;
        pedidos_ya: string;
        paypal: string;
      };
      tips_total?: string;
      tips_net?: string;
      cash_total?: string;
      non_cash_total?: string;
      refunds_count?: number;
      orders_paid?: number;
      orders_voided?: number;
      refunds_by_method?: {
        cash: string;
        card: string;
        transfer: string;
      };
    };
  }>(response);
  return {
    rows: data.results.map((row) => ({
      paymentId: row.payment_id,
      orderId: row.order_id,
      orderNumber: row.order_number,
      serviceType: row.service_type_code,
      serviceTypeLabel: row.service_type_label,
      createdAt: new Date(row.created_at),
      total: Number(row.total_amount),
      status: row.status,
      customerName: String(row.customer_name ?? ""),
      controlNumber: String(row.control_number ?? ""),
      paymentMethodCode: String(row.payment_method_code ?? ""),
      paymentMethodLabel: String(row.payment_method_label ?? ""),
      financialStatus: row.financial_status ?? "paid",
    })),
    aggregates: {
      countOrders: data.aggregates.count_orders,
      sumTotal: Number(data.aggregates.sum_total),
      sumSubtotal: 0,
      sumTax: 0,
      sumDiscountTotal: 0,
      grossTotal: Number(data.aggregates.sum_total ?? 0),
      refundTotal: Number(data.aggregates.refund_total ?? 0),
      netTotal: Number(data.aggregates.net_total ?? 0),
      paymentMethods: {
        cash: Number(data.aggregates.payment_methods?.cash ?? 0),
        card: fromCents(
          toCents(data.aggregates.payment_methods?.card ?? 0)
          + toCents(data.aggregates.payment_methods?.card_debit ?? 0)
          + toCents(data.aggregates.payment_methods?.card_credit ?? 0)
        ),
        transfer: Number(data.aggregates.payment_methods?.transfer ?? 0),
      },
      tipsTotal: Number(data.aggregates.tips_total ?? 0),
      tipsNet: Number(data.aggregates.tips_net ?? 0),
      cashTotal: Number(data.aggregates.cash_total ?? 0),
      nonCashTotal: Number(data.aggregates.non_cash_total ?? 0),
      refundsCount: data.aggregates.refunds_count ?? 0,
      ordersPaid: data.aggregates.orders_paid ?? 0,
      ordersVoided: data.aggregates.orders_voided ?? 0,
      refundsByMethod: {
        cash: Number(data.aggregates.refunds_by_method?.cash ?? 0),
        card: Number(data.aggregates.refunds_by_method?.card ?? 0),
        transfer: Number(data.aggregates.refunds_by_method?.transfer ?? 0),
      },
    },
  };
};

const bucketDate = (date: Date, granularity: ReportsGranularity): string => {
  if (granularity === "hours") return date.getHours().toString().padStart(2, "0") + ":00";
  if (granularity === "week") {
    const day = date.toLocaleDateString("es-SV", { weekday: "short" });
    return day.charAt(0).toUpperCase() + day.slice(1);
  }
  if (granularity === "month") return `${date.getDate().toString().padStart(2, "0")}/${(date.getMonth() + 1).toString().padStart(2, "0")}`;
  return date.toLocaleDateString("es-SV", { month: "short", year: "2-digit" });
};

const buildSeries = (rows: SalesReportRow[], granularity: ReportsGranularity): Map<string, { total: number; tx: number }> => {
  const map = new Map<string, { total: number; tx: number }>();
  for (const row of rows) {
    const bucket = bucketDate(row.createdAt, granularity);
    const current = map.get(bucket) ?? { total: 0, tx: 0 };
    current.total += row.total;
    current.tx += 1;
    map.set(bucket, current);
  }
  return map;
};

export const getSalesTimeseries = async (filters: {
  dateFrom: string;
  dateTo: string;
  granularity: ReportsGranularity;
  compareWith?: ReportsComparisonMode;
  compareDateFrom?: string;
  compareDateTo?: string;
  categoryIds?: string[];
  productIds?: string[];
  modifierIds?: string[];
  serviceTypes?: string[];
  paymentMethods?: string[];
  signal?: AbortSignal;
}): Promise<SalesTimeseriesResponse> => {
  const params = new URLSearchParams({
    start: filters.dateFrom,
    end: filters.dateTo,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    granularity: filters.granularity,
    group_by: filters.granularity === "hours" ? "hour" : filters.granularity,
    compare_with: filters.compareWith ?? "none",
    compare: filters.compareWith ?? "none",
  });
  if (filters.categoryIds?.length) params.set("category_ids", filters.categoryIds.join(","));
  if (filters.productIds?.length) params.set("product_ids", filters.productIds.join(","));
  if (filters.modifierIds?.length) params.set("modifier_ids", filters.modifierIds.join(","));
  if (filters.serviceTypes?.length) params.set("service_types", filters.serviceTypes.join(","));
  if (filters.paymentMethods?.length) params.set("payment_methods", filters.paymentMethods.join(","));
  if (filters.compareDateFrom) params.set("compare_date_from", filters.compareDateFrom);
  if (filters.compareDateTo) params.set("compare_date_to", filters.compareDateTo);

  const response = await request(`/reports/sales-timeseries/?${params.toString()}`, { signal: filters.signal });
  if (response.ok) {
    const payload = await handleJson<{
      series?: Array<{ key: string; total: string | number }>;
      compare?: { series?: Array<{ key: string; total: string | number }> } | null;
      kpis?: { total?: string | number; count?: number; avg_ticket?: string | number };
      compare_kpis?: { total?: string | number; count?: number; avg_ticket?: string | number };
    }>(response);
    const comparisonMap = new Map((payload.compare?.series ?? []).map((point) => [point.key, Number(point.total ?? 0)]));
    const points = (payload.series ?? []).map((point) => ({
      bucket: point.key,
      currentTotal: Number(point.total ?? 0),
      comparisonTotal: comparisonMap.get(point.key) ?? 0,
    }));
    return {
      points,
      current: {
        totalSales: Number(payload.kpis?.total ?? 0),
        transactions: Number(payload.kpis?.count ?? 0),
        avgTicket: Number(payload.kpis?.avg_ticket ?? 0),
      },
      comparison: payload.compare
        ? {
          totalSales: Number(payload.compare_kpis?.total ?? 0),
          transactions: Number(payload.compare_kpis?.count ?? 0),
          avgTicket: Number(payload.compare_kpis?.avg_ticket ?? 0),
        }
        : null,
    };
  }

  const currentReport = await getSalesReport({ dateFrom: filters.dateFrom, dateTo: filters.dateTo });
  const comparisonReport =
    filters.compareWith && filters.compareWith !== "none" && filters.compareDateFrom && filters.compareDateTo
      ? await getSalesReport({ dateFrom: filters.compareDateFrom, dateTo: filters.compareDateTo })
      : null;

  const currentSeries = buildSeries(currentReport.rows, filters.granularity);
  const comparisonSeries = comparisonReport ? buildSeries(comparisonReport.rows, filters.granularity) : new Map<string, { total: number; tx: number }>();
  const keys = Array.from(new Set([...currentSeries.keys(), ...comparisonSeries.keys()]));
  const points = keys.map((bucket) => ({
    bucket,
    currentTotal: currentSeries.get(bucket)?.total ?? 0,
    comparisonTotal: comparisonSeries.get(bucket)?.total ?? 0,
  }));
  return {
    points,
    current: {
      totalSales: currentReport.aggregates.netTotal || currentReport.aggregates.sumTotal,
      transactions: currentReport.aggregates.countOrders,
      avgTicket: currentReport.aggregates.countOrders > 0 ? (currentReport.aggregates.netTotal || currentReport.aggregates.sumTotal) / currentReport.aggregates.countOrders : 0,
    },
    comparison: comparisonReport
      ? {
          totalSales: comparisonReport.aggregates.netTotal || comparisonReport.aggregates.sumTotal,
          transactions: comparisonReport.aggregates.countOrders,
          avgTicket:
            comparisonReport.aggregates.countOrders > 0
              ? (comparisonReport.aggregates.netTotal || comparisonReport.aggregates.sumTotal) / comparisonReport.aggregates.countOrders
              : 0,
        }
      : null,
  };
};

export const getSalesBreakdown = async (filters: {
  dateFrom: string;
  dateTo: string;
  dimension: SalesBreakdownDimension;
  compareWith?: ReportsComparisonMode;
  categoryIds?: string[];
  productIds?: string[];
  modifierIds?: string[];
  serviceTypes?: string[];
  paymentMethods?: string[];
  signal?: AbortSignal;
}): Promise<SalesBreakdownRow[]> => {
  const params = new URLSearchParams({
    start: filters.dateFrom,
    end: filters.dateTo,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    dimension: filters.dimension === "service_type" ? "order_type" : filters.dimension,
    compare: filters.compareWith ?? "none",
    compare_with: filters.compareWith ?? "none",
  });
  if (filters.categoryIds?.length) params.set("category_ids", filters.categoryIds.join(","));
  if (filters.productIds?.length) params.set("product_ids", filters.productIds.join(","));
  if (filters.modifierIds?.length) params.set("modifier_ids", filters.modifierIds.join(","));
  if (filters.serviceTypes?.length) params.set("service_types", filters.serviceTypes.join(","));
  if (filters.paymentMethods?.length) params.set("payment_methods", filters.paymentMethods.join(","));
  const response = await request(`/reports/sales-breakdown/?${params.toString()}`, { signal: filters.signal });
  if (response.ok) {
    const payload = await handleJson<{ items?: Array<{ id: string | number; name: string; total: string | number; pct: number; count: number }> }>(response);
    return (payload.items ?? []).map((item) => ({
      key: String(item.id),
      label: item.name,
      total: Number(item.total ?? 0),
      percentage: Number(item.pct ?? 0) * 100,
      transactions: Number(item.count ?? 0),
    }));
  }

  const report = await getSalesReport({ dateFrom: filters.dateFrom, dateTo: filters.dateTo });
  const total = report.aggregates.netTotal || report.aggregates.sumTotal || 0;
  const grouped = new Map<string, SalesBreakdownRow>();
  for (const row of report.rows) {
    const key =
      filters.dimension === "payment_method"
        ? row.paymentMethodCode || "unknown"
        : filters.dimension === "service_type"
          ? row.serviceType || "unknown"
          : "n/a";
    const label =
      filters.dimension === "payment_method"
        ? row.paymentMethodLabel || "Desconocido"
        : filters.dimension === "service_type"
          ? row.serviceTypeLabel || String(row.serviceType || "Desconocido")
          : "Disponible con endpoint de agregación";
    const current = grouped.get(key) ?? { key, label, total: 0, percentage: 0, transactions: 0 };
    current.total += row.total;
    current.transactions += 1;
    grouped.set(key, current);
  }
  return Array.from(grouped.values())
    .map((entry) => ({ ...entry, percentage: total > 0 ? (entry.total / total) * 100 : 0 }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);
};

export const changeInternalPaymentMethod = async (
  paymentId: number,
  payload: { paymentMethodCode: string; reason?: string }
): Promise<{ paymentMethodCode: string; paymentMethodName: string }> => {
  const response = await request(`/payments/${paymentId}/internal-payment-method/`, {
    method: "PATCH",
    body: JSON.stringify({
      payment_method_code: payload.paymentMethodCode,
      reason: payload.reason ?? "",
    }),
  });
  const data = await handleJson<{ payment_method_code: string; payment_method_name: string }>(response);
  return {
    paymentMethodCode: data.payment_method_code,
    paymentMethodName: data.payment_method_name,
  };
};

export const createDiscount = async (payload: Discount): Promise<Discount> => {
  const response = await request("/menu/discounts/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? "",
      type: payload.type,
      value: payload.value,
      applies_to: payload.appliesTo,
      target_category_ids: payload.targetCategoryIds ?? [],
      target_product_ids: payload.targetProductIds ?? [],
      days_of_week: payload.daysOfWeek ?? [],
      start_time: payload.startTime ?? null,
      end_time: payload.endTime ?? null,
      service_types: payload.serviceTypes ?? [],
      min_amount: payload.minAmount ?? null,
      auto_apply: payload.autoApply,
      is_active: payload.isActive,
      priority: payload.priority ?? 100,
      stackable: payload.stackable ?? false,
      bxgy_config: payload.bxgyConfig ?? {},
    }),
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    type: Discount["type"];
    value: string;
    applies_to: Discount["appliesTo"];
    target_category_ids_display: number[];
    target_product_ids_display: number[];
    days_of_week: number[];
    start_time: string | null;
    end_time: string | null;
    service_types: string[];
    min_amount: string | null;
    auto_apply: boolean;
    is_active: boolean;
    priority?: number;
    stackable?: boolean;
    bxgy_config?: Record<string, unknown>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    type: data.type,
    value: Number(data.value),
    appliesTo: data.applies_to,
    targetCategoryIds: data.target_category_ids_display ?? [],
    targetProductIds: data.target_product_ids_display ?? [],
    daysOfWeek: data.days_of_week ?? [],
    startTime: data.start_time ?? undefined,
    endTime: data.end_time ?? undefined,
    serviceTypes: data.service_types ?? [],
    minAmount: data.min_amount ? Number(data.min_amount) : null,
    autoApply: data.auto_apply,
    isActive: data.is_active,
    priority: data.priority ?? 100,
    stackable: Boolean(data.stackable),
    bxgyConfig: data.bxgy_config ?? undefined,
  };
};

export const updateDiscount = async (discountId: number, payload: Discount): Promise<Discount> => {
  const response = await request(`/menu/discounts/${discountId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? "",
      type: payload.type,
      value: payload.value,
      applies_to: payload.appliesTo,
      target_category_ids: payload.targetCategoryIds ?? [],
      target_product_ids: payload.targetProductIds ?? [],
      days_of_week: payload.daysOfWeek ?? [],
      start_time: payload.startTime ?? null,
      end_time: payload.endTime ?? null,
      service_types: payload.serviceTypes ?? [],
      min_amount: payload.minAmount ?? null,
      auto_apply: payload.autoApply,
      is_active: payload.isActive,
      priority: payload.priority ?? 100,
      stackable: payload.stackable ?? false,
      bxgy_config: payload.bxgyConfig ?? {},
    }),
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    type: Discount["type"];
    value: string;
    applies_to: Discount["appliesTo"];
    target_category_ids_display: number[];
    target_product_ids_display: number[];
    days_of_week: number[];
    start_time: string | null;
    end_time: string | null;
    service_types: string[];
    min_amount: string | null;
    auto_apply: boolean;
    is_active: boolean;
    priority?: number;
    stackable?: boolean;
    bxgy_config?: Record<string, unknown>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    type: data.type,
    value: Number(data.value),
    appliesTo: data.applies_to,
    targetCategoryIds: data.target_category_ids_display ?? [],
    targetProductIds: data.target_product_ids_display ?? [],
    daysOfWeek: data.days_of_week ?? [],
    startTime: data.start_time ?? undefined,
    endTime: data.end_time ?? undefined,
    serviceTypes: data.service_types ?? [],
    minAmount: data.min_amount ? Number(data.min_amount) : null,
    autoApply: data.auto_apply,
    isActive: data.is_active,
    priority: data.priority ?? 100,
    stackable: Boolean(data.stackable),
    bxgyConfig: data.bxgy_config ?? undefined,
  };
};

export const deleteDiscount = async (discountId: number): Promise<void> => {
  const response = await request(`/menu/discounts/${discountId}/`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    const body = await response.text().catch(() => "");
    throw new Error(body || "No se pudo eliminar el descuento");
  }
};

const ROLE_LABELS: Record<string, string> = {
  cashier: "Cajero",
  kitchen: "Cocina",
  manager: "Gerente",
  admin: "Administrador",
  kiosk: "Kiosk",
  worker: "Worker",
};

const ROLE_KEYS: Record<string, string> = Object.entries(ROLE_LABELS).reduce(
  (acc, [key, label]) => {
    acc[label.toLowerCase()] = key;
    acc[key.toLowerCase()] = key;
    return acc;
  },
  {} as Record<string, string>
);

const resolveRoleKey = (role: string) => {
  const normalized = role.trim().toLowerCase();
  return ROLE_KEYS[normalized];
};

const mapEmployeeRoleLabel = (roleKey: string) => ROLE_LABELS[roleKey] ?? roleKey;

export const getEmployees = async (filters?: {
  search?: string;
  role?: string;
  status?: "active" | "inactive";
}): Promise<import("@/types/employee").Employee[]> => {
  const params = new URLSearchParams();
  if (filters?.search) {
    params.append("search", filters.search);
  }
  if (filters?.role) {
    const roleKey = resolveRoleKey(filters.role) ?? filters.role;
    params.append("role", roleKey);
  }
  if (filters?.status) {
    params.append("status", filters.status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await request(`/employees/${suffix}`);
  const data = await handleJson<Array<{
    id: number;
    full_name: string;
    email: string | null;
    phone: string;
    role: string;
    branch_name: string | null;
    status: "active" | "inactive";
    user_id?: number | null;
    user_username?: string | null;
    user_email?: string | null;
    user_role?: string | null;
    has_user?: boolean;
    days_worked: number;
    hours_worked: string;
    late_arrivals: number;
  }>>(response);
  return data.map((item) => ({
    id: String(item.id),
    name: item.full_name,
    email: item.email ?? "",
    role: mapEmployeeRoleLabel(item.role),
    phone: item.phone ?? "",
    branch: item.branch_name ?? "",
    status: item.status,
    hasUser: item.has_user ?? Boolean(item.user_id),
    userId: item.user_id ? String(item.user_id) : null,
    userUsername: item.user_username ?? "",
    userEmail: item.user_email ?? "",
    userRole: item.user_role ? mapEmployeeRoleLabel(item.user_role) : "",
    daysWorked: item.days_worked ?? 0,
    hoursWorked: Number(item.hours_worked ?? 0),
    lateArrivals: item.late_arrivals ?? 0,
  }));
};

type EmployeePayload = Omit<
  import("@/types/employee").Employee,
  "id" | "daysWorked" | "hoursWorked" | "lateArrivals" | "hasUser"
>;

export const createEmployee = async (
  payload: EmployeePayload & {
    createUser?: boolean;
    user?: {
      username: string;
      email?: string;
      password: string;
      role: string;
    };
  }
): Promise<import("@/types/employee").Employee> => {
  const roleKey = resolveRoleKey(payload.role);
  if (!roleKey) {
    throw new Error("Rol inválido. Usa Cajero, Cocinero, Gerente o Administrador.");
  }
  const userRoleKey = payload.user?.role ? resolveRoleKey(payload.user.role) : undefined;
  if (payload.user?.role && !userRoleKey) {
    throw new Error("Rol de usuario inválido. Usa Administrador, Gerente, Cajero o Cocinero.");
  }
  const response = await request("/employees/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      full_name: payload.name,
      role: roleKey,
      status: payload.status ?? "active",
      create_user: payload.createUser ?? false,
      user: payload.user
        ? {
            username: payload.user.username,
            password: payload.user.password,
            role: userRoleKey ?? payload.user.role,
          }
        : undefined,
    }),
  });
  const data = await handleJson<{
    id: number;
    full_name: string;
    email: string | null;
    phone: string;
    role: string;
    branch_name: string | null;
    status: "active" | "inactive";
    user_id?: number | null;
    user_username?: string | null;
    user_email?: string | null;
    user_role?: string | null;
    has_user?: boolean;
    days_worked: number;
    hours_worked: string;
    late_arrivals: number;
  }>(response);
  return {
    id: String(data.id),
    name: data.full_name,
    email: data.email ?? "",
    role: mapEmployeeRoleLabel(data.role),
    phone: data.phone ?? "",
    branch: data.branch_name ?? payload.branch,
    status: data.status,
    hasUser: data.has_user ?? Boolean(data.user_id),
    userId: data.user_id ? String(data.user_id) : null,
    userUsername: data.user_username ?? "",
    userEmail: data.user_email ?? "",
    userRole: data.user_role ? mapEmployeeRoleLabel(data.user_role) : "",
    daysWorked: data.days_worked ?? 0,
    hoursWorked: Number(data.hours_worked ?? 0),
    lateArrivals: data.late_arrivals ?? 0,
  };
};

export const updateEmployee = async (
  id: string,
  payload: Partial<import("@/types/employee").Employee> & {
    createUser?: boolean;
    user?: {
      username?: string;
      email?: string;
      password?: string;
      role?: string;
    };
  }
): Promise<import("@/types/employee").Employee> => {
  const roleKey = payload.role ? resolveRoleKey(payload.role) : undefined;
  if (payload.role && !roleKey) {
    throw new Error("Rol inválido. Usa Cajero, Cocinero, Gerente o Administrador.");
  }
  const userRoleKey = payload.user?.role ? resolveRoleKey(payload.user.role) : undefined;
  if (payload.user?.role && !userRoleKey) {
    throw new Error("Rol de usuario inválido. Usa Administrador, Gerente, Cajero o Cocinero.");
  }
  const response = await request(`/employees/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(payload.name !== undefined ? { full_name: payload.name } : {}),
      ...(roleKey ? { role: roleKey } : {}),
      ...(payload.status !== undefined ? { status: payload.status } : {}),
      ...(payload.createUser !== undefined ? { create_user: payload.createUser } : {}),
      ...(payload.user
        ? {
            user: {
              ...(payload.user.username !== undefined ? { username: payload.user.username } : {}),
              ...(payload.user.password ? { password: payload.user.password } : {}),
              ...(payload.user.role ? { role: userRoleKey ?? payload.user.role } : {}),
            },
          }
        : {}),
    }),
  });
  const data = await handleJson<{
    id: number;
    full_name: string;
    email: string | null;
    phone: string;
    role: string;
    branch_name: string | null;
    status: "active" | "inactive";
    user_id?: number | null;
    user_username?: string | null;
    user_email?: string | null;
    user_role?: string | null;
    has_user?: boolean;
    days_worked: number;
    hours_worked: string;
    late_arrivals: number;
  }>(response);
  return {
    id: String(data.id),
    name: data.full_name,
    email: data.email ?? "",
    role: mapEmployeeRoleLabel(data.role),
    phone: data.phone ?? "",
    branch: data.branch_name ?? payload.branch ?? "",
    status: data.status,
    hasUser: data.has_user ?? Boolean(data.user_id),
    userId: data.user_id ? String(data.user_id) : null,
    userUsername: data.user_username ?? "",
    userEmail: data.user_email ?? "",
    userRole: data.user_role ? mapEmployeeRoleLabel(data.user_role) : "",
    daysWorked: data.days_worked ?? 0,
    hoursWorked: Number(data.hours_worked ?? 0),
    lateArrivals: data.late_arrivals ?? 0,
  };
};

export const getAttendance = async (filters?: {
  dateFrom?: string;
  dateTo?: string;
  employeeId?: string;
}): Promise<
  Array<{
    id: number;
    employeeId: string;
    employeeName: string;
    role: string;
    date: string;
    checkIn?: string | null;
    checkOut?: string | null;
    minutesLate: number;
    notes?: string;
  }>
> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.append("date_from", filters.dateFrom);
  if (filters?.dateTo) params.append("date_to", filters.dateTo);
  if (filters?.employeeId) params.append("employee_id", filters.employeeId);
  const response = await request(`/employees/attendance/?${params.toString()}`);
  const data = await handleJson<Array<{
    id: number;
    employee: number;
    employee_name: string;
    role: string;
    date: string;
    check_in: string | null;
    check_out: string | null;
    minutes_late: number;
    notes: string;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    employeeId: String(item.employee),
    employeeName: item.employee_name,
    role: mapEmployeeRoleLabel(item.role),
    date: item.date,
    checkIn: item.check_in,
    checkOut: item.check_out,
    minutesLate: item.minutes_late ?? 0,
    notes: item.notes ?? "",
  }));
};

const buildDateTime = (date: string, time: string) => {
  if (!date || !time) return null;
  return `${date}T${time}:00`;
};

export const createAttendance = async (payload: {
  employeeId: string;
  date: string;
  entryTime?: string;
  exitTime?: string;
  minutesLate?: number;
  notes?: string;
}) => {
  const response = await request("/employees/attendance/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      employee: Number(payload.employeeId),
      date: payload.date,
      check_in: payload.entryTime ? buildDateTime(payload.date, payload.entryTime) : null,
      check_out: payload.exitTime ? buildDateTime(payload.date, payload.exitTime) : null,
      minutes_late: payload.minutesLate ?? 0,
      notes: payload.notes ?? "",
    }),
  });
  return handleJson(response);
};

export const updateAttendance = async (
  id: number,
  payload: {
    entryTime?: string;
    exitTime?: string;
    minutesLate?: number;
    notes?: string;
    date?: string;
  }
) => {
  if ((payload.entryTime || payload.exitTime) && !payload.date) {
    throw new Error("Fecha requerida para actualizar horas de asistencia.");
  }
  const response = await request(`/employees/attendance/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(payload.date ? { date: payload.date } : {}),
      ...(payload.entryTime && payload.date
        ? { check_in: buildDateTime(payload.date, payload.entryTime) }
        : {}),
      ...(payload.exitTime && payload.date
        ? { check_out: buildDateTime(payload.date, payload.exitTime) }
        : {}),
      ...(payload.minutesLate !== undefined ? { minutes_late: payload.minutesLate } : {}),
      ...(payload.notes !== undefined ? { notes: payload.notes } : {}),
    }),
  });
  return handleJson(response);
};

export type AttendanceState = {
  employee: { id: number; name: string; role: string };
  date: string;
  clockIn: string | null;
  breakStart: string | null;
  breakEnd: string | null;
  clockOut: string | null;
  canClockIn: boolean;
  canBreakStart: boolean;
  canBreakEnd: boolean;
  canClockOut: boolean;
};

export type AttendanceHistoryRow = {
  date: string;
  clockIn: string | null;
  breakStart: string | null;
  breakEnd: string | null;
  clockOut: string | null;
};

const mapAttendanceState = (data: {
  employee: { id: number; name: string; role: string };
  date: string;
  clock_in: string | null;
  break_start: string | null;
  break_end: string | null;
  clock_out: string | null;
  can_clock_in: boolean;
  can_break_start: boolean;
  can_break_end: boolean;
  can_clock_out: boolean;
}): AttendanceState => ({
  employee: data.employee,
  date: data.date,
  clockIn: data.clock_in,
  breakStart: data.break_start,
  breakEnd: data.break_end,
  clockOut: data.clock_out,
  canClockIn: data.can_clock_in,
  canBreakStart: data.can_break_start,
  canBreakEnd: data.can_break_end,
  canClockOut: data.can_clock_out,
});

export const getMyAttendanceToday = async (): Promise<AttendanceState> => {
  const response = await request("/employees/attendance/today/");
  if ((response.status === 400 || response.status === 404) && response.headers.get("content-type")?.includes("application/json")) {
    const payload = await response.json().catch(() => null);
    if (payload?.state === "NO_EMPLOYEE") return buildEmptyAttendanceState();
  }
  const data = await handleJson<any>(response);
  if (data?.attendance) {
    return mapAttendanceState(data.attendance);
  }
  return buildEmptyAttendanceState();
};

const postAttendanceAction = async (path: string): Promise<AttendanceState> => {
  const response = await request(path, { method: "POST" });
  if ((response.status === 400 || response.status === 404) && response.headers.get("content-type")?.includes("application/json")) {
    const payload = await response.json().catch(() => null);
    if (payload?.state === "NO_EMPLOYEE") return buildEmptyAttendanceState();
  }
  const data = await handleJson<any>(response);
  return mapAttendanceState(data);
};

export const attendanceClockIn = async () => postAttendanceAction("/employees/attendance/clock-in/");
export const attendanceBreakStart = async () => postAttendanceAction("/employees/attendance/break-start/");
export const attendanceBreakEnd = async () => postAttendanceAction("/employees/attendance/break-end/");
export const attendanceClockOut = async () => postAttendanceAction("/employees/attendance/clock-out/");

const mapAttendanceHistoryRows = (rows: Array<any>): AttendanceHistoryRow[] =>
  rows.map((row) => ({
    date: row.date,
    clockIn: row.clock_in,
    breakStart: row.break_start,
    breakEnd: row.break_end,
    clockOut: row.clock_out,
  }));

export const getMyAttendanceHistory = async (filters?: { start?: string; end?: string }) => {
  const params = new URLSearchParams();
  if (filters?.start) params.set("start", filters.start);
  if (filters?.end) params.set("end", filters.end);
  const response = await request(`/employees/me/attendance/${params.toString() ? `?${params.toString()}` : ""}`);
  if ((response.status === 400 || response.status === 404) && response.headers.get("content-type")?.includes("application/json")) {
    const payload = await response.json().catch(() => null);
    if (payload?.state === "NO_EMPLOYEE") return [];
  }
  const data = await handleJson<any>(response);
  const rows = Array.isArray(data) ? data : (data?.rows ?? []);
  return mapAttendanceHistoryRows(rows);
};

export const getEmployeeAttendanceHistory = async (employeeId: string | number, filters?: { start?: string; end?: string }) => {
  const params = new URLSearchParams();
  if (filters?.start) params.set("start", filters.start);
  if (filters?.end) params.set("end", filters.end);
  const response = await request(`/employees/${employeeId}/attendance/${params.toString() ? `?${params.toString()}` : ""}`);
  return mapAttendanceHistoryRows(await handleJson<any[]>(response));
};

export const getSchedules = async (
  employeeId?: string
): Promise<Array<import("@/types/employee").Schedule & { employeeId: string; dayOfWeek: number }>> => {
  const params = new URLSearchParams();
  if (employeeId) params.append("employee_id", employeeId);
  const response = await request(`/employees/schedules/?${params.toString()}`);
  const data = await handleJson<Array<{
    id: number;
    employee: number;
    employee_name: string;
    schedule_type: "Fijo" | "Turnos rotativos";
    day_of_week: number;
    start_time: string;
    end_time: string;
    break_minutes: number;
    allows_overtime: boolean;
    is_active: boolean;
    priority?: number;
    stackable?: boolean;
    bxgy_config?: Record<string, unknown>;
  }>>(response);
  return data.map((item) => ({
    id: String(item.id),
    employeeName: item.employee_name,
    scheduleType: item.schedule_type,
    days: dayOfWeekLabel(item.day_of_week),
    entryTime: item.start_time.slice(0, 5),
    exitTime: item.end_time.slice(0, 5),
    allowsOvertime: item.allows_overtime,
    employeeId: String(item.employee),
    dayOfWeek: item.day_of_week,
  }));
};

export const createSchedule = async (payload: {
  employeeId: string;
  scheduleType: "Fijo" | "Turnos rotativos";
  dayOfWeek: number;
  entryTime: string;
  exitTime: string;
  breakMinutes?: number;
  allowsOvertime?: boolean;
}) => {
  const response = await request("/employees/schedules/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      employee: Number(payload.employeeId),
      schedule_type: payload.scheduleType,
      day_of_week: payload.dayOfWeek,
      start_time: payload.entryTime,
      end_time: payload.exitTime,
      break_minutes: payload.breakMinutes ?? 0,
      allows_overtime: payload.allowsOvertime ?? false,
      is_active: true,
    }),
  });
  return handleJson(response);
};

export const updateSchedule = async (
  id: string,
  payload: {
    scheduleType?: "Fijo" | "Turnos rotativos";
    dayOfWeek?: number;
    entryTime?: string;
    exitTime?: string;
    breakMinutes?: number;
    allowsOvertime?: boolean;
    isActive?: boolean;
  }
) => {
  const response = await request(`/employees/schedules/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(payload.scheduleType ? { schedule_type: payload.scheduleType } : {}),
      ...(payload.dayOfWeek !== undefined ? { day_of_week: payload.dayOfWeek } : {}),
      ...(payload.entryTime ? { start_time: payload.entryTime } : {}),
      ...(payload.exitTime ? { end_time: payload.exitTime } : {}),
      ...(payload.breakMinutes !== undefined ? { break_minutes: payload.breakMinutes } : {}),
      ...(payload.allowsOvertime !== undefined ? { allows_overtime: payload.allowsOvertime } : {}),
      ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {}),
    }),
  });
  return handleJson(response);
};

export const deleteSchedule = async (id: string) => {
  const response = await request(`/employees/schedules/${id}/`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to delete schedule");
  }
};

export const getEmployeeStats = async (): Promise<EmployeeStats> => {
  const response = await request("/employees/stats/");
  const data = await handleJson<{
    total_employees: number;
    active_employees: number;
    inactive_employees: number;
    attendance_today_count: number;
    late_today_count: number;
  }>(response);
  return {
    totalEmployees: data.total_employees ?? 0,
    activeEmployees: data.active_employees ?? 0,
    inactiveEmployees: data.inactive_employees ?? 0,
    attendanceTodayCount: data.attendance_today_count ?? 0,
    lateTodayCount: data.late_today_count ?? 0,
  };
};

const dayOfWeekLabel = (dayOfWeek: number) => {
  const map = ["D", "L", "M", "X", "J", "V", "S"];
  return map[dayOfWeek] ?? "";
};

export const createPayment = async (payload: {
  orderId: number | string;
  method: PaymentMethod;
  paymentMethodCode?: string;
  cardType?: "debit" | "credit";
  amount: number;
  amountApplied?: number;
  cashReceived?: number;
  tipAmount?: number;
  reference?: string;
  splitPart?: number;
}): Promise<Payment> => {
  if (!payload.orderId) {
    throw new Error("createPayment: missing orderId");
  }
  const amountApplied = payload.amountApplied ?? payload.amount;
  const amountStr = Number(amountApplied || 0).toFixed(2);
  const cashReceivedStr = payload.cashReceived == null ? undefined : Number(payload.cashReceived || 0).toFixed(2);
  const tipAmountStr = Number(payload.tipAmount ?? 0).toFixed(2);
  const response = await request("/payments/", {
    method: "POST",
    body: JSON.stringify({
      order: payload.orderId,
      method: payload.method,
      payment_method_code: payload.paymentMethodCode,
      amount: amountStr,
      amount_applied: amountStr,
      cash_received: cashReceivedStr,
      tip_amount: tipAmountStr,
      card_type: payload.cardType ?? "",
      reference: payload.reference ?? "",
      split_part: payload.splitPart ?? null,
    }),
  });
  const data = await handleJson<{
    id: number;
    order: number;
    method: PaymentMethod;
    amount: string;
    tip_amount: string;
    card_type?: "debit" | "credit" | "";
    reference: string;
    received_by: string | null;
    created_at: string;
    printed?: boolean;
    print_error?: string | null;
    drawer_opened?: boolean;
    drawer_error?: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    method: data.method,
    amount: Number(data.amount),
    cashReceived: payload.cashReceived,
    tipAmount: Number(data.tip_amount),
    cardType: (data.card_type as "debit" | "credit" | "") || undefined,
    reference: data.reference ?? undefined,
    receivedBy: data.received_by,
    createdAt: new Date(data.created_at),
    printed: Boolean(data.printed),
    printError: data.print_error ?? null,
    drawerOpened: Boolean(data.drawer_opened),
    drawerError: data.drawer_error ?? null,
  };
};

export const printPaymentTicket = async (
  paymentId: number
): Promise<{
  printed: boolean;
  printError: string | null;
  receiptPdfUrl?: string | null;
  drawerOpened?: boolean;
  drawerError?: string | null;
  pdfBlob?: Blob | null;
  pdfFilename?: string | null;
}> => {
  const response = await request(`/payments/${paymentId}/print-ticket/`, { method: "POST" });
  const contentType = response.headers.get("content-type") || "";
  if (response.ok && contentType.includes("application/pdf")) {
    const disposition = response.headers.get("content-disposition") || "";
    const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
    const printErrorHeader = response.headers.get("X-Print-Error");
    const drawerOpenedHeader = response.headers.get("X-Drawer-Opened");
    const drawerErrorHeader = response.headers.get("X-Drawer-Error");
    return {
      printed: false,
      printError: printErrorHeader || null,
      receiptPdfUrl: null,
      drawerOpened: drawerOpenedHeader === "1",
      drawerError: drawerErrorHeader || null,
      pdfBlob: await response.blob(),
      pdfFilename: filenameMatch?.[1] ?? `ticket_pago_${paymentId}.pdf`,
    };
  }
  const data = await handleJson<{
    printed: boolean;
    print_error?: string | null;
    receipt_pdf_url?: string | null;
    drawer_opened?: boolean;
    drawer_error?: string | null;
  }>(response);
  return {
    printed: Boolean(data.printed),
    printError: data.print_error ?? null,
    receiptPdfUrl: data.receipt_pdf_url ?? null,
    drawerOpened: Boolean(data.drawer_opened),
    drawerError: data.drawer_error ?? null,
    pdfBlob: null,
    pdfFilename: null,
  };
};

export const getPrintingStatus = async (): Promise<{ available: boolean; queue: string }> => {
  const response = await request("/printing/status/");
  const data = await handleJson<{ available: boolean; queue: string }>(response);
  return { available: Boolean(data.available), queue: data.queue || "star_tsp100" };
};



export const getPaymentMethods = async (): Promise<PaymentMethodOption[]> => {
  const response = await request('/payments/methods/');
  const data = await handleJson<Array<any>>(response);
  return data.map((m) => ({
    id: m.id,
    code: m.code,
    name: m.name,
    isCash: Boolean(m.is_cash),
    sortOrder: Number(m.sort_order ?? 0),
  }));
};
export const getPaymentsByOrder = async (orderId: number): Promise<Payment[]> => {
  const response = await request(`/payments/?order_id=${orderId}`);
  const data = await handleJson<
    Array<{
      id: number;
      order: number;
      method: PaymentMethod;
      amount: string;
      tip_amount: string;
      reference: string;
      received_by: string | null;
      created_at: string;
    }>
  >(response);
  return data.map((payment) => ({
    id: payment.id,
    orderId: payment.order,
    method: payment.method,
    amount: Number(payment.amount),
    tipAmount: Number(payment.tip_amount),
    reference: payment.reference ?? undefined,
    receivedBy: payment.received_by,
    createdAt: new Date(payment.created_at),
  }));
};

export const createRefund = async (payload: {
  orderId: number;
  method: PaymentMethod;
  amount: number;
  tipRefunded?: number;
  reason: string;
  originalPaymentId?: number;
}): Promise<{ refund: Refund; order: Order; printJob: PrintJob }> => {
  const response = await request("/refunds/", {
    method: "POST",
    body: JSON.stringify({
      order: payload.orderId,
      original_payment: payload.originalPaymentId ?? null,
      method: payload.method,
      payment_method_code: payload.paymentMethodCode,
      amount: payload.amount,
      tip_refunded: payload.tipRefunded ?? 0,
      reason: payload.reason,
    }),
  });
  const data = await handleJson<{
    refund: {
      id: number;
      order: number;
      original_payment: number | null;
      cash_session: number | null;
      method: PaymentMethod;
      amount: string;
      tip_refunded: string;
      reason: string;
      approved_by: string | null;
      created_by: string | null;
      created_at: string;
    };
    order: Parameters<typeof mapOrder>[0];
    print_job: {
      id: number;
      order: number | null;
      type: PrintJob["type"];
      status: PrintJob["status"];
      content_text: string;
      content_html: string;
      created_at: string;
      printed_at: string | null;
    };
  }>(response);
  return {
    refund: {
      id: data.refund.id,
      orderId: data.refund.order,
      originalPaymentId: data.refund.original_payment,
      cashSessionId: data.refund.cash_session,
      method: data.refund.method,
      amount: Number(data.refund.amount),
      tipRefunded: Number(data.refund.tip_refunded),
      reason: data.refund.reason,
      approvedBy: data.refund.approved_by,
      createdBy: data.refund.created_by,
      createdAt: new Date(data.refund.created_at),
    },
    order: mapOrder(data.order),
    printJob: {
      id: data.print_job.id,
      orderId: data.print_job.order,
      type: data.print_job.type,
      status: data.print_job.status,
      contentText: data.print_job.content_text,
      contentHtml: data.print_job.content_html || undefined,
      createdAt: new Date(data.print_job.created_at),
      printedAt: data.print_job.printed_at ? new Date(data.print_job.printed_at) : null,
    },
  };
};

export const getRefundsByOrder = async (orderId: number): Promise<Refund[]> => {
  const response = await request(`/refunds/?order_id=${orderId}`);
  const data = await handleJson<
    Array<{
      id: number;
      order: number;
      original_payment: number | null;
      cash_session: number | null;
      method: PaymentMethod;
      amount: string;
      tip_refunded: string;
      reason: string;
      approved_by: string | null;
      created_by: string | null;
      created_at: string;
    }>
  >(response);
  return data.map((refund) => ({
    id: refund.id,
    orderId: refund.order,
    originalPaymentId: refund.original_payment,
    cashSessionId: refund.cash_session,
    method: refund.method,
    amount: Number(refund.amount),
    tipRefunded: Number(refund.tip_refunded),
    reason: refund.reason,
    approvedBy: refund.approved_by,
    createdBy: refund.created_by,
    createdAt: new Date(refund.created_at),
  }));
};

export const voidOrder = async (orderId: number, reason: string): Promise<{ order: Order; printJobId: number }> => {
  const response = await request(`/orders/${orderId}/void/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  const data = await handleJson<{
    order: Parameters<typeof mapOrder>[0];
    print_job_id: number;
  }>(response);
  return {
    order: mapOrder(data.order),
    printJobId: data.print_job_id,
  };
};

export const refundSaleRecord = async (
  paymentId: number,
  payload?: { reason?: string }
): Promise<{ order: Order; action: "invalidate" | "credit_note" }> => {
  const response = await request(`/payments/${paymentId}/record-refund/`, {
    method: "POST",
    body: JSON.stringify({ reason: payload?.reason ?? "" }),
  });
  const data = await handleJson<{
    order: Parameters<typeof mapOrder>[0];
    action: "invalidate" | "credit_note";
  }>(response);
  return { order: mapOrder(data.order), action: data.action };
};

export const createPrintJob = async (payload: {
  orderId: number;
  type: "kitchen" | "customer";
}): Promise<PrintJob> => {
  const response = await request("/printing/jobs/", {
    method: "POST",
    body: JSON.stringify({
      order_id: payload.orderId,
      type: payload.type,
    }),
  });
  const data = await handleJson<{
    id: number;
    order: number | null;
    type: PrintJob["type"];
    status: PrintJob["status"];
    content_text: string;
    content_html: string;
    created_at: string;
    printed_at: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    type: data.type,
    status: data.status,
    contentText: data.content_text,
    contentHtml: data.content_html || undefined,
    createdAt: new Date(data.created_at),
    printedAt: data.printed_at ? new Date(data.printed_at) : null,
  };
};

export const createRefundPrintJob = async (refundId: number): Promise<PrintJob> => {
  const response = await request("/printing/jobs/refund/", {
    method: "POST",
    body: JSON.stringify({ refund_id: refundId }),
  });
  const data = await handleJson<{
    id: number;
    order: number | null;
    type: PrintJob["type"];
    status: PrintJob["status"];
    content_text: string;
    content_html: string;
    created_at: string;
    printed_at: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    type: data.type,
    status: data.status,
    contentText: data.content_text,
    contentHtml: data.content_html || undefined,
    createdAt: new Date(data.created_at),
    printedAt: data.printed_at ? new Date(data.printed_at) : null,
  };
};

export const getPrintJobsByOrder = async (orderId: number): Promise<PrintJob[]> => {
  const response = await request(`/printing/jobs/?order_id=${orderId}`);
  const data = await handleJson<
    Array<{
      id: number;
      order: number | null;
      type: PrintJob["type"];
      status: PrintJob["status"];
      content_text: string;
      content_html: string;
      created_at: string;
      printed_at: string | null;
    }>
  >(response);
  return data.map((job) => ({
    id: job.id,
    orderId: job.order,
    type: job.type,
    status: job.status,
    contentText: job.content_text,
    contentHtml: job.content_html || undefined,
    createdAt: new Date(job.created_at),
    printedAt: job.printed_at ? new Date(job.printed_at) : null,
  }));
};

export const getPrintJob = async (jobId: number): Promise<PrintJob> => {
  const response = await request(`/printing/jobs/${jobId}/`);
  const data = await handleJson<{
    id: number;
    order: number | null;
    type: PrintJob["type"];
    status: PrintJob["status"];
    content_text: string;
    content_html: string;
    created_at: string;
    printed_at: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    type: data.type,
    status: data.status,
    contentText: data.content_text,
    contentHtml: data.content_html || undefined,
    createdAt: new Date(data.created_at),
    printedAt: data.printed_at ? new Date(data.printed_at) : null,
  };
};

export const getPrintJobById = async (id: number): Promise<PrintJob> => {
  const response = await request(`/printing/jobs/${id}/`);
  const data = await handleJson<{
    id: number;
    order: number | null;
    type: PrintJob["type"];
    status: PrintJob["status"];
    content_text: string;
    content_html: string;
    created_at: string;
    printed_at: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    type: data.type,
    status: data.status,
    contentText: data.content_text,
    contentHtml: data.content_html || undefined,
    createdAt: new Date(data.created_at),
    printedAt: data.printed_at ? new Date(data.printed_at) : null,
  };
};

export const markPrintJobPrinted = async (id: number): Promise<PrintJob> => {
  const response = await request(`/printing/jobs/${id}/mark-printed/`, {
    method: "POST",
  });
  const data = await handleJson<{
    id: number;
    order: number | null;
    type: PrintJob["type"];
    status: PrintJob["status"];
    content_text: string;
    content_html: string;
    created_at: string;
    printed_at: string | null;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    type: data.type,
    status: data.status,
    contentText: data.content_text,
    contentHtml: data.content_html || undefined,
    createdAt: new Date(data.created_at),
    printedAt: data.printed_at ? new Date(data.printed_at) : null,
  };
};




export const reorderProducts = async (payload: { categoryId?: number | null; orderedIds: number[] }): Promise<void> => {
  await request("/menu/products/reorder/", {
    method: "POST",
    body: JSON.stringify({
      category_id: payload.categoryId ?? null,
      ordered_ids: payload.orderedIds,
    }),
  });
};
export const reorderCategories = async (orderedIds: number[]): Promise<Category[]> => {
  const response = await request("/menu/categories/reorder/", {
    method: "PATCH",
    body: JSON.stringify({ orderedIds }),
  });
  const data = await handleJson<Array<{ id: number; name: string; image?: string | null; image_path?: string | null; is_active: boolean; is_hidden?: boolean; position?: number }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    isActive: item.is_active,
    isHidden: Boolean(item.is_hidden),
    position: Number(item.position ?? 0),
  }));
};




export type CashSessionHistoryRow = {
  id: number;
  registerName: string;
  openedByUsername: string;
  closedByUsername?: string | null;
  openedAt: string;
  closedAt?: string | null;
  expectedCash: number;
  countedCash: number;
  difference: number;
  status: "open" | "closed";
  notes?: string;
  summarySnapshot?: Record<string, unknown>;
  summary: CashSessionSnapshot["summary"];
};
export const getCurrentCashSession = async (): Promise<CashSessionSnapshot> => {
  const params = new URLSearchParams();
  const branchIdRaw = localStorage.getItem("selected_branch_id");
  if (branchIdRaw && Number.isFinite(Number(branchIdRaw))) {
    params.set("branch_id", String(Number(branchIdRaw)));
  }
  const query = params.toString();
  const response = await request(`/cashier/session/current/${query ? `?${query}` : ""}`);
  const data = await handleJson<any>(response);
  const hasOpenSession = Boolean(data.has_open_session);
  const session = data.session ?? null;
  if (!hasOpenSession || !session) return { open: false };
  return {
    open: true,
    session: {
      id: session.id,
      openingCash: Number(session.opening_cash ?? 0),
      openedAt: session.opened_at,
      status: session.status,
    },
    summary: {
      openingCash: Number(data.summary?.opening_cash ?? 0),
      totalCashSales: Number(data.summary?.total_cash_sales ?? 0),
      totalCashOut: Number(data.summary?.cash_expenses_total ?? 0),
      expectedCashInDrawer: Number(data.summary?.expected_cash_in_drawer ?? 0),
      countedCash: Number(data.summary?.counted_cash ?? 0),
      overShortCash: Number(data.summary?.difference ?? 0),
      methods: {
        cash: Number(data.summary?.totals_by_method?.cash ?? data.summary?.methods?.CASH?.total ?? 0),
        card: fromCents(
          toCents(data.summary?.totals_by_method?.card ?? 0)
          + toCents(data.summary?.totals_by_method?.card_debit ?? 0)
          + toCents(data.summary?.totals_by_method?.card_credit ?? 0)
        ),
        cardDebit: 0,
        cardCredit: 0,
        transfer: Number(data.summary?.totals_by_method?.transfer ?? data.summary?.methods?.TRANSFER?.total ?? 0),
        pedidosYa: Number(data.summary?.totals_by_method?.pedidos_ya ?? data.summary?.methods?.PEDIDOS_YA?.total ?? 0),
        payPal: Number(data.summary?.totals_by_method?.paypal ?? data.summary?.methods?.PAYPAL?.total ?? 0),
        cashIn: Number(data.summary?.total_cash_sales ?? data.summary?.cash_in_total ?? 0),
      },
    },
  };
};

export const openCashSession = async (openingCash: number): Promise<void> => {
  const branchIdRaw = localStorage.getItem("selected_branch_id");
  await handleJson(await request('/cashier/session/open/', {
    method: 'POST',
    body: JSON.stringify({
      opening_cash: openingCash,
      ...(branchIdRaw && Number.isFinite(Number(branchIdRaw)) ? { branch_id: Number(branchIdRaw) } : {}),
    }),
  }));
};

export const closeCashSession = async (
  closingCashCounted: number,
  notes?: string,
  totals?: { bills?: number; coins?: number }
): Promise<{ sessionId?: number; ticketText?: string; printed?: boolean; printError?: string | null }> => {
  const data = await handleJson<any>(await request('/cashier/session/close/', {
    method: 'POST',
    body: JSON.stringify({
      closing_cash_counted: closingCashCounted,
      total_bills: Number(totals?.bills ?? 0),
      total_coins: Number(totals?.coins ?? 0),
      notes: notes ?? '',
    }),
  }));
  return {
    sessionId: Number(data.session?.id ?? 0) || undefined,
    ticketText: data.ticket_text,
    printed: Boolean(data.printed),
    printError: data.print_error ?? null,
  };
};

export const getCashTransactions = async (sessionId?: number): Promise<CashTransaction[]> => {
  const params = new URLSearchParams();
  if (sessionId) params.set('session_id', String(sessionId));
  const response = await request(`/cashier/transactions/${params.toString() ? `?${params.toString()}` : ''}`);
  const data = await handleJson<Array<any>>(response);
  return data.map((tx) => ({
    id: tx.id,
    type: tx.type,
    amount: Number(tx.amount),
    description: tx.description,
    createdAt: tx.created_at,
  }));
};

export const createCashPayout = async (amount: number, description: string): Promise<void> => {
  await handleJson(await request('/cashier/transactions/', {
    method: 'POST',
    body: JSON.stringify({ type: 'cash_out', amount, description }),
  }));
};

export const openCashDrawer = async (): Promise<{ ok: boolean; message: string; error?: string | null }> => {
  const response = await request('/cashier/drawer/open/', { method: 'POST' });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  return {
    ok: Boolean(payload.success ?? payload.ok ?? response.ok),
    message: String(payload.message ?? payload.reason ?? "No se pudo abrir la gaveta"),
    error: payload.error ? String(payload.error) : null,
  };
};

export const getCashSessionsHistory = async (filters?: { dateFrom?: string; dateTo?: string; registerId?: number }): Promise<CashSessionHistoryRow[]> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set('date_from', filters.dateFrom);
  if (filters?.dateTo) params.set('date_to', filters.dateTo);
  if (filters?.registerId) params.set('register_id', String(filters.registerId));
  const response = await request(`/cashier/session/history/${params.toString() ? `?${params.toString()}` : ''}`);
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    id: row.id,
    registerName: row.register_name ?? "-",
    openedByUsername: row.opened_by ?? "-",
    closedByUsername: row.closed_by ?? null,
    openedAt: row.opened_at,
    closedAt: row.closed_at,
    expectedCash: Number(row.expected_cash ?? 0),
    countedCash: Number(row.counted_cash ?? 0),
    difference: Number(row.difference ?? 0),
    status: row.status,
    notes: row.notes ?? "",
    summarySnapshot: row.summary_snapshot ?? {},
    summary: {
      openingCash: Number(row.summary_snapshot?.opening_cash ?? 0),
      totalCashSales: Number(row.summary_snapshot?.total_cash_sales ?? 0),
      totalCashOut: Number(row.summary_snapshot?.cash_expenses_total ?? 0),
      expectedCashInDrawer: Number(row.summary_snapshot?.expected_cash_in_drawer ?? 0),
      countedCash: Number(row.summary_snapshot?.counted_cash ?? 0),
      overShortCash: Number(row.summary_snapshot?.difference ?? 0),
      methods: {
        cash: Number(row.summary_snapshot?.totals_by_method?.cash ?? row.summary_snapshot?.methods?.CASH?.total ?? 0),
        cardDebit: 0,
        cardCredit: 0,
        card: fromCents(
          toCents(row.summary_snapshot?.totals_by_method?.card ?? 0)
          + toCents(row.summary_snapshot?.totals_by_method?.card_debit ?? 0)
          + toCents(row.summary_snapshot?.totals_by_method?.card_credit ?? 0)
        ),
        transfer: Number(row.summary_snapshot?.totals_by_method?.transfer ?? row.summary_snapshot?.methods?.TRANSFER?.total ?? 0),
        pedidosYa: Number(row.summary_snapshot?.totals_by_method?.pedidos_ya ?? row.summary_snapshot?.methods?.PEDIDOS_YA?.total ?? 0),
        payPal: Number(row.summary_snapshot?.totals_by_method?.paypal ?? row.summary_snapshot?.methods?.PAYPAL?.total ?? 0),
        cashIn: Number(row.summary_snapshot?.total_cash_sales ?? row.summary_snapshot?.cash_in_total ?? 0),
      },
    },
  }));
};

export const getCashSessionDetail = async (sessionId: number): Promise<{ summary: CashSessionSnapshot["summary"]; transactions: CashTransaction[] }> => {
  const response = await request(`/cashier/sessions/${sessionId}/`);
  const data = await handleJson<any>(response);
  return {
    summary: {
      openingCash: Number(data.summary.opening_cash ?? 0),
      totalCashSales: Number(data.summary.total_cash_sales ?? 0),
      totalCashOut: Number(data.summary.cash_expenses_total ?? 0),
      expectedCashInDrawer: Number(data.summary.expected_cash_in_drawer ?? 0),
      countedCash: Number(data.summary.counted_cash ?? 0),
      overShortCash: Number(data.summary.difference ?? 0),
      methods: {
        cash: Number(data.summary.totals_by_method?.cash ?? data.summary.methods?.CASH?.total ?? 0),
        cardDebit: 0,
        cardCredit: 0,
        card: fromCents(
          toCents(data.summary.totals_by_method?.card ?? 0)
          + toCents(data.summary.totals_by_method?.card_debit ?? 0)
          + toCents(data.summary.totals_by_method?.card_credit ?? 0)
        ),
        transfer: Number(data.summary.totals_by_method?.transfer ?? data.summary.methods?.TRANSFER?.total ?? 0),
        pedidosYa: Number(data.summary.totals_by_method?.pedidos_ya ?? data.summary.methods?.PEDIDOS_YA?.total ?? 0),
        payPal: Number(data.summary.totals_by_method?.paypal ?? data.summary.methods?.PAYPAL?.total ?? 0),
        cashIn: Number(data.summary.total_cash_sales ?? data.summary.cash_in_total ?? 0),
      },
    },
    transactions: (data.transactions || []).map((tx: any) => ({
      id: tx.id,
      type: tx.type,
      amount: Number(tx.amount),
      description: tx.description,
      createdAt: tx.created_at,
    })),
  };
};




export const downloadCashSessionTicketPdf = async (sessionId: number): Promise<void> => {
  try {
    const response = await request(`/cashier/sessions/${sessionId}/ticket.pdf`, {
      headers: { Accept: "application/pdf,application/octet-stream,*/*" },
    });
    if (!response.ok) throw new Error(`No se pudo descargar ticket PDF (${response.status})`);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/pdf")) {
      throw new Error("Respuesta inválida al descargar PDF de cierre de caja.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
    const now = new Date();
    const pad = (value: number) => String(value).padStart(2, "0");
    const fallback = `end_of_day_${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}.pdf`;
    const filename = filenameMatch?.[1] || fallback;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    if (import.meta.env.DEV) {
      console.error("downloadCashSessionTicketPdf error", error);
    }
    throw error instanceof Error ? error : new Error("No se pudo descargar ticket PDF");
  }
};

export const downloadPaymentTicketPdf = async (paymentId: number): Promise<void> => {
  const response = await request(`/payments/${paymentId}/ticket.pdf`, {
    headers: { Accept: "application/pdf,application/octet-stream,*/*" },
  });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => ({}));
      const detail = String(payload?.detail ?? "").trim();
      throw new Error(detail || `No se pudo descargar ticket PDF (${response.status})`);
    }
    const raw = await response.text().catch(() => "");
    throw new Error(raw || `No se pudo descargar ticket PDF (${response.status})`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/pdf")) {
    throw new Error("Respuesta inválida al descargar PDF de ticket.");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  const fallback = `venta_${paymentId}_${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}.pdf`;
  const filename = filenameMatch?.[1] || fallback;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
export type DTERecord = {
  id: number;
  sale_id?: number;
  order_id?: number;
  dte_type: string;
  status: "PENDIENTE" | "ENVIANDO" | "ACEPTADO" | "RECHAZADO" | "INVALIDADO" | string;
  control_number: string;
  codigo_generacion: string;
  receiver_name: string;
  total_amount: number;
  hacienda_uuid?: string;
  sello_recepcion?: string;
  sello_recibido?: string;
  firma?: string;
  recibido_at?: string;
  estado_mh?: string;
  mh_response_json?: Record<string, unknown>;
  mh_response_text?: string;
  request_payload?: Record<string, unknown>;
  response_payload?: Record<string, unknown>;
  hacienda_state?: string;
  error_message?: string;
  attempts?: number;
  last_sent_at?: string;
  issued_at?: string;
  can_resend?: boolean;
  can_send_email?: boolean;
  missing_email_reason?: string;
  can_send_whatsapp?: boolean;
  missing_phone_reason?: string;
  can_credit_note?: boolean;
  credit_note_reason?: string;
  has_credit_note?: boolean;
  can_invalidate?: boolean;
  invalidate_reason?: string;
  invalidate_deadline?: string | null;
  invalidate_remaining?: string;
  customer_email?: string;
  customer_phone?: string;
  created_at: string;
};

export const dteIssuedList = async (filters?: {
  search?: string;
  status?: string;
  type?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ results: DTERecord[]; count: number; totalAmountSum: number; page: number; pageSize: number }> => {
  const params = new URLSearchParams();
  if (filters?.search) params.set("search", filters.search);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.type) params.set("type", filters.type);
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.page) params.set("page", String(filters.page));
  if (filters?.pageSize) params.set("page_size", String(filters.pageSize));
  const res = await request(`/dte/issued/?${params.toString()}`);
  const data = await handleJson<any>(res);
  const results = Array.isArray(data.results) ? data.results : Array.isArray(data) ? data : [];
  return {
    results,
    count: Number(data.count ?? results.length),
    totalAmountSum: Number(data.total_amount_sum ?? 0),
    page: Number(data.page ?? filters?.page ?? 1),
    pageSize: Number(data.page_size ?? filters?.pageSize ?? 20),
  };
};

export const dteIssuedDetail = async (id: number): Promise<DTERecord> => {
  const res = await request(`/dte/issued/${id}/`);
  return handleJson<DTERecord>(res);
};

export const dteResend = async (id: number): Promise<{ message: string; record: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/resend/`, { method: "POST" });
  const payload = await handleJson<any>(res);
  return { message: payload.message ?? "Reenvío procesado", record: payload.record as DTERecord };
};

export const dteSendEmail = async (id: number): Promise<{ message: string; record?: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/send-email/`, { method: "POST" });
  const payload = await handleJson<any>(res);
  return { message: payload.message ?? "Correo enviado", record: payload.record };
};

export const dteSendWhatsapp = async (id: number): Promise<{ message: string; record?: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/send-whatsapp/`, { method: "POST" });
  const payload = await handleJson<any>(res);
  return { message: payload.message ?? "WhatsApp enviado", record: payload.record };
};

export const dteDeliver = async (
  id: number,
  channels: Array<"whatsapp" | "email">
): Promise<{
  success: boolean;
  summary: string;
  orderId?: number;
  issuedId?: number;
  results: Record<string, { ok: boolean; statusCode: number | null; error: string | null }>;
}> => {
  const res = await request(`/dte/issued/${id}/deliver/`, {
    method: "POST",
    body: JSON.stringify({ channels }),
  });
  const payload = await handleJson<any>(res);
  return {
    success: Boolean(payload.success),
    summary: payload.summary ?? "Envío completado",
    orderId: payload.order_id,
    issuedId: payload.issued_id,
    results: Object.fromEntries(
      Object.entries(payload.results ?? {}).map(([key, value]: [string, any]) => [
        key,
        { ok: Boolean(value?.ok), statusCode: value?.status_code ?? null, error: value?.error ?? null },
      ])
    ),
  };
};

export const dteDeliverByOrder = async (
  orderId: number,
  channels: Array<"whatsapp" | "email">
): Promise<{
  success: boolean;
  summary: string;
  orderId?: number;
  issuedId?: number;
  results: Record<string, { ok: boolean; statusCode: number | null; error: string | null }>;
}> => {
  const res = await request(`/dte/orders/${orderId}/deliver/`, {
    method: "POST",
    body: JSON.stringify({ channels }),
  });
  const payload = await handleJson<any>(res);
  return {
    success: Boolean(payload.success),
    summary: payload.summary ?? "Envío completado",
    orderId: payload.order_id,
    issuedId: payload.issued_id,
    results: Object.fromEntries(
      Object.entries(payload.results ?? {}).map(([key, value]: [string, any]) => [
        key,
        { ok: Boolean(value?.ok), statusCode: value?.status_code ?? null, error: value?.error ?? null },
      ])
    ),
  };
};

export const dteInvalidate = async (id: number, motivo: string): Promise<{ message: string; record?: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/invalidate/`, {
    method: "POST",
    body: JSON.stringify({ motivo }),
  });
  const payload = await handleJson<any>(res);
  return { message: payload.message ?? "DTE invalidado", record: payload.record };
};

export const dteCreateCreditNote = async (id: number, motivo: string): Promise<{ message: string; record?: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/credit-note/`, {
    method: "POST",
    body: JSON.stringify({ motivo }),
  });
  const payload = await handleJson<any>(res);
  return { message: payload.message ?? "Nota de crédito creada", record: payload.record };
};


export const branchOptions = async (): Promise<BranchOption[]> => {
  const response = await request("/core/branches/");
  return handleJson<BranchOption[]>(response);
};

const mapCustomer = (c: any): Customer => ({
  id: c.id,
  fullName: c.full_name ?? c.name,
  companyName: c.company_name ?? "",
  clientType: c.client_type ?? "CF",
  dui: c.dui ?? "",
  nit: c.nit ?? "",
  nrc: c.nrc,
  phone: c.phone ?? c.telefono,
  email: c.email ?? c.correo,
  direccion: c.direccion ?? c.direccion_complemento,
  departmentCode: c.department_code ?? c.direccion_departamento,
  municipalityCode: c.municipality_code ?? c.direccion_municipio,
  activityCode: c.activity_code ?? c.cod_actividad,
  activityDescription: c.activity_description ?? c.desc_actividad,
  isConsumerFinal: Boolean(c.is_consumer_final),
  isDeleted: Boolean(c.is_deleted),
  name: c.name,
  tipoDocumento: c.tipo_documento,
  numDocumento: c.num_documento,
  codActividad: c.cod_actividad,
  descActividad: c.desc_actividad,
  direccionDepartamento: c.direccion_departamento,
  direccionMunicipio: c.direccion_municipio,
  direccionComplemento: c.direccion_complemento,
  telefono: c.telefono,
  correo: c.correo,
  isDefaultConsumerFinal: Boolean(c.is_default_consumer_final),
});

export const listCustomers = async (search = ""): Promise<Customer[]> => {
  const query = search ? `?q=${encodeURIComponent(search)}` : "";
  const response = await request(`/clients/${query}`);
  const data = await handleJson<any[]>(response);
  return data.map(mapCustomer);
};

export const getDefaultConsumerCustomer = async (): Promise<Customer> => {
  const response = await request('/clients/default-consumer-final/');
  const data = await handleJson<any>(response);
  return mapCustomer(data);
};

export const createCustomer = async (payload: Partial<Customer> & { fullName: string }): Promise<Customer> => {
  const response = await request('/clients/', {
    method: 'POST',
    body: JSON.stringify({
      full_name: payload.fullName,
      company_name: payload.companyName ?? '',
      client_type: payload.clientType ?? 'CF',
      dui: payload.dui ?? '',
      nit: payload.nit ?? '',
      nrc: payload.nrc ?? null,
      phone: payload.phone ?? '',
      email: payload.email ?? null,
      direccion: payload.direccion ?? '',
      department_code: payload.departmentCode ?? '',
      municipality_code: payload.municipalityCode ?? '',
      activity_code: payload.activityCode ?? '',
      activity_description: payload.activityDescription ?? '',
      is_consumer_final: Boolean(payload.isConsumerFinal),
    }),
  });
  return mapCustomer(await handleJson<any>(response));
};

export const updateCustomer = async (id: number, payload: Partial<Customer>): Promise<Customer> => {
  const response = await request(`/clients/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify({
      ...(payload.fullName !== undefined ? { full_name: payload.fullName } : {}),
      ...(payload.companyName !== undefined ? { company_name: payload.companyName } : {}),
      ...(payload.clientType !== undefined ? { client_type: payload.clientType } : {}),
      ...(payload.dui !== undefined ? { dui: payload.dui } : {}),
      ...(payload.nit !== undefined ? { nit: payload.nit } : {}),
      ...(payload.nrc !== undefined ? { nrc: payload.nrc } : {}),
      ...(payload.phone !== undefined ? { phone: payload.phone } : {}),
      ...(payload.email !== undefined ? { email: payload.email } : {}),
      ...(payload.direccion !== undefined ? { direccion: payload.direccion } : {}),
      ...(payload.departmentCode !== undefined ? { department_code: payload.departmentCode } : {}),
      ...(payload.municipalityCode !== undefined ? { municipality_code: payload.municipalityCode } : {}),
      ...(payload.activityCode !== undefined ? { activity_code: payload.activityCode } : {}),
      ...(payload.activityDescription !== undefined ? { activity_description: payload.activityDescription } : {}),
      ...(payload.isConsumerFinal !== undefined ? { is_consumer_final: payload.isConsumerFinal } : {}),
    }),
  });
  return mapCustomer(await handleJson<any>(response));
};

export const setConsumerFinalCustomer = async (id: number): Promise<Customer> => {
  const response = await request(`/clients/${id}/set-consumer-final/`, { method: 'POST' });
  return mapCustomer(await handleJson<any>(response));
};

export const deleteCustomer = async (id: number): Promise<void> => {
  const response = await request(`/clients/${id}/`, { method: 'DELETE' });
  if (!response.ok) throw new Error('No se pudo eliminar cliente');
};

export const listDepartments = async () => {
  if ((listDepartments as any)._cache) return (listDepartments as any)._cache as Array<{ code: string; name: string }>;
  const response = await request('/clients/geo/departments/');
  const data = await handleJson<Array<{ code: string; name: string }>>(response);
  (listDepartments as any)._cache = data;
  return data;
};

export const listMunicipalities = async (departmentCode?: string) => {
  const key = departmentCode || "__all__";
  const cache = ((listMunicipalities as any)._cache ||= new Map<string, Array<{ code: string; department_code: string; name: string }>>());
  if (cache.has(key)) return cache.get(key)!;
  const response = await request(`/clients/geo/municipalities/${departmentCode ? `?department_code=${departmentCode}` : ''}`);
  const data = await handleJson<Array<{ code: string; department_code: string; name: string }>>(response);
  cache.set(key, data);
  return data;
};

export const listActivities = async (q = '') => {
  const key = q || "__all__";
  const cache = ((listActivities as any)._cache ||= new Map<string, Array<{ code: string; description: string }>>());
  if (cache.has(key)) return cache.get(key)!;
  const response = await request(`/clients/activities/${q ? `?q=${encodeURIComponent(q)}` : ''}`);
  const data = await handleJson<Array<{ code: string; description: string }>>(response);
  cache.set(key, data);
  return data;
};

export const downloadOrderReceiptPdf = async (orderId: number): Promise<Blob> => {
  const response = await request(`/orders/${orderId}/receipt.pdf`, { headers: { Accept: "application/pdf" } });
  if (!response.ok) throw new Error("No se pudo descargar PDF");
  return response.blob();
};
