export const API_BASE_URL = import.meta.env.VITE_API_BASE ?? "/api";

export type Category = {
  id: number;
  name: string;
  isActive?: boolean;
};

export type Modifier = {
  id: number;
  name: string;
  price: number;
  isActive?: boolean;
};

export type ModifierGroup = {
  id: number;
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  modifiers: Modifier[];
};

export type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  category: string;
  categoryName?: string | null;
  categoryId: number;
  image?: string | null;
  imagePath?: string | null;
  imageUrl?: string | null;
  available: boolean;
  modifierGroups: number[];
};

export const resolveImageUrl = (imagePath?: string | null): string | null => {
  if (!imagePath) return null;
  if (/^https?:\/\//i.test(imagePath)) return imagePath;
  const base = API_BASE_URL.replace(/\/api\/?$/, "");
  const normalizedPath = imagePath.startsWith("/") ? imagePath : `/${imagePath}`;
  return `${base}${normalizedPath}`;
};

export type Discount = {
  id: number;
  name: string;
  description?: string;
  type: "percent" | "fixed";
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
};

export type ServiceType = {
  id: number;
  key: string;
  label: string;
  isActive?: boolean;
};

export type TaxConfig = {
  rate: number;
};

export type OrderItem = {
  id: number;
  productName: string;
  quantity: number;
  modifiers: string[];
  price: number;
};

export type Order = {
  id: number;
  orderNumber: number;
  items: OrderItem[];
  total: number;
  status: "new" | "preparing" | "ready" | "delivered" | "canceled";
  serviceType: "dine-in" | "takeout" | "delivery" | "kiosk";
  createdAt: Date;
  prepTime: number;
  customerName?: string;
  paymentStatus: "unpaid" | "partial" | "paid";
  financialStatus: "open" | "paid" | "refunded_partial" | "refunded_full" | "voided";
  totalPaid: number;
  remaining: number;
  refundTotal: number;
  netPaid: number;
};

export type EmployeeStats = {
  totalEmployees: number;
  activeEmployees: number;
  inactiveEmployees: number;
  attendanceTodayCount: number;
  lateTodayCount: number;
};

export type PaymentMethod = "cash" | "card" | "transfer";

export type Payment = {
  id: number;
  orderId: number;
  method: PaymentMethod;
  amount: number;
  tipAmount: number;
  reference?: string;
  receivedBy?: string | null;
  createdAt: Date;
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
  orderId: number;
  orderNumber: number;
  serviceType: Order["serviceType"];
  createdAt: Date;
  subtotal: number;
  tax: number;
  total: number;
  discountTotal: number;
  status: Order["status"];
  financialStatus: Order["financialStatus"];
  refundTotal: number;
  netPaid: number;
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
  role: "admin" | "manager" | "cashier" | "kitchen";
};

const buildApiUrl = (path: string) => {
  const base = API_BASE_URL.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
};

const getCsrfToken = () => {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
};

const request = async (path: string, options: RequestInit = {}) => {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type") && method !== "GET") {
    headers.set("Content-Type", "application/json");
  }

  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrfToken = getCsrfToken();
    if (csrfToken && !headers.has("X-CSRFToken")) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  return fetch(buildApiUrl(path), {
    credentials: "include",
    ...options,
    headers,
  });
};

const handleJson = async <T>(response: Response): Promise<T> => {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error("Sesión expirada. Inicia sesión nuevamente.");
    }
    if (isJson) {
      const errorPayload = await response.json().catch(() => null);
      const message =
        (errorPayload && (errorPayload.detail || errorPayload.error)) ||
        (errorPayload ? JSON.stringify(errorPayload) : "");
      throw new Error(message || "API request failed");
    }
    const text = await response.text();
    throw new Error(text ? `API request failed: ${text.slice(0, 200)}` : "API request failed");
  }

  if (!isJson) {
    const text = await response.text();
    throw new Error(text ? `Unexpected response: ${text.slice(0, 200)}` : "Unexpected response");
  }

  return response.json() as Promise<T>;
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
  return handleJson<AuthUser>(response);
};

export const logout = async (): Promise<void> => {
  const response = await request("/auth/logout/", { method: "POST" });
  if (!response.ok && response.status !== 204) {
    const message = await response.text();
    throw new Error(message || "Logout failed");
  }
};

export const me = async (): Promise<AuthUser> => {
  const response = await request("/auth/me/");
  return handleJson<AuthUser>(response);
};

let cachedTaxConfig: TaxConfig | null = null;

export const getCategories = async (query?: string): Promise<Category[]> => {
  const params = query ? `?q=${encodeURIComponent(query)}` : "";
  const response = await request(`/menu/categories/${params}`);
  const data = await handleJson<Array<{ id: number; name: string; is_active: boolean }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    isActive: item.is_active,
  }));
};

export const createCategory = async (name: string): Promise<Category> => {
  const response = await request("/menu/categories/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await handleJson<{ id: number; name: string; is_active: boolean }>(response);
  return {
    id: data.id,
    name: data.name,
    isActive: data.is_active,
  };
};

export const getProducts = async (): Promise<Product[]> => {
  const response = await request("/menu/products/");
  const data = await handleJson<Array<{
    id: number;
    name: string;
    description: string;
    price: string;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    modifier_groups: number[];
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description,
    price: Number(item.price),
    category: item.category,
    categoryName: item.category_name ?? item.category,
    categoryId: item.category_id_display ?? 0,
    image: item.image,
    imagePath: item.image_path ?? null,
    imageUrl: item.image_url ?? undefined,
    available: item.available,
    modifierGroups: item.modifier_groups,
  }));
};

export const createProduct = async (payload: {
  name: string;
  description: string;
  price: number;
  categoryId: number;
  image?: File | null;
  available: boolean;
  modifierGroupIds?: number[];
}): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
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
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    modifier_groups: number[];
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? payload.categoryId,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    modifierGroups: data.modifier_groups,
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
    modifierGroupIds?: number[];
  }
): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
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
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    modifier_groups: number[];
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? payload.categoryId,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    modifierGroups: data.modifier_groups,
  };
};

export const updateProductModifierGroups = async (
  productId: number,
  modifierGroupIds: number[],
): Promise<Product> => {
  const formData = new FormData();
  modifierGroupIds.forEach((id) => formData.append("modifier_group_ids", id.toString()));
  const response = await request(`/menu/products/${productId}/`, {
    method: "PATCH",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    modifier_groups: number[];
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? 0,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    modifierGroups: data.modifier_groups,
  };
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
    category: string;
    category_name?: string;
    category_id_display?: number;
    image: string | null;
    image_path?: string | null;
    image_url: string | null;
    available: boolean;
    modifier_groups: number[];
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    price: Number(data.price),
    category: data.category,
    categoryName: data.category_name ?? data.category,
    categoryId: data.category_id_display ?? 0,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
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
    modifiers: Array<{ id: number; name: string; price: string; is_active: boolean }>;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    required: item.required,
    minSelection: item.min_selection,
    maxSelection: item.max_selection,
    modifiers: item.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      price: Number(modifier.price),
      isActive: modifier.is_active,
    })),
  }));
};

export const createModifierGroup = async (payload: {
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  modifiers: Array<{ name: string; price: number; isActive?: boolean }>;
}): Promise<ModifierGroup> => {
  const response = await request("/menu/modifier-groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      required: payload.required,
      min_selection: payload.minSelection,
      max_selection: payload.maxSelection,
      modifiers: payload.modifiers.map((modifier) => ({
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
    modifiers: Array<{ id: number; name: string; price: string; is_active: boolean }>;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    required: data.required,
    minSelection: data.min_selection,
    maxSelection: data.max_selection,
    modifiers: data.modifiers.map((modifier) => ({
      id: modifier.id,
      name: modifier.name,
      price: Number(modifier.price),
      isActive: modifier.is_active,
    })),
  };
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
  }));
};

export const getServiceTypes = async (): Promise<ServiceType[]> => {
  const response = await request("/core/service-types/");
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean }>>(response);
  return data.map((item) => ({
    id: item.id,
    key: item.key,
    label: item.label,
    isActive: item.is_active,
  }));
};

export const getActiveTaxConfig = async (): Promise<TaxConfig> => {
  if (cachedTaxConfig) return cachedTaxConfig;
  const response = await request("/core/tax-config/active/");
  const data = await handleJson<{ rate: string }>(response);
  cachedTaxConfig = { rate: Number(data.rate) };
  return cachedTaxConfig;
};

const mapOrder = (order: {
  id: number;
  order_number: number;
  status: Order["status"];
  customer_name: string;
  total: string;
  service_type: Order["serviceType"];
  created_at: string;
  items: Array<{
    id: number;
    product_id: number;
    product_name_snapshot: string;
    price_snapshot: string;
    quantity: number;
    applied_modifiers: Array<{ modifier_name_snapshot: string }>;
  }>;
  payment_status: Order["paymentStatus"];
  financial_status: Order["financialStatus"];
  total_paid: string;
  remaining: string;
  refund_total: string;
  net_paid: string;
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
      quantity: item.quantity,
      modifiers: Array.isArray(item.applied_modifiers)
        ? item.applied_modifiers.map((modifier) => modifier.modifier_name_snapshot)
        : [],
      price: Number(item.price_snapshot),
    })),
    total: Number(order.total),
    status: order.status,
    serviceType: order.service_type,
    createdAt,
    prepTime,
    customerName: order.customer_name || undefined,
    paymentStatus: order.payment_status,
    financialStatus: order.financial_status,
    totalPaid: Number(order.total_paid ?? 0),
    remaining: Number(order.remaining ?? 0),
    refundTotal: Number(order.refund_total ?? 0),
    netPaid: Number(order.net_paid ?? 0),
  };
};

export const createOrder = async (payload: {
  serviceType: Order["serviceType"];
  customerName?: string;
  source?: "kiosk" | "pos";
  channel?: "kiosk" | "pos";
  items: Array<{
    productId: number;
    productName: string;
    price: number;
    quantity: number;
    modifiers: Array<{ name: string; price: number }>;
  }>;
}): Promise<Order> => {
  const response = await request("/orders/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      service_type_key: payload.serviceType,
      customer_name: payload.customerName ?? "",
      source: payload.source,
      channel: payload.channel,
      items: payload.items.map((item) => ({
        product_id: item.productId,
        product_name_snapshot: item.productName,
        price_snapshot: item.price,
        quantity: item.quantity,
        modifiers: item.modifiers.map((modifier) => ({
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
      product_id: number;
      product_name_snapshot: string;
      price_snapshot: string;
      quantity: number;
      applied_modifiers: Array<{ modifier_name_snapshot: string }>;
    }>;
  }>(response);
  if (import.meta.env.DEV) {
    console.debug("[API] createOrder raw response", data);
  }
  return mapOrder(data);
};

export const getActiveOrders = async (): Promise<Order[]> => {
  const response = await request("/orders/active/");
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
        product_id: number;
        product_name_snapshot: string;
        price_snapshot: string;
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
      product_id: number;
      product_name_snapshot: string;
      price_snapshot: string;
      quantity: number;
      applied_modifiers: Array<{ modifier_name_snapshot: string }>;
    }>;
  }>(response);
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

export const getCustomerOrders = async (): Promise<
  Array<{ id: number; orderNumber: number; status: Order["status"]; customerName?: string; createdAt: Date }>
> => {
  const response = await request("/orders/customer-display/");
  const data = await handleJson<
    Array<{ id: number; order_number: number; status: Order["status"]; customer_name: string; created_at: string }>
  >(response);
  if (!Array.isArray(data)) {
    return [];
  }
  return data.map((order) => ({
    id: order.id,
    orderNumber: order.order_number,
    status: order.status,
    customerName: order.customer_name || undefined,
    createdAt: new Date(order.created_at),
  }));
};

export const getSalesReport = async (filters?: {
  dateFrom?: string;
  dateTo?: string;
  serviceType?: Order["serviceType"];
  status?: Order["status"];
}): Promise<{ rows: SalesReportRow[]; aggregates: SalesReportAggregates }> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.serviceType) params.set("service_type", filters.serviceType);
  if (filters?.status) params.set("status", filters.status);
  const query = params.toString();
  const response = await request(`/reports/sales/${query ? `?${query}` : ""}`);
  const data = await handleJson<{
    results: Array<{
      order_id: number;
      order_number: number;
      service_type: Order["serviceType"];
      date: string;
      subtotal: string;
      tax: string;
      total: string;
      discount_total: string;
      status: Order["status"];
      financial_status: Order["financialStatus"];
      refund_total: string;
      net_paid: string;
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
        card: string;
        transfer: string;
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
      orderId: row.order_id,
      orderNumber: row.order_number,
      serviceType: row.service_type,
      createdAt: new Date(row.date),
      subtotal: Number(row.subtotal),
      tax: Number(row.tax),
      total: Number(row.total),
      discountTotal: Number(row.discount_total),
      status: row.status,
      financialStatus: row.financial_status,
      refundTotal: Number(row.refund_total ?? 0),
      netPaid: Number(row.net_paid ?? 0),
    })),
    aggregates: {
      countOrders: data.aggregates.count_orders,
      sumSubtotal: Number(data.aggregates.sum_subtotal),
      sumTax: Number(data.aggregates.sum_tax),
      sumTotal: Number(data.aggregates.sum_total),
      sumDiscountTotal: Number(data.aggregates.sum_discount_total),
      grossTotal: Number(data.aggregates.gross_total ?? data.aggregates.sum_total ?? 0),
      refundTotal: Number(data.aggregates.refund_total ?? 0),
      netTotal: Number(data.aggregates.net_total ?? 0),
      paymentMethods: {
        cash: Number(data.aggregates.payment_methods?.cash ?? 0),
        card: Number(data.aggregates.payment_methods?.card ?? 0),
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
  };
};

const ROLE_LABELS: Record<string, string> = {
  cashier: "Cajero",
  kitchen: "Cocinero",
  manager: "Gerente",
  admin: "Administrador",
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
      email: payload.email || null,
      phone: payload.phone ?? "",
      role: roleKey,
      branch_name_input: payload.branch || null,
      status: payload.status ?? "active",
      create_user: payload.createUser ?? false,
      user: payload.user
        ? {
            username: payload.user.username,
            email: payload.user.email || null,
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
      ...(payload.email !== undefined ? { email: payload.email || null } : {}),
      ...(payload.phone !== undefined ? { phone: payload.phone } : {}),
      ...(roleKey ? { role: roleKey } : {}),
      ...(payload.branch !== undefined ? { branch_name_input: payload.branch } : {}),
      ...(payload.status !== undefined ? { status: payload.status } : {}),
      ...(payload.createUser !== undefined ? { create_user: payload.createUser } : {}),
      ...(payload.user
        ? {
            user: {
              ...(payload.user.username !== undefined ? { username: payload.user.username } : {}),
              ...(payload.user.email !== undefined ? { email: payload.user.email || null } : {}),
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
  amount: number;
  tipAmount?: number;
  reference?: string;
}): Promise<Payment> => {
  if (!payload.orderId) {
    throw new Error("createPayment: missing orderId");
  }
  const response = await request("/payments/", {
    method: "POST",
    body: JSON.stringify({
      order: payload.orderId,
      method: payload.method,
      amount: payload.amount,
      tip_amount: payload.tipAmount ?? 0,
      reference: payload.reference ?? "",
    }),
  });
  const data = await handleJson<{
    id: number;
    order: number;
    method: PaymentMethod;
    amount: string;
    tip_amount: string;
    reference: string;
    received_by: string | null;
    created_at: string;
  }>(response);
  return {
    id: data.id,
    orderId: data.order,
    method: data.method,
    amount: Number(data.amount),
    tipAmount: Number(data.tip_amount),
    reference: data.reference ?? undefined,
    receivedBy: data.received_by,
    createdAt: new Date(data.created_at),
  };
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
