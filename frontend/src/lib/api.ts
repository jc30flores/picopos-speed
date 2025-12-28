export const API_BASE_URL = "http://localhost:8102";

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
  categoryId: number;
  image?: string | null;
  imageUrl?: string | null;
  available: boolean;
  modifierGroups: number[];
};

export type Discount = {
  id: number;
  name: string;
  description?: string;
  type: "percentage" | "fixed" | "happy-hour" | "category";
  value: number;
  appliesTo: "ticket" | "categories" | "products";
  targetCategoryIds?: number[];
  targetProductIds?: number[];
  days: number[];
  startTime?: string | null;
  endTime?: string | null;
  serviceTypeIds?: number[];
  minAmount?: number;
  requiresApproval: boolean;
  autoApply: boolean;
  active: boolean;
};

export type ServiceType = {
  id: number;
  key: string;
  label: string;
  isActive?: boolean;
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
};

export type SalesReportRow = {
  orderId: number;
  orderNumber: number;
  serviceType: Order["serviceType"];
  createdAt: Date;
  subtotal: number;
  tax: number;
  total: number;
  status: Order["status"];
};

const buildApiUrl = (path: string) => {
  if (!path.startsWith("/")) {
    return `${API_BASE_URL}/${path}`;
  }
  return `${API_BASE_URL}${path}`;
};

const handleJson = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "API request failed");
  }
  return response.json() as Promise<T>;
};

export const getCategories = async (): Promise<Category[]> => {
  const response = await fetch(buildApiUrl("/api/menu/categories/"));
  const data = await handleJson<Array<{ id: number; name: string; is_active: boolean }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    isActive: item.is_active,
  }));
};

export const createCategory = async (name: string): Promise<Category> => {
  const response = await fetch(buildApiUrl("/api/menu/categories/"), {
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
  const response = await fetch(buildApiUrl("/api/menu/products/"));
  const data = await handleJson<Array<{
    id: number;
    name: string;
    description: string;
    price: string;
    category: string;
    category_id_display?: number;
    image: string | null;
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
    categoryId: item.category_id_display ?? 0,
    image: item.image,
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

  const response = await fetch(buildApiUrl("/api/menu/products/"), {
    method: "POST",
    body: formData,
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    price: string;
    category: string;
    category_id_display?: number;
    image: string | null;
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
    categoryId: data.category_id_display ?? payload.categoryId,
    image: data.image,
    imageUrl: data.image_url ?? undefined,
    available: data.available,
    modifierGroups: data.modifier_groups,
  };
};

export const getModifierGroups = async (): Promise<ModifierGroup[]> => {
  const response = await fetch(buildApiUrl("/api/menu/modifier-groups/"));
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
  const response = await fetch(buildApiUrl("/api/menu/modifier-groups/"), {
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
  const response = await fetch(buildApiUrl("/api/menu/discounts/"));
  const data = await handleJson<Array<{
    id: number;
    name: string;
    description: string;
    type: Discount["type"];
    value: string;
    applies_to: Discount["appliesTo"];
    target_category_ids: number[];
    target_product_ids: number[];
    days: number[];
    start_time: string | null;
    end_time: string | null;
    service_type_ids: number[];
    min_amount: string;
    requires_approval: boolean;
    auto_apply: boolean;
    active: boolean;
  }>>(response);
  return data.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description,
    type: item.type,
    value: Number(item.value),
    appliesTo: item.applies_to,
    targetCategoryIds: item.target_category_ids ?? [],
    targetProductIds: item.target_product_ids ?? [],
    days: item.days,
    startTime: item.start_time ?? undefined,
    endTime: item.end_time ?? undefined,
    serviceTypeIds: item.service_type_ids ?? [],
    minAmount: Number(item.min_amount),
    requiresApproval: item.requires_approval,
    autoApply: item.auto_apply,
    active: item.active,
  }));
};

export const getServiceTypes = async (): Promise<ServiceType[]> => {
  const response = await fetch(buildApiUrl("/api/core/service-types/"));
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean }>>(response);
  return data.map((item) => ({
    id: item.id,
    key: item.key,
    label: item.label,
    isActive: item.is_active,
  }));
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
}): Order => {
  const createdAt = new Date(order.created_at);
  const prepTime = Math.floor((Date.now() - createdAt.getTime()) / 60000);
  return {
    id: order.id,
    orderNumber: order.order_number,
    items: order.items.map((item) => ({
      id: item.id,
      productName: item.product_name_snapshot,
      quantity: item.quantity,
      modifiers: item.applied_modifiers.map((modifier) => modifier.modifier_name_snapshot),
      price: Number(item.price_snapshot),
    })),
    total: Number(order.total),
    status: order.status,
    serviceType: order.service_type,
    createdAt,
    prepTime,
    customerName: order.customer_name || undefined,
  };
};

export const createOrder = async (payload: {
  serviceType: Order["serviceType"];
  customerName?: string;
  items: Array<{
    productId: number;
    productName: string;
    price: number;
    quantity: number;
    modifiers: Array<{ name: string; price: number }>;
  }>;
}): Promise<Order> => {
  const response = await fetch(buildApiUrl("/api/orders/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      service_type_key: payload.serviceType,
      customer_name: payload.customerName ?? "",
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
  const data = await handleJson<{
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
  }>(response);
  return mapOrder(data);
};

export const getActiveOrders = async (): Promise<Order[]> => {
  const response = await fetch(buildApiUrl("/api/orders/active/"));
  const data = await handleJson<
    Array<{
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
    }>
  >(response);
  return data.map(mapOrder);
};

export const updateOrderStatus = async (orderId: number, statusValue: Order["status"]): Promise<Order> => {
  const response = await fetch(buildApiUrl(`/api/orders/${orderId}/status/`), {
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
  const response = await fetch(buildApiUrl("/api/orders/customer-display/"));
  const data = await handleJson<
    Array<{ id: number; order_number: number; status: Order["status"]; customer_name: string; created_at: string }>
  >(response);
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
}): Promise<SalesReportRow[]> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.serviceType) params.set("service_type", filters.serviceType);
  if (filters?.status) params.set("status", filters.status);
  const query = params.toString();
  const response = await fetch(buildApiUrl(`/api/reports/sales/${query ? `?${query}` : ""}`));
  const data = await handleJson<
    Array<{
      order_id: number;
      order_number: number;
      service_type: Order["serviceType"];
      date: string;
      subtotal: string;
      tax: string;
      total: string;
      status: Order["status"];
    }>
  >(response);
  return data.map((row) => ({
    orderId: row.order_id,
    orderNumber: row.order_number,
    serviceType: row.service_type,
    createdAt: new Date(row.date),
    subtotal: Number(row.subtotal),
    tax: Number(row.tax),
    total: Number(row.total),
    status: row.status,
  }));
};

export const createDiscount = async (payload: Discount): Promise<Discount> => {
  const response = await fetch(buildApiUrl("/api/menu/discounts/"), {
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
      days: payload.days,
      start_time: payload.startTime ?? null,
      end_time: payload.endTime ?? null,
      service_type_ids: payload.serviceTypeIds ?? [],
      min_amount: payload.minAmount ?? 0,
      requires_approval: payload.requiresApproval,
      auto_apply: payload.autoApply,
      active: payload.active,
    }),
  });
  const data = await handleJson<{
    id: number;
    name: string;
    description: string;
    type: Discount["type"];
    value: string;
    applies_to: Discount["appliesTo"];
    target_category_ids: number[];
    target_product_ids: number[];
    days: number[];
    start_time: string | null;
    end_time: string | null;
    service_type_ids: number[];
    min_amount: string;
    requires_approval: boolean;
    auto_apply: boolean;
    active: boolean;
  }>(response);
  return {
    id: data.id,
    name: data.name,
    description: data.description,
    type: data.type,
    value: Number(data.value),
    appliesTo: data.applies_to,
    targetCategoryIds: data.target_category_ids ?? [],
    targetProductIds: data.target_product_ids ?? [],
    days: data.days,
    startTime: data.start_time ?? undefined,
    endTime: data.end_time ?? undefined,
    serviceTypeIds: data.service_type_ids ?? [],
    minAmount: Number(data.min_amount),
    requiresApproval: data.requires_approval,
    autoApply: data.auto_apply,
    active: data.active,
  };
};
