import { fromCents, moneyToFixedString, toCents } from "@/lib/money";
export const API_BASE_URL = import.meta.env.VITE_API_BASE ?? "/api";
const AUTH_DEBUG = String(import.meta.env.VITE_AUTH_DEBUG ?? "").toLowerCase() === "true";
const API_DEBUG = import.meta.env.DEV && import.meta.env.VITE_DEBUG === "true";

export type Category = {
  id: number;
  name: string;
  inventoryStockPolicy?: ProductInventoryStockPolicy;
  posProductImagesPolicy?: PosImagePolicy;
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

export type ProductInventoryStockPolicy = "inherit" | "allow" | "warn" | "block";
export type PosImagePolicy = "inherit" | "show" | "hide";

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
  inventoryLinks?: InventoryProductLink[];
  inventoryStockPolicy?: ProductInventoryStockPolicy;
  posImagePolicy?: PosImagePolicy;
  inventoryComponentsEnabled?: boolean;
  trackInventory?: boolean;
  trackedInventoryItem?: number | null;
  trackedInventoryItemName?: string | null;
  trackedInventoryItemUnit?: string | null;
  trackedInventoryItemCurrentStock?: number | null;
  trackedInventoryQuantity?: number;
  autoCreatedInventoryItem?: boolean;
  trackedInventoryWarning?: string;
};

export type ProductInventoryTrackingCreatePayload = {
  name: string;
  sku?: string;
  unit: string;
  currentStock?: number;
  minStock?: number | null;
  maxStock?: number | null;
};

export type InventorySupplier = {
  id: number;
  name: string;
  code?: string;
  contactName?: string;
  phone?: string;
  email?: string;
  address?: string;
  taxId?: string;
  notes?: string;
  isActive: boolean;
};

export type InventoryItem = {
  id: number;
  name: string;
  sku: string;
  unit: string;
  currentStock: number;
  minStock?: number | null;
  maxStock?: number | null;
  supplier?: number | null;
  supplierName?: string | null;
  unitCost?: number | null;
  supplierCode?: string;
  purchaseUnit?: string;
  purchaseToInventoryFactor?: number;
  notes?: string;
  isActive: boolean;
};

export type PurchaseOrderLine = {
  id?: number;
  inventoryItem: number;
  inventoryItemName?: string;
  inventoryItemSku?: string;
  inventoryItemUnit?: string;
  description?: string;
  quantityOrdered: number;
  quantityReceived?: number;
  pendingQuantity?: number;
  purchaseUnit?: string;
  purchaseToInventoryFactor: number;
  inventoryQuantityOrdered?: number;
  unitCost: number;
  subtotal?: number;
  notes?: string;
};

export type PurchaseOrder = {
  id: number;
  code: string;
  supplier: number;
  supplierName: string;
  status: string;
  statusLabel: string;
  paymentCategory: string;
  expectedDate?: string | null;
  notes?: string;
  proofReference?: string;
  proofUrl?: string;
  subtotal: number;
  total: number;
  createdByUsername?: string;
  createdAt: string;
  approvedAt?: string | null;
  cancelReason?: string;
  receivedPercent?: number;
  lines: PurchaseOrderLine[];
};

export type InventoryMovement = {
  id: number;
  inventoryItem: number;
  inventoryItemName: string;
  inventoryItemSku?: string;
  inventoryItemUnit?: string;
  movementType: string;
  quantityChange: number;
  quantityBefore: number;
  quantityAfter: number;
  reason?: string;
  referenceType?: string;
  referenceId?: string;
  createdByUsername?: string;
  createdAt: string;
};


export type InventoryCountLine = {
  id: number;
  session: number;
  inventoryItem: number;
  inventoryItemName: string;
  inventoryItemSku: string;
  inventoryItemUnit: string;
  systemStock: number;
  countedStock: number | null;
  difference: number;
  note: string;
  stockBeforeApply: number | null;
  stockAfterApply: number | null;
  movement: number | null;
  createdAt: string;
  updatedAt: string;
};

export type InventoryCountSession = {
  id: number;
  code: string;
  countType: "complete" | "manual" | "category" | string;
  countTypeDisplay: string;
  status: "draft" | "in_progress" | "finalized" | "applied" | "cancelled" | string;
  statusDisplay: string;
  notes: string;
  createdByUsername?: string;
  createdAt: string;
  updatedAt: string;
  finalizedAt?: string | null;
  appliedAt?: string | null;
  cancelledAt?: string | null;
  cancelReason?: string;
  totalItems: number;
  countedItems: number;
  totalDifferences: number;
  totalPositiveDifferences: number;
  totalNegativeDifferences: number;
  lines?: InventoryCountLine[];
};

export type InventoryProductLink = {
  id?: number;
  inventoryItemId: number;
  inventoryItemName: string;
  inventoryItemUnit: string;
  quantityRequired: number;
  origin?: "inherited" | "override" | "direct" | "disabled";
  categoryLinkId?: number;
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
  colorHex?: string | null;
};





export type PosQuickSalesButtonMode = "last_sale" | "history" | "hidden";
export type PosQuickSalesHistoryScope = "current_shift" | "time_window";
export type PosQuickSalesHistoryWindowMinutes = 15 | 30 | 60 | 120 | 240 | 1440;

type FeatureFlagsNormalized = {
  posEnabled: boolean;
  openOrdersEnabled: boolean;
  kioskEnabled: boolean;
  customerDisplayEnabled: boolean;
  kitchenDisplayEnabled: boolean;
  menuDiscountsEnabled: boolean;
  inventoryModuleEnabled: boolean;
  reportsEnabled: boolean;
  clientsEnabled: boolean;
  settingsEnabled: boolean;
  dteEnabled: boolean;
  whatsappEnabled: boolean;
  emailEnabled: boolean;
  cashCloseExpectedTotalsControlEnabled: boolean;
  inventoryStockPolicy: InventoryStockPolicy;
  inventoryAdvancedEnabled: boolean;
  posProductImagesEnabled: boolean;
  tableMapEnabled: boolean;
  operationMode: OperationMode;
  defaultPosEntry: DefaultPosEntry;
  allowTableMerge: boolean;
  allowTableTransfer: boolean;
  allowSplitByGuest: boolean;
  allowSplitByItem: boolean;
  posQuickSalesButtonMode: PosQuickSalesButtonMode;
  posQuickSalesHistoryScope: PosQuickSalesHistoryScope;
  posQuickSalesHistoryWindowMinutes: PosQuickSalesHistoryWindowMinutes;
};

export type OperationMode = "quick_pos" | "table_service" | "both";
export type DefaultPosEntry = "quick_pos" | "table_map";

const normalizeOperationMode = (value: unknown): OperationMode => {
  const normalized = String(value ?? "quick_pos").trim().toLowerCase();
  return normalized === "table_service" || normalized === "both" || normalized === "quick_pos" ? normalized : "quick_pos";
};

const normalizeDefaultPosEntry = (value: unknown, operationMode: OperationMode): DefaultPosEntry => {
  const normalized = String(value ?? (operationMode === "table_service" ? "table_map" : "quick_pos")).trim().toLowerCase();
  if (operationMode === "quick_pos") return "quick_pos";
  return normalized === "table_map" ? "table_map" : "quick_pos";
};

const normalizePosQuickSalesMode = (value: unknown): PosQuickSalesButtonMode => {
  const normalized = String(value ?? "last_sale").trim().toLowerCase();
  return normalized === "history" || normalized === "hidden" || normalized === "last_sale" ? normalized : "last_sale";
};

const normalizePosQuickSalesHistoryScope = (value: unknown): PosQuickSalesHistoryScope => {
  const normalized = String(value ?? "current_shift").trim().toLowerCase();
  return normalized === "time_window" || normalized === "current_shift" ? normalized : "current_shift";
};

const normalizePosQuickSalesHistoryWindow = (value: unknown): PosQuickSalesHistoryWindowMinutes => {
  const parsed = Number(value ?? 60);
  return ([15, 30, 60, 120, 240, 1440] as const).includes(parsed as PosQuickSalesHistoryWindowMinutes) ? parsed as PosQuickSalesHistoryWindowMinutes : 60;
};

export const normalizeFeatureFlags = (raw: any): FeatureFlagsNormalized => {
  const defaults: FeatureFlagsNormalized = {
    posEnabled: true,
    openOrdersEnabled: true,
    kioskEnabled: true,
    customerDisplayEnabled: true,
    kitchenDisplayEnabled: true,
    menuDiscountsEnabled: true,
    inventoryModuleEnabled: true,
    reportsEnabled: true,
    clientsEnabled: true,
    settingsEnabled: true,
    dteEnabled: false,
    whatsappEnabled: true,
    emailEnabled: true,
    cashCloseExpectedTotalsControlEnabled: true,
    inventoryStockPolicy: "allow",
    inventoryAdvancedEnabled: false,
    posProductImagesEnabled: false,
    tableMapEnabled: false,
    operationMode: "quick_pos",
    defaultPosEntry: "quick_pos",
    allowTableMerge: true,
    allowTableTransfer: true,
    allowSplitByGuest: true,
    allowSplitByItem: true,
    posQuickSalesButtonMode: "last_sale",
    posQuickSalesHistoryScope: "current_shift",
    posQuickSalesHistoryWindowMinutes: 60,
  };
  const fromMap = (obj: any, keys: string[], fallback: boolean) => {
    for (const k of keys) {
      if (obj && Object.prototype.hasOwnProperty.call(obj, k) && typeof obj[k] === 'boolean') return obj[k];
    }
    return fallback;
  };
  if (Array.isArray(raw)) {
    const rowsByKey = Object.fromEntries(raw.map((r: any) => [String(r?.key ?? ''), r]));
    const byKey = Object.fromEntries(raw.map((r: any) => [String(r?.key ?? ''), Boolean(r?.enabled ?? r?.is_enabled)]));
    const tableRow = rowsByKey.table_map_enabled ?? {};
    const tableMetadata = tableRow.metadata && typeof tableRow.metadata === "object" ? tableRow.metadata : {};
    const tableMapEnabled = fromMap(byKey, ['table_map_enabled'], defaults.tableMapEnabled);
    const operationMode = normalizeOperationMode(tableMetadata.operation_mode ?? (tableMapEnabled ? "both" : "quick_pos"));
    const defaultPosEntry = normalizeDefaultPosEntry(tableMetadata.default_pos_entry, operationMode);
    return {
      posEnabled: fromMap(byKey, ['module_pos_enabled'], defaults.posEnabled),
      openOrdersEnabled: fromMap(byKey, ['module_open_orders_enabled'], defaults.openOrdersEnabled),
      kioskEnabled: fromMap(byKey, ['FF_KIOSK_ENABLED'], defaults.kioskEnabled),
      customerDisplayEnabled: fromMap(byKey, ['FF_CUSTOMER_DISPLAY_ENABLED'], defaults.customerDisplayEnabled),
      kitchenDisplayEnabled: fromMap(byKey, ['FF_KITCHEN_DISPLAY_ENABLED'], defaults.kitchenDisplayEnabled),
      menuDiscountsEnabled: fromMap(byKey, ['module_menu_discounts_enabled'], defaults.menuDiscountsEnabled),
      inventoryModuleEnabled: fromMap(byKey, ['module_inventory_enabled', 'FF_INVENTORY'], defaults.inventoryModuleEnabled),
      reportsEnabled: fromMap(byKey, ['module_reports_enabled'], defaults.reportsEnabled),
      clientsEnabled: fromMap(byKey, ['module_clients_enabled'], defaults.clientsEnabled),
      settingsEnabled: fromMap(byKey, ['module_settings_enabled'], defaults.settingsEnabled),
      dteEnabled: fromMap(byKey, ['dte_visible', 'can_send_dte'], defaults.dteEnabled),
      whatsappEnabled: fromMap(byKey, ['fiscal_whatsapp_enabled'], defaults.whatsappEnabled),
      emailEnabled: fromMap(byKey, ['fiscal_email_enabled'], defaults.emailEnabled),
      cashCloseExpectedTotalsControlEnabled: fromMap(byKey, ['FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED'], defaults.cashCloseExpectedTotalsControlEnabled),
      inventoryStockPolicy: defaults.inventoryStockPolicy,
      inventoryAdvancedEnabled: fromMap(byKey, ['FF_INVENTORY'], defaults.inventoryAdvancedEnabled),
      posProductImagesEnabled: fromMap(byKey, ['pos_product_images_enabled'], defaults.posProductImagesEnabled),
      tableMapEnabled: operationMode !== "quick_pos" && tableMapEnabled,
      operationMode,
      defaultPosEntry,
      allowTableMerge: Boolean(tableMetadata.allow_table_merge ?? defaults.allowTableMerge),
      allowTableTransfer: Boolean(tableMetadata.allow_table_transfer ?? defaults.allowTableTransfer),
      allowSplitByGuest: Boolean(tableMetadata.allow_split_by_guest ?? defaults.allowSplitByGuest),
      allowSplitByItem: Boolean(tableMetadata.allow_split_by_item ?? defaults.allowSplitByItem),
      posQuickSalesButtonMode: defaults.posQuickSalesButtonMode,
      posQuickSalesHistoryScope: defaults.posQuickSalesHistoryScope,
      posQuickSalesHistoryWindowMinutes: defaults.posQuickSalesHistoryWindowMinutes,
    };
  }
  const operationMode = normalizeOperationMode(raw?.operationMode ?? raw?.operation_mode ?? (fromMap(raw, ['tableMapEnabled', 'table_map_enabled'], defaults.tableMapEnabled) ? "both" : "quick_pos"));
  const defaultPosEntry = normalizeDefaultPosEntry(raw?.defaultPosEntry ?? raw?.default_pos_entry, operationMode);
  return {
    posEnabled: fromMap(raw, ['posEnabled', 'pos_enabled'], defaults.posEnabled),
    openOrdersEnabled: fromMap(raw, ['openOrdersEnabled', 'open_orders_enabled'], defaults.openOrdersEnabled),
    kioskEnabled: fromMap(raw, ['kioskEnabled', 'kiosk_enabled', 'FF_KIOSK_ENABLED'], defaults.kioskEnabled),
    customerDisplayEnabled: fromMap(raw, ['customerDisplayEnabled', 'customer_display_enabled', 'FF_CUSTOMER_DISPLAY_ENABLED'], defaults.customerDisplayEnabled),
    kitchenDisplayEnabled: fromMap(raw, ['kitchenDisplayEnabled', 'kitchen_display_enabled', 'FF_KITCHEN_DISPLAY_ENABLED'], defaults.kitchenDisplayEnabled),
    menuDiscountsEnabled: fromMap(raw, ['menuDiscountsEnabled', 'menu_discounts_enabled'], defaults.menuDiscountsEnabled),
    inventoryModuleEnabled: fromMap(raw, ['inventoryModuleEnabled', 'inventory_module_enabled'], defaults.inventoryModuleEnabled),
    reportsEnabled: fromMap(raw, ['reportsEnabled', 'reports_enabled'], defaults.reportsEnabled),
    clientsEnabled: fromMap(raw, ['clientsEnabled', 'clients_enabled'], defaults.clientsEnabled),
    settingsEnabled: fromMap(raw, ['settingsEnabled', 'settings_enabled'], defaults.settingsEnabled),
    dteEnabled: fromMap(raw, ['dteEnabled', 'dte_visible', 'can_send_dte'], defaults.dteEnabled),
    whatsappEnabled: fromMap(raw, ['whatsappEnabled', 'fiscal_whatsapp_enabled'], defaults.whatsappEnabled),
    emailEnabled: fromMap(raw, ['emailEnabled', 'fiscal_email_enabled'], defaults.emailEnabled),
    cashCloseExpectedTotalsControlEnabled: fromMap(raw, ['cashCloseExpectedTotalsControlEnabled', 'cash_close_expected_totals_control_enabled', 'FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED'], defaults.cashCloseExpectedTotalsControlEnabled),
    inventoryStockPolicy: normalizeInventoryStockPolicy(raw?.inventoryStockPolicy ?? raw?.inventory_stock_policy),
    inventoryAdvancedEnabled: fromMap(raw, ['inventoryAdvancedEnabled', 'inventory_advanced_enabled', 'FF_INVENTORY'], defaults.inventoryAdvancedEnabled),
    posProductImagesEnabled: fromMap(raw, ['posProductImagesEnabled', 'pos_product_images_enabled'], defaults.posProductImagesEnabled),
    tableMapEnabled: operationMode !== "quick_pos" && fromMap(raw, ['tableMapEnabled', 'table_map_enabled'], defaults.tableMapEnabled),
    operationMode,
    defaultPosEntry,
    allowTableMerge: fromMap(raw, ['allowTableMerge', 'allow_table_merge'], defaults.allowTableMerge),
    allowTableTransfer: fromMap(raw, ['allowTableTransfer', 'allow_table_transfer'], defaults.allowTableTransfer),
    allowSplitByGuest: fromMap(raw, ['allowSplitByGuest', 'allow_split_by_guest'], defaults.allowSplitByGuest),
    allowSplitByItem: fromMap(raw, ['allowSplitByItem', 'allow_split_by_item'], defaults.allowSplitByItem),
    posQuickSalesButtonMode: normalizePosQuickSalesMode(raw?.posQuickSalesButtonMode ?? raw?.pos_quick_sales_button_mode),
    posQuickSalesHistoryScope: normalizePosQuickSalesHistoryScope(raw?.posQuickSalesHistoryScope ?? raw?.pos_quick_sales_history_scope),
    posQuickSalesHistoryWindowMinutes: normalizePosQuickSalesHistoryWindow(raw?.posQuickSalesHistoryWindowMinutes ?? raw?.pos_quick_sales_history_window_minutes),
  };
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

export type InventoryStockPolicy = "allow" | "warn" | "block";

const normalizeInventoryStockPolicy = (value: unknown): InventoryStockPolicy => {
  const policy = String(value || "allow").toLowerCase();
  return policy === "warn" || policy === "block" ? policy : "allow";
};

const normalizeProductInventoryStockPolicy = (value: unknown): ProductInventoryStockPolicy => {
  const policy = String(value || "inherit").toLowerCase();
  return policy === "allow" || policy === "warn" || policy === "block" ? policy : "inherit";
};

const normalizePosImagePolicy = (value: unknown): PosImagePolicy => {
  const policy = String(value || "inherit").toLowerCase();
  return policy === "show" || policy === "hide" ? policy : "inherit";
};

type CategoryApiPayload = {
  id: number;
  name: string;
  image?: string | null;
  image_url?: string | null;
  image_path?: string | null;
  is_active: boolean;
  is_hidden?: boolean;
  position?: number;
  inventory_stock_policy?: ProductInventoryStockPolicy;
  pos_product_images_policy?: PosImagePolicy;
};

const normalizeCategory = (data: CategoryApiPayload): Category => ({
  id: data.id,
  name: data.name,
  image: data.image ?? null,
  imagePath: data.image_path ?? null,
  imageUrl: normalizeImageUrl(data),
  isActive: data.is_active,
  isHidden: Boolean(data.is_hidden),
  position: Number(data.position ?? 0),
  inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
  posProductImagesPolicy: normalizePosImagePolicy(data.pos_product_images_policy),
});

const appendProductInventoryTrackingFormData = (formData: FormData, payload: {
  inventoryComponentsEnabled?: boolean;
  trackInventory?: boolean;
  trackedInventoryItem?: number | null;
  trackedInventoryQuantity?: number;
  newInventoryItem?: ProductInventoryTrackingCreatePayload | null;
}) => {
  formData.append("inventory_components_enabled", (payload.inventoryComponentsEnabled ?? true) ? "true" : "false");
  formData.append("track_inventory", payload.trackInventory ? "true" : "false");
  formData.append("tracked_inventory_quantity", String(payload.trackedInventoryQuantity ?? 1));
  if (payload.trackedInventoryItem) {
    formData.append("tracked_inventory_item", String(payload.trackedInventoryItem));
  }
  if (payload.newInventoryItem) {
    formData.append("new_inventory_item", JSON.stringify({
      name: payload.newInventoryItem.name,
      sku: payload.newInventoryItem.sku ?? "",
      unit: payload.newInventoryItem.unit,
      current_stock: payload.newInventoryItem.currentStock ?? 0,
      min_stock: payload.newInventoryItem.minStock ?? null,
      max_stock: payload.newInventoryItem.maxStock ?? null,
    }));
  }
};

const mapProductInventoryFields = (data: any) => ({
  inventoryComponentsEnabled: Boolean(data.inventory_components_enabled ?? true),
  trackInventory: Boolean(data.track_inventory),
  trackedInventoryItem: data.tracked_inventory_item != null ? Number(data.tracked_inventory_item) : null,
  trackedInventoryItemName: data.tracked_inventory_item_name ?? null,
  trackedInventoryItemUnit: data.tracked_inventory_item_unit ?? null,
  trackedInventoryItemCurrentStock: data.tracked_inventory_item_current_stock != null ? Number(data.tracked_inventory_item_current_stock) : null,
  trackedInventoryQuantity: Number(data.tracked_inventory_quantity ?? 1),
  autoCreatedInventoryItem: Boolean(data.auto_created_inventory_item),
  trackedInventoryWarning: String(data.tracked_inventory_warning ?? ""),
});

export type FeatureFlag = {
  id: number;
  key: string;
  label: string;
  description?: string;
  isEnabled: boolean;
};

export type FeatureSettings = {
  posEnabled: boolean;
  openOrdersEnabled: boolean;
  kioskEnabled: boolean;
  customerDisplayEnabled: boolean;
  kitchenDisplayEnabled: boolean;
  menuDiscountsEnabled: boolean;
  reportsEnabled: boolean;
  clientsEnabled: boolean;
  settingsEnabled: boolean;
  cashCloseExpectedTotalsControlEnabled: boolean;
  cashCloseExpectedTotalsAllowedRoles: string[];
  cashCloseExpectedTotalsVisibleFields: string[];
  inventoryStockPolicy: InventoryStockPolicy;
  inventoryAdvancedEnabled: boolean;
  posProductImagesEnabled: boolean;
  tableMapEnabled: boolean;
  operationMode: OperationMode;
  defaultPosEntry: DefaultPosEntry;
  allowTableMerge: boolean;
  allowTableTransfer: boolean;
  allowSplitByGuest: boolean;
  allowSplitByItem: boolean;
  posQuickSalesButtonMode: PosQuickSalesButtonMode;
  posQuickSalesHistoryScope: PosQuickSalesHistoryScope;
  posQuickSalesHistoryWindowMinutes: PosQuickSalesHistoryWindowMinutes;
};

export type AppearanceSettings = {
  primaryColor: string;
  colorPrimary: string;
  colorPrimaryHover: string;
  colorPrimarySoft: string;
  colorPrimaryBorder: string;
  colorPrimaryText: string;
  colorPrimaryContrast: string;
  cssVariables: Record<string, string>;
  palette?: string[];
};

export type PublicPwaMetadata = {
  appName: string;
  shortName: string;
  description: string;
  siteName: string;
  themeColor: string;
  backgroundColor: string;
  display: "standalone" | "fullscreen" | "minimal-ui" | "browser";
  orientation: string;
  startUrl: string;
  scope: string;
  version: string;
  brandingVersion: string;
  logoVersion: string;
  hasCustomerLogo: boolean;
  customerLogoUrl: string | null;
  ticketLogoUrl: string | null;
  manifestUrl: string;
  icon192Url: string;
  icon512Url: string;
  maskableIconUrl: string;
  appleTouchIconUrl: string;
  faviconUrl: string;
  shareImageUrl: string;
};

export type DteIssuerSettings = {
  legalName: string;
  commercialName: string;
  documentType: string;
  nit: string;
  dui: string;
  nrc: string;
  activityCode: string;
  activityDescription: string;
  establishmentType: string;
  department: string;
  municipality: string;
  address: string;
  phone: string;
  email: string;
};

export type DteBranchSettings = {
  id?: number | null;
  name: string;
  code: string;
  address: string;
  establishmentCodeMh: string;
  establishmentCode: string;
  posCodeMh: string;
  posCode: string;
  establishmentType: string;
  branchAddress: string;
  phone: string;
  email: string;
  active: boolean;
};

export type DteCorrelative = {
  id: number;
  tipoDte: string;
  label: string;
  ambiente: "00" | "01";
  environment: string;
  branchName: string;
  year: number;
  establishmentCode: string;
  posCode: string;
  lastNumber: number;
  nextNumber: number;
  active: boolean;
  updatedAt?: string | null;
};

export type DteSettings = {
  haciendaEnabled: boolean;
  ambiente: "00" | "01";
  baseUrl: string;
  apiTokenMasked: string;
  timeoutSeconds: number;
  retryCount: number;
  fiscalEmailEnabled: boolean;
  fiscalWhatsappEnabled: boolean;
  fiscalPdfEnabled: boolean;
  fiscalJsonEnabled: boolean;
  status: string;
  lastConnectionTestAt: string | null;
  lastErrorSanitized: string;
  canManageTechnical: boolean;
  permissions?: {
    canViewBasic: boolean;
    canEditTechnical: boolean;
    canEditCorrelatives: boolean;
    isSuperadmin: boolean;
  };
  issuer: DteIssuerSettings;
  branch: DteBranchSettings;
  correlatives: DteCorrelative[];
  pendingFields: string[];
  apiTokenConfigured: boolean;
  message?: string;
};

export type TicketSettings = {
  ticketLogoUrl: string | null;
  ticketLogoVersion: string;
  ticketLogoName: string | null;
  hasTicketLogo: boolean;
};

export type FeatureSettingsOptions = {
  roles: Array<{ code: string; label: string }>;
  cashCloseExpectedTotalFields: Array<{ code: string; label: string }>;
};

export type BusinessHoursSettings = {
  businessHoursEnabled: boolean;
  openingTime: string;
  closingTime: string;
  graceHoursAfterClose: number;
  timezone: string;
  autoCloseCashEnabled: boolean;
  autoCloseCountZero: boolean;
  updatedAt?: string | null;
};

export type TransactionTicketPayload = {
  paymentId: number;
  orderId: number;
  ticketText: string;
  ticketHtml: string;
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
  discountName?: string;
  unitPriceFinal?: number;
  lineTotalBeforeDiscount?: number;
  lineTotalDiscount?: number;
  lineTotalFinal?: number;
  pricingMetadata?: Record<string, unknown> | null;
  unitPriceOverride?: number | null;
  assignedName?: string;
  guestNumber?: number | null;
  guestLabel?: string;
  tableGuestId?: number | null;
  tableGuestLabel?: string;
  tableGuestSeatNumber?: number | null;
  requiresKitchen?: boolean;
  kitchenStatus?: "pending" | "sent" | "ready" | "delivered";
  kitchenStatusLabel?: string;
  kitchenSentAt?: string | null;
  kitchenReadyAt?: string | null;
  kitchenDeliveredAt?: string | null;
  kitchenCompletedAt?: string | null;
  kitchenServedAt?: string | null;
  isPendingKitchen?: boolean;
  isInKitchen?: boolean;
  isCompleted?: boolean;
  isServed?: boolean;
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
  whatsappNumCliente?: string;
  whatsappNumClienteCountry?: string;
  dteDocumentType?: "CF" | "CCF" | "SX";
  ivaExempt?: boolean;
  ivaExemptDiscount?: number;
  paymentStatus: "unpaid" | "partial" | "paid";
  financialStatus: "open" | "paid" | "refunded_partial" | "refunded_full" | "voided";
  totalPaid: number;
  remaining: number;
  grossSubtotal?: number;
  netTotal?: number;
  paidTotal?: number;
  amountDue?: number;
  amountDueCents?: number;
  remainingCents?: number;
  refundTotal: number;
  netPaid: number;
  discountSnapshot?: Record<string, unknown> | null;
  requiresKitchen?: boolean;
  sendToKitchen?: boolean;
  discountTotal?: number;
  disposableTotal?: number;
  subtotalBeforeDiscounts?: number;
  subtotalAfterDiscounts?: number;
  taxTotal?: number;
  totalPayable?: number;
  isPending?: boolean;
  pendingState?: "none" | "pending_payment" | "paid_pending_delivery" | "in_kitchen" | "ready";
  pendingReference?: string;
  pendingMarkedAt?: string | null;
  pendingCompletedAt?: string | null;
  pendingCompletionType?: "none" | "paid" | "removed" | "canceled";
  pendingCompletionNote?: string;
  tableSessionId?: number | null;
  tableLabel?: string;
  tableOrderMode?: "table" | "per_person" | null;
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
  isIvaExempt: boolean;
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
  isActive: boolean;
  colorHex?: string | null;
  isDefault?: boolean;
  fiscalPaymentType?: "CASH" | "CARD" | "TRANSFER";
  linkedOrderTypeId?: number | null;
  linkedOrderTypeName?: string | null;
  autoPrintTicket?: boolean;
};

export type CashSessionSnapshot = {
  open: boolean;
  hasOpenCashSession?: boolean;
  canOpenCash?: boolean;
  canCloseCash?: boolean;
  pendingOpenOrdersCount?: number;
  cashAutoClose?: { closed?: number; skipped?: number; details?: unknown[] };
  lastOpenedAt?: string | null;
  lastClosedAt?: string | null;
  totalSessionsToday?: number;
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
    countedBills: number;
    countedCoins: number;
    countedPosCards: number;
    countedPedidosYa: number;
    overShortCash: number;
    methods: { cash: number; card: number; cardDebit: number; cardCredit: number; transfer: number; pedidosYa: number; payPal: number; cashIn: number };
  };
};

export type LastSaleAction = {
  id: number;
  orderId: number;
  paymentId: number;
  orderNumber: string;
  controlNumber: string;
  customerName: string;
  paymentMethod: string;
  total: number;
  status: string;
  createdAt: string;
  canPrintTicket: boolean;
  canSendDte: boolean;
};

export type RecentSaleAction = {
  id: number;
  paymentId: number;
  orderNumber: string;
  controlNumber: string;
  customerName: string;
  paymentMethod: string;
  total: number;
  status: string;
  createdAt: string;
  canPrintTicket: boolean;
  canSendDte: boolean;
};

export type CashTransaction = {
  id: number;
  type: "cash_out" | "cash_in" | "expense" | "payout" | "card" | "transfer" | "pedidosya" | "paypal";
  displayType?: string;
  impactsCash?: boolean;
  amount: number;
  description: string;
  paymentId?: number | null;
  refundId?: number | null;
  orderId?: number | null;
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
  allocations?: PaymentAllocation[];
};

export type PaymentAllocation = {
  id: number;
  tableSessionId?: number | null;
  tableGuestId?: number | null;
  orderItemId?: number | null;
  guestNumber?: number | null;
  guestLabel?: string;
  amount: number;
  amountCents: number;
  createdAt?: Date | null;
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

export type EmployeeWorkedHoursRow = {
  employeeId: number;
  employeeName: string;
  totalMinutes: number;
  totalHours: number;
};

export type EmployeeWorkedHoursReport = {
  rows: EmployeeWorkedHoursRow[];
  totals: {
    totalMinutes: number;
    totalHours: number;
  };
};

export type EmployeeHoursSummaryRow = {
  employeeId: number;
  name: string;
  role: string;
  daysWorked: number;
  entriesCount: number;
  exitsCount: number;
  shiftMinutes: number;
  breakMinutes: number;
  netMinutes: number;
  currentState: string;
  status: string;
};

export type EmployeeHoursSummaryResponse = {
  dateFrom: string;
  dateTo: string;
  totals: {
    employeeCount: number;
    totalShiftMinutes: number;
    totalBreakMinutes: number;
    totalNetMinutes: number;
    totalHours: number;
  };
  employees: EmployeeHoursSummaryRow[];
};

export type EmployeeHoursDetailResponse = {
  employee: { id: number; name: string; role: string };
  totals: { shiftMinutes: number; breakMinutes: number; netMinutes: number };
  days: Array<{
    date: string;
    dailyTotals: { shiftMinutes: number; breakMinutes: number; netMinutes: number };
    cycles: Array<{
      id: number;
      clockInAt: string | null;
      breakStartAt: string | null;
      breakEndAt: string | null;
      clockOutAt: string | null;
      shiftMinutes: number;
      breakMinutes: number;
      breakSeconds: number;
      netMinutes: number;
      clockOutNextDay: boolean;
      status: string;
    }>;
  }>;
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
  role: "superadmin" | "admin" | "manager" | "cashier" | "waiter" | "kitchen" | "kiosk" | "worker" | "accountant";
  isSuperuser: boolean;
  isStaff: boolean;
  redirectTo?: string;
  permissions?: {
    isSuperadmin?: boolean;
    canManageFeatures?: boolean;
    canManageDteSettings?: boolean;
    canManageCorrelatives?: boolean;
    canManageAppearance?: boolean;
  };
};

type AuthPayload = AuthUser & {
  is_superuser?: boolean;
  is_staff?: boolean;
  redirect_to?: string;
  user?: Partial<AuthUser> & { is_superuser?: boolean; is_staff?: boolean };
  profile?: { role?: AuthUser["role"]; redirect_to?: string; redirectTo?: string };
  permissions?: {
    is_superadmin?: boolean;
    isSuperadmin?: boolean;
    can_manage_features?: boolean;
    canManageFeatures?: boolean;
    can_manage_dte_settings?: boolean;
    canManageDteSettings?: boolean;
    can_manage_correlatives?: boolean;
    canManageCorrelatives?: boolean;
    can_manage_appearance?: boolean;
    canManageAppearance?: boolean;
  };
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
  payload?: unknown;

  constructor(message: string, options?: { code?: string; status?: number; isNetworkError?: boolean; payload?: unknown }) {
    super(message);
    this.name = "ApiRequestError";
    this.code = options?.code;
    this.status = options?.status;
    this.isNetworkError = Boolean(options?.isNetworkError);
    this.payload = options?.payload;
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
  hasActiveSession: false,
  latestEvent: "NONE",
  lastClockIn: null,
  lastClockOut: null,
  totalEntriesToday: 0,
  totalExitsToday: 0,
  canClockIn: true,
  canBreakStart: false,
  canBreakEnd: false,
  canClockOut: false,
  state: "OFF_SHIFT",
  accessAllowed: false,
  activeCycle: null,
  cyclesToday: [],
});

type ApiRequestOptions = RequestInit & { public?: boolean };

const SESSION_EXPIRY_CODES = new Set(["session_expired", "idle_timeout", "max_session_age"]);

const getSessionExpiryMessage = (code?: string, fallback?: string) => {
  if (code === "idle_timeout") return "Tu sesión se cerró por inactividad.";
  if (code === "max_session_age") return "Tu sesión venció por seguridad. Ingresa nuevamente.";
  return fallback || "Tu sesión expiró. Ingresa nuevamente.";
};

const dispatchSessionExpired = (code?: string, detail?: string) => {
  const message = getSessionExpiryMessage(code, detail);
  window.dispatchEvent(new CustomEvent("auth:session-expired", { detail: { code: code || "session_expired", message } }));
  window.dispatchEvent(new CustomEvent("auth:unauthorized", { detail: { code: code || "session_expired", message } }));
};

const request = async (path: string, options: ApiRequestOptions = {}) => {
  const { public: explicitPublicRequest, ...fetchOptions } = options;
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedPathKey = normalizedPath.endsWith("/") ? normalizedPath.slice(0, -1) : normalizedPath;
  const isPublicRequest = Boolean(explicitPublicRequest) || normalizedPath.startsWith("/public/");

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
  if (options.body === 0 || options.body === "0") {
    console.error("INVALID_API_BODY_ZERO", { path, method, body: options.body });
    throw new Error("Invalid API body: 0");
  }

  try {
    response = await fetch(buildApiUrl(path), {
      credentials: isPublicRequest ? "omit" : "include",
      ...fetchOptions,
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
  if (response.status === 401 && !isPublicRequest) {
    const payload = await response.clone().json().catch(() => null);
    const code = payload && typeof payload.code === "string" ? String(payload.code) : undefined;
    const detail = payload && typeof payload.detail === "string" ? String(payload.detail) : undefined;
    const isExplicitSessionExpiry = Boolean(code && SESSION_EXPIRY_CODES.has(code));
    if (isExplicitSessionExpiry || normalizedPathKey === "/auth/me" || !authBypassUnauthorizedEvent.has(normalizedPathKey)) {
      dispatchSessionExpired(code, detail);
    }
    console.info("AUTH_SESSION_EXPIRED", {
      status: 401,
      endpoint: normalizedPath,
      action: "logout",
      code: code || "unauthorized",
    });
  }
  if (response.status === 403 && !isPublicRequest && !authBypassUnauthorizedEvent.has(normalizedPathKey)) {
    console.info("AUTH_FORBIDDEN_NON_AUTH", {
      endpoint: normalizedPath,
      action: "keep_session",
    });
  }
  if (response.status === 403 && !isPublicRequest && normalizedPathKey === "/auth/me") {
    const payload = await response.clone().json().catch(() => null);
    const detail = payload && typeof payload.detail === "string" ? String(payload.detail) : undefined;
    dispatchSessionExpired("session_expired", detail);
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
      let fieldMessage = "";
      if (!detailText && errorPayload && typeof errorPayload === "object") {
        const firstValue = Object.values(errorPayload as Record<string, unknown>)[0];
        if (Array.isArray(firstValue)) fieldMessage = String(firstValue[0] ?? "");
        else if (typeof firstValue === "string") fieldMessage = firstValue;
      }
      const message = detailText || fieldMessage || (errorPayload ? JSON.stringify(errorPayload) : "");
      throw new ApiRequestError(message || `Error del servidor (${response.status}). Revisa el backend.`, {
        code: errorCode,
        status: response.status,
        payload: errorPayload,
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
  const rawPermissions = raw.permissions ?? {};
  const rawRole = String(raw.role ?? nestedProfile.role ?? "cashier").toLowerCase();
  const normalizedRole = ({
    cajero: "cashier",
    cocina: "kitchen",
    gerente: "manager",
    mesero: "waiter",
  } as Record<string, AuthUser["role"]>)[rawRole] ?? rawRole;
  return {
    id: Number(raw.id ?? nestedUser.id ?? 0),
    username: String(raw.username ?? nestedUser.username ?? ""),
    email: String(raw.email ?? nestedUser.email ?? ""),
    role: normalizedRole as AuthUser["role"],
    isSuperuser: Boolean(raw.isSuperuser ?? raw.is_superuser ?? nestedUser.isSuperuser ?? nestedUser.is_superuser),
    isStaff: Boolean(raw.isStaff ?? raw.is_staff ?? nestedUser.isStaff ?? nestedUser.is_staff),
    redirectTo: (raw.redirectTo ?? raw.redirect_to ?? nestedProfile.redirectTo ?? nestedProfile.redirect_to) as string | undefined,
    permissions: {
      isSuperadmin: Boolean(rawPermissions.isSuperadmin ?? rawPermissions.is_superadmin),
      canManageFeatures: Boolean(rawPermissions.canManageFeatures ?? rawPermissions.can_manage_features),
      canManageDteSettings: Boolean(rawPermissions.canManageDteSettings ?? rawPermissions.can_manage_dte_settings),
      canManageCorrelatives: Boolean(rawPermissions.canManageCorrelatives ?? rawPermissions.can_manage_correlatives),
      canManageAppearance: Boolean(rawPermissions.canManageAppearance ?? rawPermissions.can_manage_appearance),
    },
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
  const response = await request("/auth/logout/", { method: "POST", body: JSON.stringify({}) });
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
  const data = await handleJson<CategoryApiPayload[]>(response);
  // NOTE: backend ordering by `position` is the source of truth for categories.
  // Do not re-sort on the client; preserve API order exactly.
  return data
    .map(normalizeCategory)
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

export const getFeatureSettings = async (): Promise<FeatureSettings> => {
  const response = await request("/settings/features/");
  const data = await handleJson<any>(response);
  const normalized = normalizeFeatureFlags(data);
  return {
    posEnabled: normalized.posEnabled,
    openOrdersEnabled: normalized.openOrdersEnabled,
    kioskEnabled: normalized.kioskEnabled,
    customerDisplayEnabled: normalized.customerDisplayEnabled,
    kitchenDisplayEnabled: normalized.kitchenDisplayEnabled,
    menuDiscountsEnabled: normalized.menuDiscountsEnabled,
    reportsEnabled: normalized.reportsEnabled,
    clientsEnabled: normalized.clientsEnabled,
    settingsEnabled: normalized.settingsEnabled,
    cashCloseExpectedTotalsControlEnabled: normalized.cashCloseExpectedTotalsControlEnabled,
    cashCloseExpectedTotalsAllowedRoles: data.cash_close_expected_totals_allowed_roles ?? [],
    cashCloseExpectedTotalsVisibleFields: data.cash_close_expected_totals_visible_fields ?? [],
    inventoryStockPolicy: normalizeInventoryStockPolicy(data.inventory_stock_policy ?? normalized.inventoryStockPolicy),
    inventoryAdvancedEnabled: Boolean(data.inventory_advanced_enabled ?? normalized.inventoryAdvancedEnabled),
    posProductImagesEnabled: Boolean(data.pos_product_images_enabled ?? normalized.posProductImagesEnabled),
    tableMapEnabled: Boolean(data.table_map_enabled ?? normalized.tableMapEnabled),
    operationMode: normalized.operationMode,
    defaultPosEntry: normalized.defaultPosEntry,
    allowTableMerge: normalized.allowTableMerge,
    allowTableTransfer: normalized.allowTableTransfer,
    allowSplitByGuest: normalized.allowSplitByGuest,
    allowSplitByItem: normalized.allowSplitByItem,
    posQuickSalesButtonMode: normalized.posQuickSalesButtonMode,
    posQuickSalesHistoryScope: normalized.posQuickSalesHistoryScope,
    posQuickSalesHistoryWindowMinutes: normalized.posQuickSalesHistoryWindowMinutes,
  };
};

const featureSettingsFromNormalized = (normalized: FeatureFlagsNormalized, data: any = {}): FeatureSettings => ({
  posEnabled: normalized.posEnabled,
  openOrdersEnabled: normalized.openOrdersEnabled,
  kioskEnabled: normalized.kioskEnabled,
  customerDisplayEnabled: normalized.customerDisplayEnabled,
  kitchenDisplayEnabled: normalized.kitchenDisplayEnabled,
  menuDiscountsEnabled: normalized.menuDiscountsEnabled,
  reportsEnabled: normalized.reportsEnabled,
  clientsEnabled: normalized.clientsEnabled,
  settingsEnabled: normalized.settingsEnabled,
  cashCloseExpectedTotalsControlEnabled: normalized.cashCloseExpectedTotalsControlEnabled,
  cashCloseExpectedTotalsAllowedRoles: data.cash_close_expected_totals_allowed_roles ?? [],
  cashCloseExpectedTotalsVisibleFields: data.cash_close_expected_totals_visible_fields ?? [],
  inventoryStockPolicy: normalizeInventoryStockPolicy(data.inventory_stock_policy ?? normalized.inventoryStockPolicy),
  inventoryAdvancedEnabled: Boolean(data.inventory_advanced_enabled ?? normalized.inventoryAdvancedEnabled),
  posProductImagesEnabled: Boolean(data.pos_product_images_enabled ?? normalized.posProductImagesEnabled),
  tableMapEnabled: Boolean(data.table_map_enabled ?? normalized.tableMapEnabled),
  operationMode: normalized.operationMode,
  defaultPosEntry: normalized.defaultPosEntry,
  allowTableMerge: normalized.allowTableMerge,
  allowTableTransfer: normalized.allowTableTransfer,
  allowSplitByGuest: normalized.allowSplitByGuest,
  allowSplitByItem: normalized.allowSplitByItem,
  posQuickSalesButtonMode: normalized.posQuickSalesButtonMode,
  posQuickSalesHistoryScope: normalized.posQuickSalesHistoryScope,
  posQuickSalesHistoryWindowMinutes: normalized.posQuickSalesHistoryWindowMinutes,
});

export const getRuntimeFeatureSettings = async (): Promise<FeatureSettings> => {
  const response = await request("/core/feature-flags/");
  const data = await handleJson<any>(response);
  return featureSettingsFromNormalized(normalizeFeatureFlags(data));
};

export const updateFeatureSettings = async (payload: Partial<FeatureSettings>): Promise<FeatureSettings> => {
  const body = Object.fromEntries(Object.entries({
    kiosk_enabled: payload.kioskEnabled,
    pos_enabled: payload.posEnabled,
    open_orders_enabled: payload.openOrdersEnabled,
    customer_display_enabled: payload.customerDisplayEnabled,
    kitchen_display_enabled: payload.kitchenDisplayEnabled,
    menu_discounts_enabled: payload.menuDiscountsEnabled,
    reports_enabled: payload.reportsEnabled,
    clients_enabled: payload.clientsEnabled,
    settings_enabled: payload.settingsEnabled,
    cash_close_expected_totals_control_enabled: payload.cashCloseExpectedTotalsControlEnabled,
    cash_close_expected_totals_allowed_roles: payload.cashCloseExpectedTotalsAllowedRoles,
    cash_close_expected_totals_visible_fields: payload.cashCloseExpectedTotalsVisibleFields,
    inventory_stock_policy: payload.inventoryStockPolicy,
    inventory_advanced_enabled: payload.inventoryAdvancedEnabled,
    pos_product_images_enabled: payload.posProductImagesEnabled,
    table_map_enabled: payload.tableMapEnabled,
    operation_mode: payload.operationMode,
    default_pos_entry: payload.defaultPosEntry,
    allow_table_merge: payload.allowTableMerge,
    allow_table_transfer: payload.allowTableTransfer,
    allow_split_by_guest: payload.allowSplitByGuest,
    allow_split_by_item: payload.allowSplitByItem,
    pos_quick_sales_button_mode: payload.posQuickSalesButtonMode,
    pos_quick_sales_history_scope: payload.posQuickSalesHistoryScope,
    pos_quick_sales_history_window_minutes: payload.posQuickSalesHistoryWindowMinutes,
  }).filter(([, value]) => value !== undefined));
  const response = await request("/settings/features/", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  const data = await handleJson<any>(response);
  const normalized = normalizeFeatureFlags(data);
  return {
    posEnabled: normalized.posEnabled,
    openOrdersEnabled: normalized.openOrdersEnabled,
    kioskEnabled: normalized.kioskEnabled,
    customerDisplayEnabled: normalized.customerDisplayEnabled,
    kitchenDisplayEnabled: normalized.kitchenDisplayEnabled,
    menuDiscountsEnabled: normalized.menuDiscountsEnabled,
    reportsEnabled: normalized.reportsEnabled,
    clientsEnabled: normalized.clientsEnabled,
    settingsEnabled: normalized.settingsEnabled,
    cashCloseExpectedTotalsControlEnabled: normalized.cashCloseExpectedTotalsControlEnabled,
    cashCloseExpectedTotalsAllowedRoles: data.cash_close_expected_totals_allowed_roles ?? [],
    cashCloseExpectedTotalsVisibleFields: data.cash_close_expected_totals_visible_fields ?? [],
    inventoryStockPolicy: normalizeInventoryStockPolicy(data.inventory_stock_policy ?? normalized.inventoryStockPolicy),
    inventoryAdvancedEnabled: Boolean(data.inventory_advanced_enabled ?? normalized.inventoryAdvancedEnabled),
    posProductImagesEnabled: Boolean(data.pos_product_images_enabled ?? normalized.posProductImagesEnabled),
    tableMapEnabled: Boolean(data.table_map_enabled ?? normalized.tableMapEnabled),
    operationMode: normalized.operationMode,
    defaultPosEntry: normalized.defaultPosEntry,
    allowTableMerge: normalized.allowTableMerge,
    allowTableTransfer: normalized.allowTableTransfer,
    allowSplitByGuest: normalized.allowSplitByGuest,
    allowSplitByItem: normalized.allowSplitByItem,
    posQuickSalesButtonMode: normalized.posQuickSalesButtonMode,
    posQuickSalesHistoryScope: normalized.posQuickSalesHistoryScope,
    posQuickSalesHistoryWindowMinutes: normalized.posQuickSalesHistoryWindowMinutes,
  };
};

export const getFeatureSettingsOptions = async (): Promise<FeatureSettingsOptions> => {
  const response = await request("/settings/features/options/");
  const data = await handleJson<any>(response);
  return {
    roles: data.roles ?? [],
    cashCloseExpectedTotalFields: data.cash_close_expected_total_fields ?? [],
  };
};

const normalizeTimeValue = (value: unknown, fallback: string) => String(value ?? fallback).slice(0, 5);

const mapBusinessHoursSettings = (data: Record<string, unknown>): BusinessHoursSettings => ({
  businessHoursEnabled: Boolean(data.business_hours_enabled),
  openingTime: normalizeTimeValue(data.opening_time, "08:00"),
  closingTime: normalizeTimeValue(data.closing_time, "22:00"),
  graceHoursAfterClose: Number(data.grace_hours_after_close ?? 4),
  timezone: String(data.timezone ?? "America/El_Salvador"),
  autoCloseCashEnabled: Boolean(data.auto_close_cash_enabled),
  autoCloseCountZero: Boolean(data.auto_close_count_zero ?? true),
  updatedAt: data.updated_at ?? null,
});

export const getBusinessHoursSettings = async (): Promise<BusinessHoursSettings> => {
  const response = await request("/settings/business-hours/");
  return mapBusinessHoursSettings(await handleJson<Record<string, unknown>>(response));
};

export const updateBusinessHoursSettings = async (payload: Partial<BusinessHoursSettings>): Promise<BusinessHoursSettings> => {
  const body = Object.fromEntries(Object.entries({
    business_hours_enabled: payload.businessHoursEnabled,
    opening_time: payload.openingTime,
    closing_time: payload.closingTime,
    grace_hours_after_close: payload.graceHoursAfterClose,
    timezone: payload.timezone,
    auto_close_cash_enabled: payload.autoCloseCashEnabled,
    auto_close_count_zero: payload.autoCloseCountZero,
  }).filter(([, value]) => value !== undefined));
  const response = await request("/settings/business-hours/", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return mapBusinessHoursSettings(await handleJson<Record<string, unknown>>(response));
};

const mapAppearanceSettings = (data: any): AppearanceSettings => ({
  primaryColor: String(data.primary_color ?? "#1F7A4D"),
  colorPrimary: String(data.color_primary ?? data.primary_color ?? "#1F7A4D"),
  colorPrimaryHover: String(data.color_primary_hover ?? "#17623E"),
  colorPrimarySoft: String(data.color_primary_soft ?? "#DDF3E8"),
  colorPrimaryBorder: String(data.color_primary_border ?? "#7EC8A3"),
  colorPrimaryText: String(data.color_primary_text ?? "#0D3B26"),
  colorPrimaryContrast: String(data.color_primary_contrast ?? "#FFFFFF"),
  cssVariables: data.css_variables ?? {},
  palette: Array.isArray(data.palette) ? data.palette : [],
});

export const getAppearanceSettings = async (): Promise<AppearanceSettings> => {
  const response = await request("/settings/appearance/");
  return mapAppearanceSettings(await handleJson<any>(response));
};

export const getPublicAppearanceSettings = async (): Promise<AppearanceSettings> => {
  const response = await request("/public/appearance/", { public: true });
  return mapAppearanceSettings(await handleJson<any>(response));
};

const mapPublicPwaMetadata = (data: any): PublicPwaMetadata => ({
  appName: String(data.app_name ?? "GastroPOSV"),
  shortName: String(data.short_name ?? data.app_name ?? "GastroPOSV"),
  description: String(data.description ?? "Sistema POS para restaurante"),
  siteName: String(data.site_name ?? "GastroPOSV"),
  themeColor: String(data.theme_color ?? "#1F7A4D"),
  backgroundColor: String(data.background_color ?? "#0B1020"),
  display: (data.display ?? "standalone") as PublicPwaMetadata["display"],
  orientation: String(data.orientation ?? "any"),
  startUrl: String(data.start_url ?? "/"),
  scope: String(data.scope ?? "/"),
  version: String(data.version ?? "default"),
  brandingVersion: String(data.branding_version ?? data.version ?? "default"),
  logoVersion: String(data.logo_version ?? data.branding_version ?? data.version ?? ""),
  hasCustomerLogo: Boolean(data.has_customer_logo),
  customerLogoUrl: data.customer_logo_url ? String(data.customer_logo_url) : null,
  ticketLogoUrl: data.ticket_logo_url ? String(data.ticket_logo_url) : null,
  manifestUrl: String(data.manifest_url ?? "/api/public/manifest.webmanifest"),
  icon192Url: String(data.icon_192_url ?? "/api/public/pwa/icon-192.png"),
  icon512Url: String(data.icon_512_url ?? "/api/public/pwa/icon-512.png"),
  maskableIconUrl: String(data.maskable_icon_url ?? "/api/public/pwa/icon-maskable-512.png"),
  appleTouchIconUrl: String(data.apple_touch_icon_url ?? "/api/public/pwa/apple-touch-icon.png"),
  faviconUrl: String(data.favicon_url ?? "/api/public/pwa/favicon.ico"),
  shareImageUrl: String(data.share_image_url ?? "/api/public/pwa/share-image.png"),
});

export const getPublicPwaMetadata = async (): Promise<PublicPwaMetadata> => {
  const response = await request("/public/pwa/metadata/", { public: true });
  return mapPublicPwaMetadata(await handleJson<any>(response));
};

export const updateAppearanceSettings = async (payload: { primaryColor?: string; restoreDefault?: boolean }): Promise<AppearanceSettings> => {
  const response = await request("/settings/appearance/", {
    method: "PATCH",
    body: JSON.stringify({ primary_color: payload.primaryColor, restore_default: payload.restoreDefault }),
  });
  return mapAppearanceSettings(await handleJson<any>(response));
};

const mapDteSettings = (data: any): DteSettings => ({
  haciendaEnabled: Boolean(data.enabled ?? data.hacienda_enabled),
  ambiente: (data.environment === "production" || data.ambiente === "01" ? "01" : "00") as "00" | "01",
  baseUrl: String(data.base_url ?? ""),
  apiTokenMasked: String(data.api_token_masked ?? ""),
  timeoutSeconds: Number(data.timeout_seconds ?? 15),
  retryCount: Number(data.retry_count ?? 3),
  fiscalEmailEnabled: Boolean(data.fiscal_email_enabled ?? data.api?.fiscal_email_enabled),
  fiscalWhatsappEnabled: Boolean(data.fiscal_whatsapp_enabled ?? data.api?.fiscal_whatsapp_enabled),
  fiscalPdfEnabled: Boolean(data.fiscal_pdf_enabled ?? data.api?.fiscal_pdf_enabled),
  fiscalJsonEnabled: Boolean(data.fiscal_json_enabled ?? data.api?.fiscal_json_enabled),
  status: String(data.config_status ?? data.status ?? "disabled"),
  lastConnectionTestAt: data.last_connection_test_at ?? null,
  lastErrorSanitized: String(data.last_error_sanitized ?? ""),
  canManageTechnical: Boolean(data.can_manage_technical ?? data.permissions?.can_edit_technical),
  permissions: {
    canViewBasic: Boolean(data.permissions?.can_view_basic),
    canEditTechnical: Boolean(data.permissions?.can_edit_technical ?? data.can_manage_technical),
    canEditCorrelatives: Boolean(data.permissions?.can_edit_correlatives),
    isSuperadmin: Boolean(data.permissions?.is_superadmin),
  },
  issuer: {
    legalName: String(data.issuer?.legal_name ?? ""),
    commercialName: String(data.issuer?.commercial_name ?? ""),
    documentType: String(data.issuer?.document_type ?? "NIT"),
    nit: String(data.issuer?.nit ?? ""),
    dui: String(data.issuer?.dui ?? ""),
    nrc: String(data.issuer?.nrc ?? ""),
    activityCode: String(data.issuer?.activity_code ?? ""),
    activityDescription: String(data.issuer?.activity_description ?? ""),
    establishmentType: String(data.issuer?.establishment_type ?? ""),
    department: String(data.issuer?.department ?? ""),
    municipality: String(data.issuer?.municipality ?? ""),
    address: String(data.issuer?.address ?? ""),
    phone: String(data.issuer?.phone ?? ""),
    email: String(data.issuer?.email ?? ""),
  },
  branch: {
    id: data.branch?.id ?? null,
    name: String(data.branch?.name ?? data.single_branch?.branch_name ?? ""),
    code: String(data.branch?.code ?? ""),
    address: String(data.branch?.address ?? ""),
    establishmentCodeMh: String(data.branch?.establishment_code_mh ?? data.single_branch?.establishment_code ?? ""),
    establishmentCode: String(data.branch?.establishment_code ?? ""),
    posCodeMh: String(data.branch?.pos_code_mh ?? data.single_branch?.pos_code ?? ""),
    posCode: String(data.branch?.pos_code ?? ""),
    establishmentType: String(data.branch?.establishment_type ?? data.single_branch?.establishment_type ?? ""),
    branchAddress: String(data.branch?.branch_address ?? data.single_branch?.address ?? ""),
    phone: String(data.branch?.phone ?? ""),
    email: String(data.branch?.email ?? ""),
    active: Boolean(data.branch?.active ?? true),
  },
  correlatives: (Array.isArray(data.correlatives) ? data.correlatives : []).map((row: any) => ({
    id: Number(row.id),
    tipoDte: String(row.tipo_dte ?? ""),
    label: String(row.label ?? row.tipo_dte ?? ""),
    ambiente: (row.ambiente === "01" ? "01" : "00") as "00" | "01",
    environment: String(row.environment ?? ""),
    branchName: String(row.branch_name ?? ""),
    year: Number(row.year ?? new Date().getFullYear()),
    establishmentCode: String(row.establishment_code ?? ""),
    posCode: String(row.pos_code ?? ""),
    lastNumber: Number(row.last_number ?? 0),
    nextNumber: Number(row.next_number ?? 1),
    active: Boolean(row.active ?? true),
    updatedAt: row.updated_at ?? null,
  })),
  pendingFields: Array.isArray(data.pending_fields) ? data.pending_fields.map(String) : [],
  apiTokenConfigured: Boolean(data.api?.api_token_configured ?? data.api_token_masked),
  message: data.message ? String(data.message) : undefined,
});

export const getDteSettings = async (): Promise<DteSettings> => {
  const response = await request("/settings/dte/");
  return mapDteSettings(await handleJson<any>(response));
};

export const updateDteSettings = async (payload: Partial<DteSettings> & { apiToken?: string }): Promise<DteSettings> => {
  const response = await request("/settings/dte/", {
    method: "PATCH",
    body: JSON.stringify({
      hacienda_enabled: payload.haciendaEnabled,
      enabled: payload.haciendaEnabled,
      ambiente: payload.ambiente,
      environment: payload.ambiente === "01" ? "production" : payload.ambiente === "00" ? "test" : undefined,
      base_url: payload.baseUrl,
      api_token: payload.apiToken,
      timeout_seconds: payload.timeoutSeconds,
      retry_count: payload.retryCount,
      fiscal_email_enabled: payload.fiscalEmailEnabled,
      fiscal_whatsapp_enabled: payload.fiscalWhatsappEnabled,
      fiscal_pdf_enabled: payload.fiscalPdfEnabled,
      fiscal_json_enabled: payload.fiscalJsonEnabled,
      issuer: payload.issuer ? {
        legal_name: payload.issuer.legalName,
        commercial_name: payload.issuer.commercialName,
        document_type: payload.issuer.documentType,
        nit: payload.issuer.nit,
        dui: payload.issuer.dui,
        nrc: payload.issuer.nrc,
        activity_code: payload.issuer.activityCode,
        activity_description: payload.issuer.activityDescription,
        establishment_type: payload.issuer.establishmentType,
        department: payload.issuer.department,
        municipality: payload.issuer.municipality,
        address: payload.issuer.address,
        phone: payload.issuer.phone,
        email: payload.issuer.email,
      } : undefined,
      branch: payload.branch ? {
        name: payload.branch.name,
        code: payload.branch.code,
        address: payload.branch.address,
        establishment_code_mh: payload.branch.establishmentCodeMh,
        establishment_code: payload.branch.establishmentCode,
        pos_code_mh: payload.branch.posCodeMh,
        pos_code: payload.branch.posCode,
        establishment_type: payload.branch.establishmentType,
        branch_address: payload.branch.branchAddress,
        phone: payload.branch.phone,
        email: payload.branch.email,
      } : undefined,
    }),
  });
  return mapDteSettings(await handleJson<any>(response));
};

export const initializeDteCorrelatives = async (): Promise<DteCorrelative[]> => {
  const response = await request("/settings/dte/correlatives/initialize/", { method: "POST", body: JSON.stringify({ ambientes: ["00", "01"] }) });
  const data = await handleJson<any>(response);
  return mapDteSettings({ correlatives: data.correlatives ?? [] } as any).correlatives;
};

export const updateDteCorrelative = async (id: number, payload: { lastNumber: number; reason: string; confirmDecrease?: boolean }): Promise<DteCorrelative[]> => {
  const response = await request(`/settings/dte/correlatives/${id}/`, {
    method: "PATCH",
    body: JSON.stringify({ last_number: payload.lastNumber, reason: payload.reason, confirm_decrease: payload.confirmDecrease }),
  });
  const data = await handleJson<any>(response);
  return mapDteSettings({ correlatives: data.correlatives ?? [] } as any).correlatives;
};

export const testDteConnectionSettings = async (): Promise<{ ok: boolean; status: string; message: string; missing?: string[] }> => {
  const response = await request("/settings/dte/test-connection/", { method: "POST", body: JSON.stringify({}) });
  return handleJson(response);
};

const mapTicketSettings = (data: any): TicketSettings => ({
  ticketLogoUrl: data.ticket_logo_url ?? null,
  ticketLogoVersion: String(data.ticket_logo_version ?? data.logo_version ?? ""),
  ticketLogoName: data.ticket_logo_name ?? null,
  hasTicketLogo: Boolean(data.has_ticket_logo ?? data.ticket_logo_url),
});

export const getTicketSettings = async (): Promise<TicketSettings> => {
  const response = await request("/settings/ticket/");
  return mapTicketSettings(await handleJson<any>(response));
};

export const uploadTicketLogo = async (file: File): Promise<TicketSettings> => {
  const formData = new FormData();
  formData.append("logo", file);
  const response = await request("/settings/ticket/logo/", { method: "POST", body: formData });
  return mapTicketSettings(await handleJson<any>(response));
};

export const deleteTicketLogo = async (): Promise<TicketSettings> => {
  const response = await request("/settings/ticket/logo/", { method: "DELETE" });
  return mapTicketSettings(await handleJson<any>(response));
};

export const getTransactionTicket = async (paymentId: number): Promise<TransactionTicketPayload> => {
  const response = await request(`/reports/transactions/${paymentId}/ticket/`);
  const data = await handleJson<any>(response);
  return {
    paymentId: Number(data.payment_id),
    orderId: Number(data.order_id),
    ticketText: String(data.ticket_text ?? ""),
    ticketHtml: String(data.ticket_html ?? ""),
  };
};

export const createCategory = async (payload: string | { name: string; image?: File | null; inventoryStockPolicy?: ProductInventoryStockPolicy; posProductImagesPolicy?: PosImagePolicy }): Promise<Category> => {
  const normalizedPayload = typeof payload === "string" ? { name: payload, image: null, inventoryStockPolicy: "inherit" as ProductInventoryStockPolicy } : payload;
  const formData = new FormData();
  formData.append("name", normalizedPayload.name);
  if (normalizedPayload.image) {
    formData.append("image", normalizedPayload.image);
  }
  formData.append("inventory_stock_policy", normalizedPayload.inventoryStockPolicy ?? "inherit");
  formData.append("pos_product_images_policy", normalizedPayload.posProductImagesPolicy ?? "inherit");

  const response = await request("/menu/categories/", {
    method: "POST",
    body: formData,
  });
  const data = await handleJson<CategoryApiPayload>(response);
  return normalizeCategory(data);
};

export const updateCategory = async (
  categoryId: number,
  payload: string | { name?: string; image?: File | null; removeImage?: boolean; inventoryStockPolicy?: ProductInventoryStockPolicy; posProductImagesPolicy?: PosImagePolicy }
): Promise<Category> => {
  const normalizedPayload = typeof payload === "string" ? { name: payload, image: null, removeImage: false, inventoryStockPolicy: undefined } : payload;
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
  if (normalizedPayload.inventoryStockPolicy !== undefined) {
    formData.append("inventory_stock_policy", normalizedPayload.inventoryStockPolicy);
  }
  if (normalizedPayload.posProductImagesPolicy !== undefined) {
    formData.append("pos_product_images_policy", normalizedPayload.posProductImagesPolicy);
  }

  const response = await request(`/menu/categories/${categoryId}/`, {
    method: "PATCH",
    body: formData,
  });
  const data = await handleJson<CategoryApiPayload>(response);
  return normalizeCategory(data);
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
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
    inventory_links?: Array<{ id: number; inventory_item: number; inventory_item_name: string; inventory_item_unit: string; quantity_required: string }>;
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
      requiresKitchen: item.requires_kitchen !== false,
      inventoryStockPolicy: normalizeProductInventoryStockPolicy(item.inventory_stock_policy),
      posImagePolicy: normalizePosImagePolicy(item.pos_image_policy),
    ...mapProductInventoryFields(item),
      modifierGroups: item.modifier_groups,
      modifierGroupsPos: item.modifier_groups_pos ?? [],
      modifierGroupLinks: (item.modifier_group_links ?? []).map((link) => ({
        groupId: link.group_id,
        showInPos: Boolean(link.show_in_pos),
      })),
      inventoryLinks: (item.inventory_links ?? []).map((link) => ({
        id: link.id,
        inventoryItemId: link.inventory_item,
        inventoryItemName: link.inventory_item_name,
        inventoryItemUnit: link.inventory_item_unit,
        quantityRequired: Number(link.quantity_required),
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
  inventoryLinks?: Array<{ inventoryItemId: number; quantityRequired: number }>;
  inventoryStockPolicy?: ProductInventoryStockPolicy;
  posImagePolicy?: PosImagePolicy;
  inventoryComponentsEnabled?: boolean;
  trackInventory?: boolean;
  trackedInventoryItem?: number | null;
  trackedInventoryQuantity?: number;
  newInventoryItem?: ProductInventoryTrackingCreatePayload | null;
}): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
  formData.append("requires_kitchen", payload.requiresKitchen ? "true" : "false");
  formData.append("inventory_stock_policy", payload.inventoryStockPolicy ?? "inherit");
  formData.append("pos_image_policy", payload.posImagePolicy ?? "inherit");
  appendProductInventoryTrackingFormData(formData, payload);
  formData.append("disposable_fee", String(payload.disposableFee ?? 0));
  formData.append("disposable_apply_to", JSON.stringify(payload.disposableApplyTo ?? []));
  if (payload.image) {
    formData.append("image", payload.image);
  }
  if (payload.modifierGroupIds?.length) {
    payload.modifierGroupIds.forEach((id) => formData.append("modifier_group_ids", id.toString()));
  }
  if (payload.inventoryLinks) {
    formData.append("inventory_links", JSON.stringify(payload.inventoryLinks.map((row) => ({
      inventory_item: row.inventoryItemId,
      quantity_required: row.quantityRequired,
    }))));
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
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
    inventory_links?: Array<{ id: number; inventory_item: number; inventory_item_name: string; inventory_item_unit: string; quantity_required: string }>;
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
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    posImagePolicy: normalizePosImagePolicy(data.pos_image_policy),
    ...mapProductInventoryFields(data),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
    inventoryLinks: (data.inventory_links ?? []).map((link) => ({
      id: link.id,
      inventoryItemId: link.inventory_item,
      inventoryItemName: link.inventory_item_name,
      inventoryItemUnit: link.inventory_item_unit,
      quantityRequired: Number(link.quantity_required),
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
    inventoryLinks?: Array<{ inventoryItemId: number; quantityRequired: number }>;
    inventoryStockPolicy?: ProductInventoryStockPolicy;
    posImagePolicy?: PosImagePolicy;
    inventoryComponentsEnabled?: boolean;
    trackInventory?: boolean;
    trackedInventoryItem?: number | null;
    trackedInventoryQuantity?: number;
    newInventoryItem?: ProductInventoryTrackingCreatePayload | null;
  }
): Promise<Product> => {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description);
  formData.append("price", payload.price.toString());
  formData.append("category_id", payload.categoryId.toString());
  formData.append("available", payload.available ? "true" : "false");
  formData.append("requires_kitchen", payload.requiresKitchen ? "true" : "false");
  formData.append("inventory_stock_policy", payload.inventoryStockPolicy ?? "inherit");
  formData.append("pos_image_policy", payload.posImagePolicy ?? "inherit");
  appendProductInventoryTrackingFormData(formData, payload);
  formData.append("disposable_fee", String(payload.disposableFee ?? 0));
  formData.append("disposable_apply_to", JSON.stringify(payload.disposableApplyTo ?? []));
  if (payload.image) {
    formData.append("image", payload.image);
  }
  if (payload.modifierGroupIds?.length) {
    payload.modifierGroupIds.forEach((id) => formData.append("modifier_group_ids", id.toString()));
  }
  if (payload.inventoryLinks) {
    formData.append("inventory_links", JSON.stringify(payload.inventoryLinks.map((row) => ({
      inventory_item: row.inventoryItemId,
      quantity_required: row.quantityRequired,
    }))));
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
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
    inventory_links?: Array<{ id: number; inventory_item: number; inventory_item_name: string; inventory_item_unit: string; quantity_required: string }>;
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
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    posImagePolicy: normalizePosImagePolicy(data.pos_image_policy),
    ...mapProductInventoryFields(data),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
    inventoryLinks: (data.inventory_links ?? []).map((link) => ({
      id: link.id,
      inventoryItemId: link.inventory_item,
      inventoryItemName: link.inventory_item_name,
      inventoryItemUnit: link.inventory_item_unit,
      quantityRequired: Number(link.quantity_required),
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


const mapInventorySupplier = (row: any): InventorySupplier => ({
  id: Number(row.id),
  name: row.name ?? "",
  code: row.code ?? "",
  contactName: row.contact_name ?? "",
  phone: row.phone ?? "",
  email: row.email ?? "",
  address: row.address ?? "",
  taxId: row.tax_id ?? "",
  notes: row.notes ?? "",
  isActive: Boolean(row.is_active),
});

const mapInventoryItem = (row: any): InventoryItem => ({
  id: row.id,
  name: row.name,
  sku: row.sku ?? "",
  unit: row.unit,
  currentStock: Number(row.current_stock ?? 0),
  minStock: row.min_stock != null ? Number(row.min_stock) : null,
  maxStock: row.max_stock != null ? Number(row.max_stock) : null,
  supplier: row.supplier ?? null,
  supplierName: row.supplier_name ?? null,
  unitCost: row.unit_cost != null ? Number(row.unit_cost) : null,
  supplierCode: row.supplier_code ?? "",
  purchaseUnit: row.purchase_unit ?? "",
  purchaseToInventoryFactor: Number(row.purchase_to_inventory_factor ?? 1),
  notes: row.notes ?? "",
  isActive: Boolean(row.is_active),
});

const mapPurchaseOrderLine = (row: any): PurchaseOrderLine => ({
  id: row.id,
  inventoryItem: row.inventory_item,
  inventoryItemName: row.inventory_item_name ?? "",
  inventoryItemSku: row.inventory_item_sku ?? "",
  inventoryItemUnit: row.inventory_item_unit ?? "",
  description: row.description ?? "",
  quantityOrdered: Number(row.quantity_ordered ?? 0),
  quantityReceived: Number(row.quantity_received ?? 0),
  pendingQuantity: Number(row.pending_quantity ?? 0),
  purchaseUnit: row.purchase_unit ?? "",
  purchaseToInventoryFactor: Number(row.purchase_to_inventory_factor ?? 1),
  inventoryQuantityOrdered: Number(row.inventory_quantity_ordered ?? 0),
  unitCost: Number(row.unit_cost ?? 0),
  subtotal: Number(row.subtotal ?? 0),
  notes: row.notes ?? "",
});

const mapPurchaseOrder = (row: any): PurchaseOrder => ({
  id: Number(row.id),
  code: row.code ?? "",
  supplier: Number(row.supplier),
  supplierName: row.supplier_name ?? "",
  status: row.status ?? "draft",
  statusLabel: row.status_label ?? row.status ?? "Borrador",
  paymentCategory: row.payment_category ?? "cash",
  expectedDate: row.expected_date ?? null,
  notes: row.notes ?? "",
  proofReference: row.proof_reference ?? "",
  proofUrl: row.proof_url ?? "",
  subtotal: Number(row.subtotal ?? 0),
  total: Number(row.total ?? 0),
  createdByUsername: row.created_by_username ?? "",
  createdAt: row.created_at,
  approvedAt: row.approved_at ?? null,
  cancelReason: row.cancel_reason ?? "",
  receivedPercent: Number(row.received_percent ?? 0),
  lines: (row.lines ?? []).map(mapPurchaseOrderLine),
});

export const getInventoryItems = async (q?: string): Promise<InventoryItem[]> => {
  const params = new URLSearchParams();
  if (q?.trim()) params.set("q", q.trim());
  const response = await request(`/inventory/items/${params.toString() ? `?${params.toString()}` : ""}`);
  const data = await handleJson<Array<any>>(response);
  return data.map(mapInventoryItem);
};

export const createInventoryItem = async (payload: {
  name: string; sku?: string; unit: string; initialStock?: number; minStock?: number | null; maxStock?: number | null; supplier?: number | null; unitCost?: number | null; supplierCode?: string; purchaseUnit?: string; purchaseToInventoryFactor?: number; notes?: string; isActive: boolean;
}): Promise<InventoryItem> => {
  const response = await request("/inventory/items/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      sku: payload.sku ?? "",
      unit: payload.unit,
      initial_stock: payload.initialStock ?? 0,
      min_stock: payload.minStock,
      max_stock: payload.maxStock,
      supplier: payload.supplier,
      unit_cost: payload.unitCost,
      supplier_code: payload.supplierCode ?? "",
      purchase_unit: payload.purchaseUnit ?? "",
      purchase_to_inventory_factor: payload.purchaseToInventoryFactor ?? 1,
      notes: payload.notes ?? "",
      is_active: payload.isActive,
    }),
  });
  const row = await handleJson<any>(response);
  return mapInventoryItem(row);
};

export const updateInventoryItem = async (id: number, payload: {
  name: string; sku?: string; unit: string; minStock?: number | null; maxStock?: number | null; supplier?: number | null; unitCost?: number | null; supplierCode?: string; purchaseUnit?: string; purchaseToInventoryFactor?: number; notes?: string; isActive: boolean;
}): Promise<InventoryItem> => {
  const response = await request(`/inventory/items/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      sku: payload.sku ?? "",
      unit: payload.unit,
      min_stock: payload.minStock,
      max_stock: payload.maxStock,
      supplier: payload.supplier,
      unit_cost: payload.unitCost,
      supplier_code: payload.supplierCode ?? "",
      purchase_unit: payload.purchaseUnit ?? "",
      purchase_to_inventory_factor: payload.purchaseToInventoryFactor ?? 1,
      notes: payload.notes ?? "",
      is_active: payload.isActive,
    }),
  });
  const row = await handleJson<any>(response);
  return mapInventoryItem(row);
};

export const addInventoryStock = async (id: number, quantity: number, reason?: string): Promise<InventoryItem> => {
  const response = await request(`/inventory/items/${id}/add-stock/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity, reason: reason ?? "" }),
  });
  const row = await handleJson<any>(response);
  return mapInventoryItem(row);
};

export const adjustInventoryStock = async (id: number, payload: { setStock?: number; delta?: number; reason?: string }): Promise<InventoryItem> => {
  const response = await request(`/inventory/items/${id}/adjust-stock/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ set_stock: payload.setStock, delta: payload.delta, reason: payload.reason ?? "" }),
  });
  const row = await handleJson<any>(response);
  return mapInventoryItem(row);
};

export const createInventoryAdjustment = async (payload: {
  inventoryItem: number;
  adjustmentType: "entry" | "loss" | "damaged" | "correction";
  quantity?: number;
  setStock?: number;
  reason?: string;
}): Promise<{ message: string; item: InventoryItem; movement: InventoryMovement; stockBefore: number; stockAfter: number; adjustmentType: string }> => {
  const response = await request("/inventory/adjustments/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inventory_item: payload.inventoryItem,
      adjustment_type: payload.adjustmentType,
      quantity: payload.quantity,
      set_stock: payload.setStock,
      reason: payload.reason ?? "",
    }),
  });
  const row = await handleJson<any>(response);
  const itemRow = row.item;
  const movementRow = row.movement;
  return {
    message: row.message ?? "Ajuste registrado correctamente.",
    item: { id: itemRow.id, name: itemRow.name, sku: itemRow.sku ?? "", unit: itemRow.unit, currentStock: Number(itemRow.current_stock ?? 0), minStock: itemRow.min_stock != null ? Number(itemRow.min_stock) : null, maxStock: itemRow.max_stock != null ? Number(itemRow.max_stock) : null, notes: itemRow.notes ?? "", isActive: Boolean(itemRow.is_active) },
    movement: { id: movementRow.id, inventoryItem: movementRow.inventory_item, inventoryItemName: movementRow.inventory_item_name, movementType: movementRow.movement_type, quantityChange: Number(movementRow.quantity_change), quantityBefore: Number(movementRow.quantity_before), quantityAfter: Number(movementRow.quantity_after), reason: movementRow.reason ?? "", referenceType: movementRow.reference_type ?? "", referenceId: movementRow.reference_id ?? "", createdByUsername: movementRow.created_by_username ?? "", createdAt: movementRow.created_at },
    stockBefore: Number(row.stock_before),
    stockAfter: Number(row.stock_after),
    adjustmentType: row.adjustment_type,
  };
};

export const getInventoryMovements = async (inventoryItemId?: number, filters?: { movementType?: string; dateFrom?: string; dateTo?: string; user?: number }): Promise<InventoryMovement[]> => {
  const params = new URLSearchParams();
  if (inventoryItemId) params.set("inventory_item", String(inventoryItemId));
  if (filters?.movementType) params.set("movement_type", filters.movementType);
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.user) params.set("user", String(filters.user));
  const response = await request(`/inventory/movements/${params.toString() ? `?${params.toString()}` : ""}`);
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    id: row.id,
    inventoryItem: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemSku: row.inventory_item_sku ?? "",
    inventoryItemUnit: row.inventory_item_unit ?? "",
    movementType: row.movement_type,
    quantityChange: Number(row.quantity_change),
    quantityBefore: Number(row.quantity_before),
    quantityAfter: Number(row.quantity_after),
    reason: row.reason ?? "",
    referenceType: row.reference_type ?? "",
    referenceId: row.reference_id ?? "",
    createdByUsername: row.created_by_username ?? "",
    createdAt: row.created_at,
  }));
};


const mapInventoryCountLine = (row: any): InventoryCountLine => ({
  id: row.id,
  session: row.session,
  inventoryItem: row.inventory_item,
  inventoryItemName: row.inventory_item_name,
  inventoryItemSku: row.inventory_item_sku ?? "",
  inventoryItemUnit: row.inventory_item_unit ?? "",
  systemStock: Number(row.system_stock ?? 0),
  countedStock: row.counted_stock == null ? null : Number(row.counted_stock),
  difference: Number(row.difference ?? 0),
  note: row.note ?? "",
  stockBeforeApply: row.stock_before_apply == null ? null : Number(row.stock_before_apply),
  stockAfterApply: row.stock_after_apply == null ? null : Number(row.stock_after_apply),
  movement: row.movement ?? null,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

const mapInventoryCountSession = (row: any): InventoryCountSession => ({
  id: row.id,
  code: row.code || `CI-${row.id}`,
  countType: row.count_type,
  countTypeDisplay: row.count_type_display ?? row.count_type,
  status: row.status,
  statusDisplay: row.status_display ?? row.status,
  notes: row.notes ?? "",
  createdByUsername: row.created_by_username ?? "",
  createdAt: row.created_at,
  updatedAt: row.updated_at,
  finalizedAt: row.finalized_at ?? null,
  appliedAt: row.applied_at ?? null,
  cancelledAt: row.cancelled_at ?? null,
  cancelReason: row.cancel_reason ?? "",
  totalItems: Number(row.total_items ?? 0),
  countedItems: Number(row.counted_items ?? 0),
  totalDifferences: Number(row.total_differences ?? 0),
  totalPositiveDifferences: Number(row.total_positive_differences ?? 0),
  totalNegativeDifferences: Number(row.total_negative_differences ?? 0),
  lines: Array.isArray(row.lines) ? row.lines.map(mapInventoryCountLine) : undefined,
});

const normalizeInventoryCountId = (id: number | string): string => String(id).replace(/^:+/, "");

export const getInventoryCounts = async (filters?: { status?: string; countType?: string; dateFrom?: string; dateTo?: string; user?: number; inventoryItem?: number; q?: string }): Promise<InventoryCountSession[]> => {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.countType) params.set("count_type", filters.countType);
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.user) params.set("user", String(filters.user));
  if (filters?.inventoryItem) params.set("inventory_item", String(filters.inventoryItem));
  if (filters?.q) params.set("q", filters.q);
  const response = await request(`/inventory/counts/${params.toString() ? `?${params.toString()}` : ""}`);
  return (await handleJson<any[]>(response)).map(mapInventoryCountSession);
};

export const createInventoryCount = async (payload: { countType: "complete" | "manual" | "category"; notes?: string; itemIds?: number[] }): Promise<InventoryCountSession> => {
  const response = await request("/inventory/counts/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ count_type: payload.countType, notes: payload.notes ?? "", item_ids: payload.itemIds ?? [] }) });
  return mapInventoryCountSession(await handleJson<any>(response));
};

export const getInventoryCount = async (id: number | string): Promise<InventoryCountSession> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/`);
  return mapInventoryCountSession(await handleJson<any>(response));
};

export const updateInventoryCountLines = async (id: number | string, lines: Array<{ id: number; countedStock?: number | null; note?: string }>): Promise<InventoryCountSession> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/lines/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lines: lines.map((line) => ({ id: line.id, counted_stock: line.countedStock, note: line.note ?? "" })) }) });
  return mapInventoryCountSession(await handleJson<any>(response));
};

export const finalizeInventoryCount = async (id: number | string): Promise<InventoryCountSession> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/finalize/`, { method: "POST" });
  return mapInventoryCountSession(await handleJson<any>(response));
};

export const applyInventoryCount = async (id: number | string): Promise<{ message: string; movementsCreated: number; session: InventoryCountSession }> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/apply/`, { method: "POST" });
  const data = await handleJson<any>(response);
  return { message: data.message, movementsCreated: Number(data.movements_created ?? 0), session: mapInventoryCountSession(data.session) };
};

export const cancelInventoryCount = async (id: number | string, cancelReason?: string): Promise<InventoryCountSession> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/cancel/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cancel_reason: cancelReason ?? "" }) });
  return mapInventoryCountSession(await handleJson<any>(response));
};

export const deleteInventoryCount = async (id: number | string): Promise<void> => {
  const countId = normalizeInventoryCountId(id);
  const response = await request(`/inventory/counts/${countId}/`, { method: "DELETE" });
  if (response.status === 204) return;
  await handleJson(response);
};

export const getInventoryReportAdjustments = async (filters?: { dateFrom?: string; dateTo?: string; inventoryItem?: number; user?: number; movementType?: string }): Promise<InventoryMovement[]> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.inventoryItem) params.set("inventory_item", String(filters.inventoryItem));
  if (filters?.user) params.set("user", String(filters.user));
  if (filters?.movementType) params.set("movement_type", filters.movementType);
  const response = await request(`/inventory/reports/adjustments/${params.toString() ? `?${params.toString()}` : ""}`);
  const data = await handleJson<any[]>(response);
  return data.map((row) => ({ id: row.id, inventoryItem: row.inventory_item, inventoryItemName: row.inventory_item_name, inventoryItemSku: row.inventory_item_sku ?? "", inventoryItemUnit: row.inventory_item_unit ?? "", movementType: row.movement_type, quantityChange: Number(row.quantity_change), quantityBefore: Number(row.quantity_before), quantityAfter: Number(row.quantity_after), reason: row.reason ?? "", referenceType: row.reference_type ?? "", referenceId: row.reference_id ?? "", createdByUsername: row.created_by_username ?? "", createdAt: row.created_at }));
};

export const getInventoryReportCounts = async (filters?: { dateFrom?: string; dateTo?: string; status?: string; countType?: string; user?: number; inventoryItem?: number }): Promise<InventoryCountSession[]> => {
  const params = new URLSearchParams();
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.countType) params.set("count_type", filters.countType);
  if (filters?.user) params.set("user", String(filters.user));
  if (filters?.inventoryItem) params.set("inventory_item", String(filters.inventoryItem));
  const response = await request(`/inventory/reports/counts/${params.toString() ? `?${params.toString()}` : ""}`);
  return (await handleJson<any[]>(response)).map(mapInventoryCountSession);
};

export const downloadInventoryPdf = async (url: string, filename: string): Promise<void> => {
  const response = await request(url);
  if (!response.ok) throw new Error("No se pudo descargar el PDF");
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
};

export const getCatalogInventoryLinks = async (productId: number): Promise<InventoryProductLink[]> => {
  const response = await request(`/inventory/catalog-links/${productId}/`);
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    id: row.id,
    inventoryItemId: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemUnit: row.inventory_item_unit,
    quantityRequired: Number(row.quantity_required),
  }));
};

export const getCategoryInventoryLinks = async (categoryId: number): Promise<InventoryProductLink[]> => {
  const response = await request(`/inventory/category-links/${categoryId}/`);
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    id: row.id,
    inventoryItemId: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemUnit: row.inventory_item_unit,
    quantityRequired: Number(row.quantity_required),
    origin: "direct",
  }));
};

export const saveCategoryInventoryLinks = async (categoryId: number, links: Array<{ inventoryItemId: number; quantityRequired: number }>): Promise<InventoryProductLink[]> => {
  const response = await request(`/inventory/category-links/${categoryId}/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      links: links.map((row) => ({ inventory_item: row.inventoryItemId, quantity_required: row.quantityRequired })),
    }),
  });
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    id: row.id,
    inventoryItemId: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemUnit: row.inventory_item_unit,
    quantityRequired: Number(row.quantity_required),
    origin: "direct",
  }));
};

export const getProductEffectiveInventoryLinks = async (productId: number): Promise<InventoryProductLink[]> => {
  const response = await request(`/inventory/product-effective-links/${productId}/`);
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    inventoryItemId: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemUnit: row.inventory_item_unit,
    quantityRequired: Number(row.quantity_required),
    origin: row.origin,
    categoryLinkId: row.category_link_id ?? undefined,
  }));
};

export const saveProductEffectiveInventoryLinks = async (
  productId: number,
  links: Array<{ inventoryItemId: number; quantityRequired: number }>
): Promise<InventoryProductLink[]> => {
  const response = await request(`/inventory/product-effective-links/${productId}/`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      links: links.map((row) => ({ inventory_item: row.inventoryItemId, quantity_required: row.quantityRequired })),
    }),
  });
  const data = await handleJson<Array<any>>(response);
  return data.map((row) => ({
    inventoryItemId: row.inventory_item,
    inventoryItemName: row.inventory_item_name,
    inventoryItemUnit: row.inventory_item_unit,
    quantityRequired: Number(row.quantity_required),
    origin: row.origin,
    categoryLinkId: row.category_link_id ?? undefined,
  }));
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
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
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
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    posImagePolicy: normalizePosImagePolicy(data.pos_image_policy),
    ...mapProductInventoryFields(data),
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
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
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
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    posImagePolicy: normalizePosImagePolicy(data.pos_image_policy),
    ...mapProductInventoryFields(data),
    modifierGroups: data.modifier_groups,
  };
};

export const updateProductKitchenRouting = async (
  productId: number,
  requiresKitchen: boolean,
): Promise<Product> => {
  const formData = new FormData();
  formData.append("requires_kitchen", requiresKitchen ? "true" : "false");
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
    is_archived?: boolean;
    requires_kitchen: boolean;
    inventory_stock_policy?: ProductInventoryStockPolicy;
    pos_image_policy?: PosImagePolicy;
    inventory_components_enabled?: boolean;
    track_inventory?: boolean;
    tracked_inventory_item?: number | null;
    tracked_inventory_item_name?: string | null;
    tracked_inventory_item_unit?: string | null;
    tracked_inventory_item_current_stock?: string | null;
    tracked_inventory_quantity?: string;
    auto_created_inventory_item?: boolean;
    tracked_inventory_warning?: string;
    modifier_groups: number[];
    modifier_groups_pos?: number[];
    modifier_group_links?: Array<{ group_id: number; show_in_pos: boolean }>;
  }>(response);
  const normalizedImageUrl = normalizeImageUrl(data);
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
    categoryId: data.category_id_display ?? 0,
    image: data.image,
    imagePath: data.image_path ?? null,
    imageUrl: normalizedImageUrl,
    image_url: normalizedImageUrl,
    image_path: data.image_path ?? null,
    available: data.available,
    isArchived: Boolean(data.is_archived),
    requiresKitchen: Boolean(data.requires_kitchen),
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    posImagePolicy: normalizePosImagePolicy(data.pos_image_policy),
    ...mapProductInventoryFields(data),
    modifierGroups: data.modifier_groups,
    modifierGroupsPos: data.modifier_groups_pos ?? [],
    modifierGroupLinks: (data.modifier_group_links ?? []).map((link) => ({
      groupId: link.group_id,
      showInPos: Boolean(link.show_in_pos),
    })),
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
    priority?: number;
    stackable?: boolean;
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
    priority: item.priority ?? 100,
    stackable: Boolean(item.stackable),
    hasConditions: Boolean(item.has_conditions),
    availableNow: Boolean(item.available_now),
  }));
};

export const getServiceTypes = async (): Promise<ServiceType[]> => {
  const response = await request("/core/service-types/");
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean; color_hex?: string | null }>>(response);
  return data.map((item) => ({
    id: item.id,
    key: item.key,
    label: item.label,
    isActive: item.is_active,
    sortOrder: item.sort_order ?? 0,
    disposablesEnabled: item.disposables_enabled === true,
    colorHex: item.color_hex ?? null,
  }));
};

export const listOrderTypes = async (): Promise<ServiceType[]> => {
  const response = await request('/core/order-types/');
  const data = await handleJson<Array<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean; color_hex?: string | null }>>(response);
  return data.map((item) => ({ id: item.id, key: item.key, label: item.label, isActive: item.is_active, sortOrder: item.sort_order ?? 0, disposablesEnabled: item.disposables_enabled === true, colorHex: item.color_hex ?? null }));
};

export const createOrderType = async (payload: { key: string; label: string; isActive: boolean; sortOrder: number; disposablesEnabled?: boolean; colorHex?: string | null }): Promise<ServiceType> => {
  const response = await request('/core/order-types/', {
    method: 'POST',
    body: JSON.stringify({ key: payload.key, label: payload.label, is_active: payload.isActive, sort_order: payload.sortOrder, disposables_enabled: payload.disposablesEnabled === true, color_hex: payload.colorHex || null }),
  });
  const data = await handleJson<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean; color_hex?: string | null }>(response);
  return { id: data.id, key: data.key, label: data.label, isActive: data.is_active, sortOrder: data.sort_order ?? 0, disposablesEnabled: data.disposables_enabled === true, colorHex: data.color_hex ?? null };
};

export const updateOrderType = async (id: number, payload: Partial<{ key: string; label: string; isActive: boolean; sortOrder: number; disposablesEnabled: boolean; colorHex: string | null }>): Promise<ServiceType> => {
  const body: Record<string, unknown> = {};
  if (payload.key !== undefined) body.key = payload.key;
  if (payload.label !== undefined) body.label = payload.label;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.sortOrder !== undefined) body.sort_order = payload.sortOrder;
  if (payload.disposablesEnabled !== undefined) body.disposables_enabled = payload.disposablesEnabled;
  if (payload.colorHex !== undefined) body.color_hex = payload.colorHex || null;
  const response = await request(`/core/order-types/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
  const data = await handleJson<{ id: number; key: string; label: string; is_active: boolean; sort_order?: number; disposables_enabled?: boolean; color_hex?: string | null }>(response);
  return { id: data.id, key: data.key, label: data.label, isActive: data.is_active, sortOrder: data.sort_order ?? 0, disposablesEnabled: data.disposables_enabled === true, colorHex: data.color_hex ?? null };
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
  whatsapp_num_cliente?: string;
  whatsapp_num_cliente_country?: string;
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
    guest_number?: number | null;
    guest_label?: string;
    table_guest_id?: number | null;
    table_guest_label?: string;
    table_guest_seat_number?: number | null;
    unit_price_list?: string | null;
    unit_price_special?: string | null;
    unit_price_before_discount?: string;
    discount_amount?: string;
    discount_percent?: string;
    discount_name?: string;
    unit_price_final?: string;
    line_total_before_discount?: string;
    line_total_discount?: string;
    line_total_final?: string;
    pricing_metadata?: Record<string, unknown> | null;
    requires_kitchen?: boolean;
    kitchen_status?: "pending" | "sent" | "ready" | "delivered";
    kitchen_status_label?: string;
    kitchen_sent_at?: string | null;
    kitchen_ready_at?: string | null;
    kitchen_delivered_at?: string | null;
    kitchen_completed_at?: string | null;
    kitchen_served_at?: string | null;
    is_pending_kitchen?: boolean;
    is_in_kitchen?: boolean;
    is_completed?: boolean;
    is_served?: boolean;
    applied_modifiers: Array<{ modifier_name_snapshot: string }>;
  }>;
  payment_status: Order["paymentStatus"];
  financial_status: Order["financialStatus"];
  total_paid: string;
  paid_total?: string;
  remaining: string;
  amount_due?: string;
  amount_due_cents?: number;
  remaining_cents?: number;
  refund_total: string;
  net_paid: string;
  discount_snapshot?: Record<string, unknown> | null;
  requires_kitchen?: boolean;
  send_to_kitchen?: boolean;
  gross_subtotal?: string;
  discount_total?: string;
  net_total?: string;
  disposable_total?: string;
  subtotal_before_discounts?: string;
  subtotal_after_discounts?: string;
  tax_total?: string;
  total_payable?: string;
  is_pending?: boolean;
  pending_state?: Order["pendingState"];
  pending_reference?: string;
  pending_marked_at?: string | null;
  pending_completed_at?: string | null;
  pending_completion_type?: Order["pendingCompletionType"];
  pending_completion_note?: string;
  table_session_id?: number | null;
  table_label?: string;
  table_order_mode?: "table" | "per_person" | null;
}): Order => {
  const createdAt = new Date(order.created_at);
  const prepTime = Math.floor((Date.now() - createdAt.getTime()) / 60000);
  const items = Array.isArray(order.items) ? order.items : [];
  const grossSubtotal = Number(order.gross_subtotal ?? order.subtotal_before_discounts ?? order.total);
  const netTotal = Number(order.net_total ?? order.total_payable ?? order.total);
  const paidTotal = Number(order.paid_total ?? order.total_paid ?? 0);
  const amountDue = Number(order.amount_due ?? order.remaining ?? 0);
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
      discountName: item.discount_name ?? "",
      unitPriceFinal: Number(item.unit_price_final ?? item.price_snapshot),
      lineTotalBeforeDiscount: Number(item.line_total_before_discount ?? Number(item.price_snapshot) * item.quantity),
      lineTotalDiscount: Number(item.line_total_discount ?? 0),
      lineTotalFinal: Number(item.line_total_final ?? Number(item.price_snapshot) * item.quantity),
      pricingMetadata: item.pricing_metadata ?? null,
      unitPriceOverride: item.unit_price_override != null ? Number(item.unit_price_override) : null,
      assignedName: item.assigned_name || undefined,
      guestNumber: item.guest_number ?? item.table_guest_seat_number ?? null,
      guestLabel: item.guest_label || item.table_guest_label || item.assigned_name || undefined,
      tableGuestId: item.table_guest_id ?? null,
      tableGuestLabel: item.table_guest_label || item.assigned_name || undefined,
      tableGuestSeatNumber: item.table_guest_seat_number ?? null,
      requiresKitchen: item.requires_kitchen !== false,
      kitchenStatus: item.kitchen_status ?? "pending",
      kitchenStatusLabel: item.kitchen_status_label || undefined,
      kitchenSentAt: item.kitchen_sent_at ?? null,
      kitchenReadyAt: item.kitchen_ready_at ?? null,
      kitchenDeliveredAt: item.kitchen_delivered_at ?? null,
      kitchenCompletedAt: item.kitchen_completed_at ?? item.kitchen_ready_at ?? null,
      kitchenServedAt: item.kitchen_served_at ?? item.kitchen_delivered_at ?? null,
      isPendingKitchen: Boolean(item.requires_kitchen !== false && (item.is_pending_kitchen ?? (item.kitchen_status ?? "pending") === "pending")),
      isInKitchen: Boolean(item.requires_kitchen !== false && (item.is_in_kitchen ?? item.kitchen_status === "sent")),
      isCompleted: Boolean(item.requires_kitchen !== false && (item.is_completed ?? item.kitchen_status === "ready")),
      isServed: Boolean(item.requires_kitchen !== false && (item.is_served ?? item.kitchen_status === "delivered")),
    })),
    total: Number(order.total),
    status: order.status,
    serviceType: order.service_type,
    createdAt,
    prepTime,
    customerName: order.customer_name || undefined,
    customerId: order.customer_id ?? undefined,
    whatsappNumCliente: (order.whatsapp_num_cliente || "").trim() || undefined,
    whatsappNumClienteCountry: (order.whatsapp_num_cliente_country || "").trim() || undefined,
    dteDocumentType: order.dte_document_type ?? "CF",
    ivaExempt: Boolean(order.iva_exempt),
    ivaExemptDiscount: Number(order.iva_exempt_discount ?? 0),
    paymentStatus: order.payment_status,
    financialStatus: order.financial_status,
    totalPaid: paidTotal,
    remaining: amountDue,
    grossSubtotal,
    netTotal,
    paidTotal,
    amountDue,
    amountDueCents:
      order.amount_due_cents !== undefined && order.amount_due_cents !== null
        ? Number(order.amount_due_cents)
        : toCents(netTotal),
    remainingCents:
      order.remaining_cents !== undefined && order.remaining_cents !== null
        ? Number(order.remaining_cents)
        : toCents(amountDue),
    refundTotal: Number(order.refund_total ?? 0),
    netPaid: Number(order.net_paid ?? 0),
    discountSnapshot: order.discount_snapshot ?? null,
    requiresKitchen: Boolean(order.requires_kitchen),
    sendToKitchen: Boolean(order.send_to_kitchen),
    discountTotal: order.discount_total != null ? Number(order.discount_total) : undefined,
    disposableTotal: order.disposable_total != null ? Number(order.disposable_total) : undefined,
    subtotalBeforeDiscounts: grossSubtotal,
    subtotalAfterDiscounts: Number(order.subtotal_after_discounts ?? order.total),
    taxTotal: Number(order.tax_total ?? 0),
    totalPayable: netTotal,
    isPending: Boolean(order.is_pending),
    pendingState: (order.pending_state ?? "none") as Order["pendingState"],
    pendingReference: order.pending_reference ?? "",
    pendingMarkedAt: order.pending_marked_at ?? null,
    pendingCompletedAt: order.pending_completed_at ?? null,
    pendingCompletionType: (order.pending_completion_type ?? "none") as Order["pendingCompletionType"],
    pendingCompletionNote: order.pending_completion_note ?? "",
    tableSessionId: order.table_session_id ?? null,
    tableLabel: order.table_label ?? "",
    tableOrderMode: order.table_order_mode ?? null,
  };
};

export const getPendingOrders = async (params?: { branchId?: number; tab?: "pending" | "finalized"; query?: string }): Promise<{ count: number; results: Order[] }> => {
  const qs = new URLSearchParams();
  if (params?.branchId) qs.set("branch_id", String(params.branchId));
  if (params?.tab) qs.set("tab", params.tab);
  if (params?.query) qs.set("q", params.query);
  const response = await request(`/orders/pending/${qs.toString() ? `?${qs.toString()}` : ""}`);
  const data = await handleJson<{ count: number; results: any[] }>(response);
  return {
    count: Number(data.count ?? 0),
    results: (data.results ?? []).map((row) => mapOrder(row)),
  };
};

export const setOrderPending = async (
  orderId: number,
  payload: {
    isPending: boolean;
    pendingState?: "pending_payment" | "paid_pending_delivery" | "in_kitchen" | "ready";
    authorizationPin?: string;
    pendingReference?: string;
    removalReason?: string;
    completionType?: "paid" | "removed" | "canceled";
    discountId?: number | null;
    discountMode?: "manual" | "auto";
    manualDiscountSnapshot?: Record<string, unknown> | null;
    items?: Array<{
      sourceOrderItemId?: number;
      productId?: number | null;
      productName: string;
      quantity: number;
      price: number;
      isCustom?: boolean;
      unitPriceOverride?: number | null;
      customCode?: string;
      assignedName?: string;
      tableGuestId?: number | null;
      modifiers: Array<{ id?: number; name: string; price: number }>;
    }>;
  }
): Promise<Order> => {
  const response = await request(`/orders/${orderId}/pending/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      is_pending: payload.isPending,
      pending_state: payload.pendingState,
      authorization_pin: payload.authorizationPin ?? "",
      pending_reference: payload.pendingReference ?? "",
      removal_reason: payload.removalReason ?? "",
      completion_type: payload.completionType ?? "",
      manual_discount_id: payload.discountId ?? undefined,
      discount_id: payload.discountId ?? undefined,
      discount_mode: payload.discountMode ?? undefined,
      manual_discount_snapshot: payload.manualDiscountSnapshot ?? undefined,
      items: (payload.items ?? []).map((item) => ({
        source_order_item_id: item.sourceOrderItemId ?? null,
        product_id: item.productId ?? null,
        product_name_snapshot: item.productName,
        quantity: item.quantity,
        price_snapshot: item.price,
        is_custom: Boolean(item.isCustom),
        unit_price_override: item.unitPriceOverride ?? null,
        snapshot_sku_or_code: item.customCode ?? "",
        assigned_name: item.assignedName ?? "",
        table_guest_id: item.tableGuestId ?? null,
        modifiers: (item.modifiers ?? []).map((mod) => ({ id: mod.id, name: mod.name, price: mod.price })),
      })),
    }),
  });
  return mapOrder(await handleJson<any>(response));
};

export const createOrder = async (payload: {
  serviceType: Order["serviceType"];
  customerName?: string;
  customerId?: number;
  whatsappNumCliente?: string;
  whatsappNumClienteCountry?: string;
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
    tableGuestId?: number | null;
  }>;
}): Promise<Order> => {
  const orderPayload = {
    service_type_key: payload.serviceType,
    customer_name: payload.customerName ?? "",
    customer_id: payload.customerId,
    whatsapp_num_cliente: (payload.whatsappNumCliente ?? "").trim(),
    whatsapp_num_cliente_country: (payload.whatsappNumClienteCountry ?? "").trim().toUpperCase(),
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
      table_guest_id: item.tableGuestId ?? null,
      modifiers: item.modifiers.map((modifier) => ({
        id: modifier.id,
        name: modifier.name,
        price: modifier.price,
      })),
    })),
  };

  if (API_DEBUG) {
    console.info("[pos-debug] create-order-payload", {
      customerId: orderPayload.customer_id ?? null,
      dteDocumentType: orderPayload.dte_document_type,
      whatsappNumCliente: orderPayload.whatsapp_num_cliente,
      whatsappNumClienteCountry: orderPayload.whatsapp_num_cliente_country,
      source: orderPayload.source,
      channel: orderPayload.channel,
      items: orderPayload.items.length,
    });
  }

  const response = await request("/orders/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(orderPayload),
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("text/html")) {
      throw new Error("Error al crear orden. Revisa backend logs.");
    }
  }

  try {
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
  } catch (error) {
    if (API_DEBUG) {
      const apiError = error as { message?: string; status?: number; code?: string };
      console.info("[pos-debug] create-order-error", {
        status: apiError?.status ?? null,
        code: apiError?.code ?? null,
        message: apiError?.message ?? "Unknown error",
      });
    }
    throw error;
  }
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
  payload: {
    customerId: number;
    dteDocumentType: "CF" | "CCF" | "SX";
    ivaExempt?: boolean;
    whatsappNumCliente?: string;
    whatsappNumClienteCountry?: string;
  }
): Promise<Order> => {
  const response = await request(`/orders/${orderId}/`, {
    method: "PATCH",
    body: JSON.stringify({
      customer_id: payload.customerId,
      dte_document_type: payload.dteDocumentType,
      iva_exempt: Boolean(payload.ivaExempt),
      whatsapp_num_cliente: (payload.whatsappNumCliente ?? "").trim(),
      whatsapp_num_cliente_country: (payload.whatsappNumClienteCountry ?? "").trim().toUpperCase(),
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
    inventoryStockPolicy: normalizeProductInventoryStockPolicy(data.inventory_stock_policy),
    ...mapProductInventoryFields(data),
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



export const getEmployeeWorkedHoursReport = async (filters: { dateFrom: string; dateTo: string; signal?: AbortSignal }): Promise<EmployeeWorkedHoursReport> => {
  const params = new URLSearchParams({
    start: filters.dateFrom,
    end: filters.dateTo,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  });
  const response = await request(`/reports/employee-worked-hours/?${params.toString()}`, { signal: filters.signal });
  const data = await handleJson<{
    employees?: Array<{ employee_id: number; employee_name: string; total_minutes: number; total_hours: string | number }>;
    totals?: { total_minutes?: number; total_hours?: string | number };
  }>(response);
  return {
    rows: (data.employees ?? []).map((row) => ({
      employeeId: Number(row.employee_id),
      employeeName: row.employee_name,
      totalMinutes: Number(row.total_minutes ?? 0),
      totalHours: Number(row.total_hours ?? 0),
    })),
    totals: {
      totalMinutes: Number(data.totals?.total_minutes ?? 0),
      totalHours: Number(data.totals?.total_hours ?? 0),
    },
  };
};

export const getEmployeeHoursSummary = async (filters: { dateFrom: string; dateTo: string; groupBy?: "month" | "week" | "custom"; signal?: AbortSignal }): Promise<EmployeeHoursSummaryResponse> => {
  const params = new URLSearchParams({
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    group_by: filters.groupBy ?? "month",
  });
  const response = await request(`/reports/employee-hours/?${params.toString()}`, { signal: filters.signal });
  const data = await handleJson<any>(response);
  return {
    dateFrom: data.date_from,
    dateTo: data.date_to,
    totals: {
      employeeCount: Number(data.totals?.employee_count ?? 0),
      totalShiftMinutes: Number(data.totals?.total_shift_minutes ?? 0),
      totalBreakMinutes: Number(data.totals?.total_break_minutes ?? 0),
      totalNetMinutes: Number(data.totals?.total_net_minutes ?? 0),
      totalHours: Number(data.totals?.total_hours ?? 0),
    },
    employees: (data.employees ?? []).map((row: any) => ({
      employeeId: Number(row.employee_id),
      name: row.name,
      role: row.role,
      daysWorked: Number(row.days_worked ?? 0),
      entriesCount: Number(row.entries_count ?? 0),
      exitsCount: Number(row.exits_count ?? 0),
      shiftMinutes: Number(row.shift_minutes ?? 0),
      breakMinutes: Number(row.break_minutes ?? 0),
      netMinutes: Number(row.net_minutes ?? 0),
      currentState: String(row.current_state ?? "OFF_SHIFT"),
      status: String(row.status ?? "active"),
    })),
  };
};

export const getEmployeeHoursDetail = async (employeeId: number, filters: { dateFrom: string; dateTo: string; signal?: AbortSignal }): Promise<EmployeeHoursDetailResponse> => {
  const params = new URLSearchParams({ date_from: filters.dateFrom, date_to: filters.dateTo });
  const response = await request(`/reports/employee-hours/${employeeId}/?${params.toString()}`, { signal: filters.signal });
  const data = await handleJson<any>(response);
  return {
    employee: { id: Number(data.employee.id), name: data.employee.name, role: data.employee.role },
    totals: {
      shiftMinutes: Number(data.totals?.shift_minutes ?? 0),
      breakMinutes: Number(data.totals?.break_minutes ?? 0),
      netMinutes: Number(data.totals?.net_minutes ?? 0),
    },
    days: (data.days ?? []).map((day: any) => ({
      date: String(day.date),
      dailyTotals: {
        shiftMinutes: Number(day.daily_totals?.shift_minutes ?? 0),
        breakMinutes: Number(day.daily_totals?.break_minutes ?? 0),
        netMinutes: Number(day.daily_totals?.net_minutes ?? 0),
      },
      cycles: (day.cycles ?? []).map((cycle: any) => ({
        id: Number(cycle.id ?? 0),
        clockInAt: cycle.clock_in_at,
        breakStartAt: cycle.break_start_at,
        breakEndAt: cycle.break_end_at,
        clockOutAt: cycle.clock_out_at,
        shiftMinutes: Number(cycle.shift_minutes ?? 0),
        breakMinutes: Number(cycle.break_minutes ?? 0),
        breakSeconds: Number(cycle.break_seconds ?? Math.round(Number(cycle.break_minutes ?? 0) * 60)),
        netMinutes: Number(cycle.net_minutes ?? 0),
        clockOutNextDay: Boolean(cycle.clock_out_next_day),
        status: String(cycle.status ?? "incompleto"),
      })),
    })),
  };
};

export const changeInternalPaymentMethod = async (
  paymentId: number,
  payload: { paymentMethodCode?: string; paymentMethodId?: number; reason?: string }
): Promise<{ paymentMethodCode: string; paymentMethodName: string }> => {
  const response = await request(`/payments/${paymentId}/internal-payment-method/`, {
    method: "PATCH",
    body: JSON.stringify({
      payment_method_code: payload.paymentMethodCode ?? "",
      payment_method_id: payload.paymentMethodId ?? null,
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
  waiter: "Mesero",
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
    throw new Error("Rol inválido. Usa Cajero, Mesero, Cocinero, Gerente o Administrador.");
  }
  const userRoleKey = payload.user?.role ? resolveRoleKey(payload.user.role) : undefined;
  if (payload.user?.role && !userRoleKey) {
    throw new Error("Rol de usuario inválido. Usa Administrador, Gerente, Cajero, Mesero o Cocinero.");
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


export const deleteEmployee = async (id: string): Promise<{ ok: boolean; deleted: boolean; message: string }> => {
  const response = await request(`/employees/${id}/`, { method: "DELETE" });
  return handleJson(response);
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
    throw new Error("Rol inválido. Usa Cajero, Mesero, Cocinero, Gerente o Administrador.");
  }
  const userRoleKey = payload.user?.role ? resolveRoleKey(payload.user.role) : undefined;
  if (payload.user?.role && !userRoleKey) {
    throw new Error("Rol de usuario inválido. Usa Administrador, Gerente, Cajero, Mesero o Cocinero.");
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
  hasActiveSession: boolean;
  latestEvent: "CLOCK_IN" | "CLOCK_OUT" | "NONE";
  lastClockIn: string | null;
  lastClockOut: string | null;
  totalEntriesToday: number;
  totalExitsToday: number;
  canClockIn: boolean;
  canBreakStart: boolean;
  canBreakEnd: boolean;
  canClockOut: boolean;
  state: "OFF_SHIFT" | "WORKING" | "ON_BREAK";
  accessAllowed: boolean;
  activeCycle: {
    sequence?: number;
    clock_in_at: string | null;
    break_seconds?: number;
    break_seconds?: number;
    break_minutes?: number;
    current_break_started_at?: string | null;
    breaks_count?: number;
    clock_out_at: string | null;
    started_on_previous_day?: boolean;
  } | null;
  cyclesToday: Array<{
    sequence?: number;
    clock_in_at: string | null;
    break_seconds?: number;
    break_minutes?: number;
    current_break_started_at?: string | null;
    breaks_count?: number;
    clock_out_at: string | null;
  }>;
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
  has_active_session?: boolean;
  latest_event?: "CLOCK_IN" | "CLOCK_OUT" | "NONE";
  last_clock_in?: string | null;
  last_clock_out?: string | null;
  total_entries_today?: number;
  total_exits_today?: number;
  can_clock_in: boolean;
  can_break_start: boolean;
  can_break_end: boolean;
  can_clock_out: boolean;
  state?: "OFF_SHIFT" | "WORKING" | "ON_BREAK";
  access_allowed?: boolean;
  active_cycle?: {
    sequence?: number;
    clock_in_at: string | null;
    break_seconds?: number;
    break_minutes?: number;
    current_break_started_at?: string | null;
    breaks_count?: number;
    clock_out_at: string | null;
    started_on_previous_day?: boolean;
  } | null;
  cycles_today?: Array<{
    sequence?: number;
    clock_in_at: string | null;
    break_seconds?: number;
    break_minutes?: number;
    current_break_started_at?: string | null;
    breaks_count?: number;
    clock_out_at: string | null;
  }>;
}): AttendanceState => ({
  employee: data.employee,
  date: data.date,
  clockIn: data.clock_in,
  breakStart: data.break_start,
  breakEnd: data.break_end,
  clockOut: data.clock_out,
  hasActiveSession: typeof data.has_active_session === "boolean"
    ? data.has_active_session
    : Boolean(data.clock_in) && (!data.clock_out || new Date(data.clock_in).getTime() > new Date(data.clock_out).getTime()),
  latestEvent: data.latest_event ?? "NONE",
  lastClockIn: data.last_clock_in ?? data.clock_in,
  lastClockOut: data.last_clock_out ?? data.clock_out,
  totalEntriesToday: Number(data.total_entries_today ?? (data.clock_in ? 1 : 0)),
  totalExitsToday: Number(data.total_exits_today ?? (data.clock_out ? 1 : 0)),
  canClockIn: data.can_clock_in,
  canBreakStart: data.can_break_start,
  canBreakEnd: data.can_break_end,
  canClockOut: data.can_clock_out,
  state: data.state ?? "OFF_SHIFT",
  accessAllowed: typeof data.access_allowed === "boolean" ? data.access_allowed : Boolean(data.has_active_session),
  activeCycle: data.active_cycle ?? null,
  cyclesToday: data.cycles_today ?? [],
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
  const response = await request(path, { method: "POST", body: JSON.stringify({}) });
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
      ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {}), ...(payload.x !== undefined ? { x: payload.x } : {}), ...(payload.y !== undefined ? { y: payload.y } : {}), ...(payload.width !== undefined ? { width: payload.width } : {}), ...(payload.height !== undefined ? { height: payload.height } : {}), ...(payload.color !== undefined ? { color: payload.color } : {}), ...(payload.operationalZoom !== undefined ? { operational_zoom: payload.operationalZoom } : {}), ...(payload.operationalOffsetX !== undefined ? { operational_offset_x: payload.operationalOffsetX } : {}), ...(payload.operationalOffsetY !== undefined ? { operational_offset_y: payload.operationalOffsetY } : {}),
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


export type CartAvailabilityItem = {
  productId: number;
  productName: string;
  resolvedPolicy: InventoryStockPolicy;
  policySource: "product" | "category" | "global";
  policySourceLabel: string;
  policyLabel: string;
  isTracked: boolean;
  hasComponents: boolean;
  tracksOwnInventory: boolean;
  duplicateTrackingComponent: boolean;
  canAddOne: boolean;
  maxAddableNow: number;
  currentCartQuantity: number;
  status: "ok" | "blocked" | "warning" | "allowed_without_stock";
  message?: string;
  missing: Array<{ inventoryItemId: number; name: string; available: string; reservedInCart: string; requiredForNext: string; missing: string; unit: string }>;
};

export type CartAvailability = {
  items: CartAvailabilityItem[];
  cartHasBlockedItems: boolean;
  cartHasWarnings: boolean;
};

export const checkCartInventoryAvailability = async (payload: { cartItems: Array<{ productId: number; quantity: number }>; candidateProductIds?: number[] }): Promise<CartAvailability> => {
  const response = await request("/inventory/cart-availability/", {
    method: "POST",
    body: JSON.stringify({
      cart_items: payload.cartItems.map((item) => ({ product_id: item.productId, quantity: item.quantity })),
      candidate_product_ids: payload.candidateProductIds ?? [],
    }),
  });
  const data = await handleJson<any>(response);
  return {
    cartHasBlockedItems: Boolean(data.cart_has_blocked_items),
    cartHasWarnings: Boolean(data.cart_has_warnings),
    items: Array.isArray(data.items) ? data.items.map((item: any) => ({
      productId: Number(item.product_id),
      productName: String(item.product_name ?? ""),
      resolvedPolicy: normalizeInventoryStockPolicy(item.resolved_policy),
      policySource: item.policy_source === "product" || item.policy_source === "category" ? item.policy_source : "global",
      policySourceLabel: String(item.policy_source_label ?? "Configuración global"),
      policyLabel: String(item.policy_label ?? "Permitir venta"),
      isTracked: Boolean(item.is_tracked),
      hasComponents: Boolean(item.has_components),
      tracksOwnInventory: Boolean(item.tracks_own_inventory),
      duplicateTrackingComponent: Boolean(item.duplicate_tracking_component),
      canAddOne: Boolean(item.can_add_one),
      maxAddableNow: Number(item.max_addable_now ?? 0),
      currentCartQuantity: Number(item.current_cart_quantity ?? 0),
      status: item.status ?? "ok",
      message: item.message ?? "",
      missing: Array.isArray(item.missing) ? item.missing.map((miss: any) => ({
        inventoryItemId: Number(miss.inventory_item_id),
        name: String(miss.name ?? ""),
        available: String(miss.available ?? "0"),
        reservedInCart: String(miss.reserved_in_cart ?? "0"),
        requiredForNext: String(miss.required_for_next ?? "0"),
        missing: String(miss.missing ?? "0"),
        unit: String(miss.unit ?? ""),
      })) : [],
    })) : [],
  };
};

export type InventoryAvailabilityItem = {
  inventoryItemId: number;
  name: string;
  sku?: string;
  unit: string;
  available: string;
  required: string;
  missing: string;
  affectedProducts: Array<{ productId: number; productName: string; quantity: string; policySource?: "product" | "category" | "global"; policySourceLabel?: string; policyLabel?: string }>;
};

export type InventoryAvailabilityCheck = {
  ok: boolean;
  policy: InventoryStockPolicy;
  hasInsufficientStock: boolean;
  items: InventoryAvailabilityItem[];
  message?: string;
};

const mapInventoryAvailability = (data: any): InventoryAvailabilityCheck => ({
  ok: Boolean(data.ok),
  policy: normalizeInventoryStockPolicy(data.policy),
  hasInsufficientStock: Boolean(data.has_insufficient_stock),
  message: data.message,
  items: Array.isArray(data.items) ? data.items.map((item: any) => ({
    inventoryItemId: Number(item.inventory_item_id),
    name: String(item.name ?? ""),
    sku: item.sku ?? "",
    unit: String(item.unit ?? ""),
    available: String(item.available ?? "0"),
    required: String(item.required ?? "0"),
    missing: String(item.missing ?? "0"),
    affectedProducts: Array.isArray(item.affected_products) ? item.affected_products.map((product: any) => ({
      productId: Number(product.product_id),
      productName: String(product.product_name ?? ""),
      quantity: String(product.quantity ?? "0"),
      policySource: product.policy_source === "product" || product.policy_source === "category" ? product.policy_source : "global",
      policySourceLabel: String(product.policy_source_label ?? "Configuración global"),
      policyLabel: String(product.policy_label ?? "Permitir venta"),
    })) : [],
  })) : [],
});

export const checkOrderInventoryAvailability = async (orderId: number | string): Promise<InventoryAvailabilityCheck> => {
  const response = await request(`/inventory/orders/${orderId}/availability-check/`, { method: "POST" });
  return mapInventoryAvailability(await handleJson<any>(response));
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
  paymentScope?: "order" | "guest" | "custom" | "items" | "split_part";
  tableSessionId?: number | null;
  tableGuestId?: number | null;
  guestNumber?: number | null;
  guestLabel?: string;
  orderItemIds?: number[];
  inventoryWarningConfirmed?: boolean;
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
      payment_scope: payload.paymentScope ?? "order",
      table_session: payload.tableSessionId ?? null,
      table_guest: payload.tableGuestId ?? null,
      guest_number: payload.guestNumber ?? null,
      guest_label: payload.guestLabel ?? "",
      order_item_ids: payload.orderItemIds ?? [],
      inventory_warning_confirmed: Boolean(payload.inventoryWarningConfirmed),
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
    allocations?: Array<{
      id: number;
      table_session?: number | null;
      table_guest?: number | null;
      order_item?: number | null;
      guest_number?: number | null;
      guest_label?: string;
      amount: string;
      amount_cents: number;
      created_at?: string | null;
    }>;
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
    allocations: (data.allocations ?? []).map((allocation) => ({
      id: allocation.id,
      tableSessionId: allocation.table_session ?? null,
      tableGuestId: allocation.table_guest ?? null,
      orderItemId: allocation.order_item ?? null,
      guestNumber: allocation.guest_number ?? null,
      guestLabel: allocation.guest_label ?? "",
      amount: Number(allocation.amount),
      amountCents: Number(allocation.amount_cents ?? Math.round(Number(allocation.amount || 0) * 100)),
      createdAt: allocation.created_at ? new Date(allocation.created_at) : null,
    })),
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
  const response = await request(`/payments/${paymentId}/print-ticket/?t=${Date.now()}`, { method: "POST", cache: "no-store" });
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
  return { available: Boolean(data.available), queue: data.queue || "TSP143-(STR_T-001)" };
};



const mapPaymentMethodOption = (m: any): PaymentMethodOption => ({
  id: m.id,
  code: m.code,
  name: m.name,
  isCash: Boolean(m.is_cash),
  sortOrder: Number(m.sort_order ?? 0),
  isActive: Boolean(m.is_active ?? true),
  colorHex: m.color_hex || null,
  isDefault: Boolean(m.is_default),
  fiscalPaymentType: (m.fiscal_payment_type || (m.is_cash ? "CASH" : "TRANSFER")) as PaymentMethodOption["fiscalPaymentType"],
  linkedOrderTypeId: m.linked_order_type_id ?? null,
  linkedOrderTypeName: m.linked_order_type_name ?? null,
  autoPrintTicket: Boolean(m.auto_print_ticket),
});

export const getPaymentMethods = async (options?: { includeInactive?: boolean }): Promise<PaymentMethodOption[]> => {
  const query = options?.includeInactive ? '?include_inactive=1' : '';
  const response = await request(`/payments/methods/${query}`);
  const data = await handleJson<Array<any>>(response);
  return data.map(mapPaymentMethodOption);
};

export const createPaymentMethod = async (payload: Partial<PaymentMethodOption> & { code: string; name: string }): Promise<PaymentMethodOption> => {
  const response = await request('/payments/methods/', {
    method: 'POST',
    body: JSON.stringify({
      code: payload.code,
      name: payload.name,
      is_cash: Boolean(payload.isCash),
      sort_order: Number(payload.sortOrder ?? 0),
      is_active: payload.isActive !== false,
      color_hex: payload.colorHex || '',
      is_default: Boolean(payload.isDefault),
      fiscal_payment_type: payload.fiscalPaymentType || (payload.isCash ? "CASH" : "TRANSFER"),
      linked_order_type_id: payload.linkedOrderTypeId ?? null,
      auto_print_ticket: Boolean(payload.autoPrintTicket),
    }),
  });
  return mapPaymentMethodOption(await handleJson<any>(response));
};

export const updatePaymentMethod = async (id: number, payload: Partial<PaymentMethodOption>): Promise<PaymentMethodOption> => {
  const body: Record<string, unknown> = {};
  if (payload.code !== undefined) body.code = payload.code;
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.isCash !== undefined) body.is_cash = payload.isCash;
  if (payload.sortOrder !== undefined) body.sort_order = payload.sortOrder;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.colorHex !== undefined) body.color_hex = payload.colorHex || '';
  if (payload.isDefault !== undefined) body.is_default = payload.isDefault;
  if (payload.fiscalPaymentType !== undefined) body.fiscal_payment_type = payload.fiscalPaymentType;
  if (payload.linkedOrderTypeId !== undefined) body.linked_order_type_id = payload.linkedOrderTypeId ?? null;
  if (payload.autoPrintTicket !== undefined) body.auto_print_ticket = payload.autoPrintTicket;
  const response = await request(`/payments/methods/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
  return mapPaymentMethodOption(await handleJson<any>(response));
};

export const deletePaymentMethod = async (id: number): Promise<{ hidden: boolean; detail?: string }> => {
  const response = await request(`/payments/methods/${id}/`, { method: 'DELETE' });
  if (response.status === 204) return { hidden: false };
  const data = await handleJson<any>(response);
  return { hidden: Boolean(data?.hidden), detail: data?.detail };
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
      allocations?: Array<{
        id: number;
        table_session?: number | null;
        table_guest?: number | null;
        order_item?: number | null;
        guest_number?: number | null;
        guest_label?: string;
        amount: string;
        amount_cents: number;
        created_at?: string | null;
      }>;
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
    allocations: (payment.allocations ?? []).map((allocation) => ({
      id: allocation.id,
      tableSessionId: allocation.table_session ?? null,
      tableGuestId: allocation.table_guest ?? null,
      orderItemId: allocation.order_item ?? null,
      guestNumber: allocation.guest_number ?? null,
      guestLabel: allocation.guest_label ?? "",
      amount: Number(allocation.amount),
      amountCents: Number(allocation.amount_cents ?? Math.round(Number(allocation.amount || 0) * 100)),
      createdAt: allocation.created_at ? new Date(allocation.created_at) : null,
    })),
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
): Promise<{
  order: Order;
  action: "invalidate" | "credit_note" | "internal_refund";
  message?: string;
  fiscalResult?: { attempted: boolean; success: boolean; message: string };
}> => {
  const response = await request(`/payments/${paymentId}/record-refund/`, {
    method: "POST",
    body: JSON.stringify({ reason: payload?.reason ?? "" }),
  });
  const data = await handleJson<{
    order: Parameters<typeof mapOrder>[0];
    action: "invalidate" | "credit_note" | "internal_refund";
    message?: string;
    fiscal_result?: { attempted: boolean; success: boolean; message: string };
  }>(response);
  return { order: mapOrder(data.order), action: data.action, message: data.message, fiscalResult: data.fiscal_result };
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
  const hasOpenSession = Boolean(data.has_open_cash_session ?? data.has_open_session);
  const session = data.session ?? null;
  if (!hasOpenSession || !session) {
    return {
      open: false,
      hasOpenCashSession: false,
      canOpenCash: Boolean(data.can_open_cash ?? true),
      canCloseCash: Boolean(data.can_close_cash ?? false),
      pendingOpenOrdersCount: Number(data.pending_orders_count ?? 0),
      cashAutoClose: data.cash_auto_close ?? undefined,
      lastOpenedAt: data.last_opened_at ?? null,
      lastClosedAt: data.last_closed_at ?? null,
      totalSessionsToday: Number(data.total_sessions_today ?? 0),
    };
  }
  return {
    open: true,
    hasOpenCashSession: true,
    canOpenCash: Boolean(data.can_open_cash ?? false),
    canCloseCash: Boolean(data.can_close_cash ?? true),
    pendingOpenOrdersCount: Number(data.pending_orders_count ?? 0),
    cashAutoClose: data.cash_auto_close ?? undefined,
    lastOpenedAt: data.last_opened_at ?? session.opened_at ?? null,
    lastClosedAt: data.last_closed_at ?? session.closed_at ?? null,
    totalSessionsToday: Number(data.total_sessions_today ?? 0),
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
      countedBills: Number(data.summary?.counted_bills ?? 0),
      countedCoins: Number(data.summary?.counted_coins ?? 0),
      countedPosCards: Number(data.summary?.counted_pos_cards ?? 0),
      countedPedidosYa: Number(data.summary?.counted_pedidos_ya ?? 0),
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
  closingCashCounted: number | string,
  notes?: string,
  totals?: { bills?: number | string; coins?: number | string; posCards?: number | string; pedidosYa?: number | string },
  options?: { sessionId?: number }
): Promise<{ sessionId?: number; ticketText?: string; printed?: boolean; printError?: string | null }> => {
  const branchIdRaw = localStorage.getItem("selected_branch_id");
  const data = await handleJson<any>(await request('/cashier/session/close/', {
    method: 'POST',
    body: JSON.stringify({
      ...(options?.sessionId ? { session_id: Number(options.sessionId) } : {}),
      total_contado: moneyToFixedString(closingCashCounted),
      total_billetes: moneyToFixedString(totals?.bills ?? 0),
      total_monedas: moneyToFixedString(totals?.coins ?? 0),
      total_pos_tarjetas: moneyToFixedString(totals?.posCards ?? 0),
      total_pedidos_ya: moneyToFixedString(totals?.pedidosYa ?? 0),
      notes: notes ?? '',
      ...(branchIdRaw && Number.isFinite(Number(branchIdRaw)) ? { branch_id: Number(branchIdRaw) } : {}),
    }),
  }));
  return {
    sessionId: Number(data.session?.id ?? 0) || undefined,
    ticketText: data.ticket_text,
    printed: Boolean(data.printed),
    printError: data.print_error ?? null,
  };
};

export const getCashTransactions = async (sessionId?: number, options?: { includeAll?: boolean }): Promise<CashTransaction[]> => {
  const params = new URLSearchParams();
  if (sessionId) params.set('session_id', String(sessionId));
  if (options?.includeAll) params.set('include', 'all');
  const response = await request(`/cashier/transactions/${params.toString() ? `?${params.toString()}` : ''}`);
  const data = await handleJson<Array<any>>(response);
  return data.map((tx) => ({
    id: tx.id,
    type: tx.type,
    displayType: tx.display_type,
    impactsCash: Boolean(tx.impacts_cash),
    amount: Number(tx.amount),
    description: tx.description,
    paymentId: tx.payment_id ?? null,
    refundId: tx.refund_id ?? null,
    orderId: tx.order_id ?? null,
    createdAt: tx.created_at,
  }));
};

type RecentSaleActionResponse = {
  id: number | string;
  payment_id: number | string;
  order_number?: string | null;
  control_number?: string | null;
  customer_name?: string | null;
  payment_method?: string | null;
  total?: number | string | null;
  status?: string | null;
  created_at?: string | null;
  can_print_ticket?: boolean;
  can_send_dte?: boolean;
};

export const getLastSaleAction = async (): Promise<LastSaleAction | null> => {
  const response = await request('/cashier/last-sale/');
  if (response.status === 404) return null;
  const row = await handleJson<RecentSaleActionResponse & { order_id?: number | string }>(response);
  return {
    id: Number(row.id),
    orderId: Number(row.order_id ?? row.id),
    paymentId: Number(row.payment_id),
    orderNumber: String(row.order_number ?? `ORD-${row.id}`),
    controlNumber: String(row.control_number ?? ""),
    customerName: String(row.customer_name ?? "CONSUMIDOR FINAL"),
    paymentMethod: String(row.payment_method ?? ""),
    total: Number(row.total ?? 0),
    status: String(row.status ?? ""),
    createdAt: String(row.created_at ?? ""),
    canPrintTicket: Boolean(row.can_print_ticket),
    canSendDte: Boolean(row.can_send_dte),
  };
};

export const getRecentSalesActions = async (): Promise<RecentSaleAction[]> => {
  const response = await request('/cashier/recent-sales/');
  const data = await handleJson<RecentSaleActionResponse[]>(response);
  return data.map((row) => ({
    id: Number(row.id),
    paymentId: Number(row.payment_id),
    orderNumber: String(row.order_number ?? `ORD-${row.id}`),
    controlNumber: String(row.control_number ?? ""),
    customerName: String(row.customer_name ?? "CONSUMIDOR FINAL"),
    paymentMethod: String(row.payment_method ?? ""),
    total: Number(row.total ?? 0),
    status: String(row.status ?? ""),
    createdAt: String(row.created_at ?? ""),
    canPrintTicket: Boolean(row.can_print_ticket),
    canSendDte: Boolean(row.can_send_dte),
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
      countedBills: Number(row.summary_snapshot?.counted_bills ?? 0),
      countedCoins: Number(row.summary_snapshot?.counted_coins ?? 0),
      countedPosCards: Number(row.summary_snapshot?.counted_pos_cards ?? 0),
      countedPedidosYa: Number(row.summary_snapshot?.counted_pedidos_ya ?? 0),
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
      countedBills: Number(data.summary.counted_bills ?? 0),
      countedCoins: Number(data.summary.counted_coins ?? 0),
      countedPosCards: Number(data.summary.counted_pos_cards ?? 0),
      countedPedidosYa: Number(data.summary.counted_pedidos_ya ?? 0),
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
  const response = await request(`/cashier/sessions/${sessionId}/ticket.pdf`, {
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
    throw new Error("Respuesta inválida al descargar PDF de cierre de caja.");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
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
};



export const fetchPaymentTicketBlob = async (paymentId: number): Promise<Blob> => {
  const response = await request(`/payments/${paymentId}/ticket.pdf?t=${Date.now()}`, {
    headers: { Accept: "application/pdf" },
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error("No se encontró el ticket solicitado.");
    throw new Error("No se pudo preparar el ticket. Intenta nuevamente.");
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/pdf")) {
    throw new Error("El servidor devolvió un formato de ticket no válido.");
  }
  return response.blob();
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

export const downloadDteExportZip = async (payload: { year: number; month: number; type: "json" | "f07" | "pdf" }): Promise<string> => {
  const response = await request("/reports/dte/export/", {
    method: "POST",
    headers: { Accept: "application/zip,application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const errorPayload = await response.json().catch(() => ({}));
      const detail = String(errorPayload?.detail || errorPayload?.error || "").trim();
      throw new Error(detail || `No se pudo exportar DTE (${response.status})`);
    }
    const raw = await response.text().catch(() => "");
    throw new Error(raw || `No se pudo exportar DTE (${response.status})`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/zip")) {
    throw new Error("Respuesta inválida al exportar DTE.");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] || `dte_${payload.type}_${payload.year}_${String(payload.month).padStart(2, "0")}.zip`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return filename;
};

export const dteResend = async (
  id: number
): Promise<{ success: boolean; pending?: boolean; status?: string; message: string; record: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/resend/`, { method: "POST" });
  const payload = await handleJson<any>(res);
  return {
    success: Boolean(payload.success),
    pending: Boolean(payload.pending),
    status: payload.status,
    message: payload.message ?? "Reenvío procesado",
    record: payload.record as DTERecord,
  };
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
  channels: Array<"whatsapp" | "email">,
  options?: { numCliente?: string; clienteTelefono?: string; destinationSource?: "manual_extra" | "none" }
): Promise<{
  success: boolean;
  summary: string;
  orderId?: number;
  issuedId?: number;
  results: Record<
    string,
    {
      ok: boolean;
      statusCode: number | null;
      providerStatus: number | null;
      providerMessage: string | null;
      recipient: string | null;
      error: string | null;
    }
  >;
}> => {
  const res = await request(`/dte/issued/${id}/deliver/`, {
    method: "POST",
    body: JSON.stringify({
      channels,
      ...(options?.numCliente ? { num_cliente: options.numCliente } : {}),
      ...(options?.clienteTelefono ? { cliente_telefono: options.clienteTelefono, telefono_cliente: options.clienteTelefono, customer_phone: options.clienteTelefono } : {}),
      ...(options?.destinationSource ? { destination_source: options.destinationSource } : {}),
    }),
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
        {
          ok: Boolean(value?.ok),
          statusCode: value?.status_code ?? null,
          providerStatus: value?.provider_status ?? null,
          providerMessage: value?.provider_message ?? null,
          recipient: value?.recipient ?? null,
          error: value?.error ?? null,
        },
      ])
    ),
  };
};

export const dteDeliverByOrder = async (
  orderId: number,
  channels: Array<"whatsapp" | "email">,
  options?: { numCliente?: string; clienteTelefono?: string; destinationSource?: "manual_extra" | "none" }
): Promise<{
  success: boolean;
  summary: string;
  orderId?: number;
  issuedId?: number;
  results: Record<
    string,
    {
      ok: boolean;
      statusCode: number | null;
      providerStatus: number | null;
      providerMessage: string | null;
      recipient: string | null;
      error: string | null;
    }
  >;
}> => {
  const res = await request(`/dte/orders/${orderId}/deliver/`, {
    method: "POST",
    body: JSON.stringify({
      channels,
      ...(options?.numCliente ? { num_cliente: options.numCliente } : {}),
      ...(options?.clienteTelefono ? { cliente_telefono: options.clienteTelefono, telefono_cliente: options.clienteTelefono, customer_phone: options.clienteTelefono } : {}),
      ...(options?.destinationSource ? { destination_source: options.destinationSource } : {}),
    }),
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
        {
          ok: Boolean(value?.ok),
          statusCode: value?.status_code ?? null,
          providerStatus: value?.provider_status ?? null,
          providerMessage: value?.provider_message ?? null,
          recipient: value?.recipient ?? null,
          error: value?.error ?? null,
        },
      ])
    ),
  };
};

export const dteInvalidate = async (
  id: number,
  payload: { motivoAnulacion: string; numDocResponsable: string }
): Promise<{ message: string; record?: DTERecord }> => {
  const res = await request(`/dte/issued/${id}/invalidate/`, {
    method: "POST",
    body: JSON.stringify({
      motivo_anulacion: payload.motivoAnulacion,
      num_doc_responsable: payload.numDocResponsable,
    }),
  });
  const data = await handleJson<any>(res);
  return { message: data.message ?? "DTE invalidado", record: data.record };
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
  isIvaExempt: Boolean(c.is_iva_exempt),
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
      is_iva_exempt: Boolean(payload.isIvaExempt),
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
      ...(payload.isIvaExempt !== undefined ? { is_iva_exempt: payload.isIvaExempt } : {}),
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
  const response = await request(`/orders/${orderId}/receipt.pdf?t=${Date.now()}`, { headers: { Accept: "application/pdf" }, cache: "no-store" });
  if (!response.ok) throw new Error("No se pudo descargar PDF");
  return response.blob();
};


export const updateEmployeeHoursCycle = async (cycleId: number, payload: { date: string; clockInTime: string; clockOutTime: string | null; clockOutNextDay: boolean; shiftSeconds: number; breakSeconds: number; reason: string; }) => {
  const response = await request(`/reports/employee-hours/cycles/${cycleId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: payload.date, clock_in_time: payload.clockInTime, clock_out_time: payload.clockOutTime, clock_out_next_day: payload.clockOutNextDay, shift_seconds: payload.shiftSeconds, break_seconds: payload.breakSeconds, reason: payload.reason }),
  });
  return handleJson<any>(response);
};

export const createEmployeeHoursCycle = async (payload: { employeeId: number; date: string; clockInTime: string; clockOutTime: string | null; clockOutNextDay: boolean; reason: string; shiftSeconds?: number; breakSeconds?: number; breakStartTime?: string | null; breakEndTime?: string | null; }) => {
  const response = await request(`/reports/employee-hours/cycles/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_id: payload.employeeId, date: payload.date, clock_in_time: payload.clockInTime, break_start_time: payload.breakStartTime, break_end_time: payload.breakEndTime, clock_out_time: payload.clockOutTime, clock_out_next_day: payload.clockOutNextDay, shift_seconds: payload.shiftSeconds, break_seconds: payload.breakSeconds, reason: payload.reason }),
  });
  return handleJson<any>(response);
};

export const getInventorySuppliers = async (q?: string, isActive?: boolean): Promise<InventorySupplier[]> => {
  const params = new URLSearchParams();
  if (q?.trim()) params.set("q", q.trim());
  if (isActive !== undefined) params.set("is_active", String(isActive));
  const response = await request(`/inventory/suppliers/${params.toString() ? `?${params.toString()}` : ""}`);
  const data = await handleJson<any[]>(response);
  return data.map(mapInventorySupplier);
};

export const saveInventorySupplier = async (payload: Partial<InventorySupplier> & { id?: number; name: string }): Promise<InventorySupplier> => {
  const response = await request(`/inventory/suppliers/${payload.id ? `${payload.id}/` : ""}`, {
    method: payload.id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      code: payload.code ?? "",
      contact_name: payload.contactName ?? "",
      phone: payload.phone ?? "",
      email: payload.email ?? "",
      address: payload.address ?? "",
      tax_id: payload.taxId ?? "",
      notes: payload.notes ?? "",
      is_active: payload.isActive ?? true,
    }),
  });
  return mapInventorySupplier(await handleJson<any>(response));
};

export const deleteInventorySupplier = async (id: number): Promise<void> => {
  const response = await request(`/inventory/suppliers/${id}/`, { method: "DELETE" });
  if (response.status !== 204) await handleJson<any>(response);
};

export const getPurchaseOrders = async (filters?: { q?: string; supplier?: string; status?: string; dateFrom?: string; dateTo?: string }): Promise<PurchaseOrder[]> => {
  const params = new URLSearchParams();
  if (filters?.q) params.set("q", filters.q);
  if (filters?.supplier) params.set("supplier", filters.supplier);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  const response = await request(`/inventory/purchase-orders/${params.toString() ? `?${params.toString()}` : ""}`);
  const data = await handleJson<any[]>(response);
  return data.map(mapPurchaseOrder);
};

export const savePurchaseOrder = async (payload: {
  id?: number;
  supplier: number;
  paymentCategory: string;
  expectedDate?: string | null;
  notes?: string;
  proofReference?: string;
  proofUrl?: string;
  lines: Array<{ inventoryItem: number; description?: string; quantityOrdered: number; purchaseUnit?: string; purchaseToInventoryFactor: number; unitCost: number; notes?: string }>;
}): Promise<PurchaseOrder> => {
  const response = await request(`/inventory/purchase-orders/${payload.id ? `${payload.id}/` : ""}`, {
    method: payload.id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      supplier: payload.supplier,
      payment_category: payload.paymentCategory,
      expected_date: payload.expectedDate || null,
      notes: payload.notes ?? "",
      proof_reference: payload.proofReference ?? "",
      proof_url: payload.proofUrl ?? "",
      lines: payload.lines.map((line) => ({
        inventory_item: line.inventoryItem,
        description: line.description ?? "",
        quantity_ordered: line.quantityOrdered,
        purchase_unit: line.purchaseUnit ?? "",
        purchase_to_inventory_factor: line.purchaseToInventoryFactor,
        unit_cost: line.unitCost,
        notes: line.notes ?? "",
      })),
    }),
  });
  return mapPurchaseOrder(await handleJson<any>(response));
};

export const approvePurchaseOrder = async (id: number): Promise<PurchaseOrder> => mapPurchaseOrder(await handleJson<any>(await request(`/inventory/purchase-orders/${id}/approve/`, { method: "POST" })));
export const cancelPurchaseOrder = async (id: number, reason?: string): Promise<PurchaseOrder> => mapPurchaseOrder(await handleJson<any>(await request(`/inventory/purchase-orders/${id}/cancel/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason: reason ?? "" }) })));
export const deletePurchaseOrder = async (id: number): Promise<void> => { const response = await request(`/inventory/purchase-orders/${id}/`, { method: "DELETE" }); if (response.status !== 204) await handleJson<any>(response); };
export const receivePurchaseOrder = async (id: number, payload: { notes?: string; updateUnitCost?: boolean; lines: Array<{ lineId: number; quantityReceived: number; notes?: string }> }): Promise<PurchaseOrder> => {
  const response = await request(`/inventory/purchase-orders/${id}/receive/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      notes: payload.notes ?? "",
      update_unit_cost: payload.updateUnitCost ?? true,
      lines: payload.lines.map((line) => ({ line_id: line.lineId, quantity_received: line.quantityReceived, notes: line.notes ?? "" })),
    }),
  });
  const data = await handleJson<any>(response);
  return mapPurchaseOrder(data.order);
};


export type DiningArea = { id: number; name: string; sortOrder: number; isActive: boolean; x:number; y:number; width:number; height:number; color?:string; operationalZoom:number; operationalOffsetX:number; operationalOffsetY:number };
export type RestaurantTable = { id: number; area: number; areaName?: string; name: string; number: number; capacity: number; shape: "round"|"square"|"rectangle"|"booth"|"bar"; x: number; y: number; width: number; height: number; rotation: number; color?: string; isActive: boolean; sortOrder: number };
export type TableGuest = { id: number; label: string; baseLabel: string; displayName: string; customName: string; seatNumber: number; isActive: boolean; isPaid: boolean };
export type TableSession = { id: number; status: string; guestsCount: number; orderMode: "table"|"per_person"; primaryOrder?: number | null; tableIds: number[]; guests: TableGuest[]; openedAt?: string | null; totalCached?: number; groupNumber?: number | null; sentCount?: number; savedCount?: number; detail?: string };
export type TableLayout = { areas: DiningArea[]; tables: RestaurantTable[]; sessions: TableSession[] };
export type TableKitchenItem = { id: number; productName: string; quantity: number; assignedName?: string; guestNumber?: number | null; guestLabel?: string; tableGuestId?: number | null; tableGuestLabel?: string; tableGuestSeatNumber?: number | null; kitchenStatus: "pending"|"sent"|"ready"|"delivered"; kitchenStatusLabel?: string; kitchenSentAt?: string | null; kitchenReadyAt?: string | null; kitchenDeliveredAt?: string | null; kitchenCompletedAt?: string | null; kitchenServedAt?: string | null; isPendingKitchen?: boolean; isInKitchen?: boolean; isCompleted?: boolean; isServed?: boolean; modifiers: string[]; lineTotal: number };
export type TableKitchenPerson = { label: string; items: TableKitchenItem[]; total: number };
export type TableKitchenSessionSummary = { sessionId: number; orderId?: number | null; status: string; tables: string[]; tableLabel: string; guestsCount: number; orderMode: "table"|"per_person"; total: number; remaining: number; items: TableKitchenItem[]; people: TableKitchenPerson[] };
export type TableReadySummary = { tableId: number | null; tableIds: number[]; tableName: string; sessionId: number; orderId?: number | null; readyCount: number; groupLabel?: string | null; items: TableKitchenItem[] };
type RawDiningArea = Partial<Record<"id"|"name"|"sort_order"|"is_active"|"x"|"y"|"width"|"height"|"color"|"operational_zoom"|"operational_offset_x"|"operational_offset_y", unknown>>;
type RawRestaurantTable = Partial<Record<"id"|"area"|"area_name"|"name"|"number"|"capacity"|"shape"|"x"|"y"|"width"|"height"|"rotation"|"color"|"is_active"|"sort_order", unknown>>;
type RawTableGuest = Partial<Record<"id"|"label"|"base_label"|"display_name"|"custom_name"|"seat_number"|"is_active"|"is_paid", unknown>>;
type RawTableSession = Partial<Record<"id"|"status"|"guests_count"|"guest_count"|"order_mode"|"primary_order"|"order_id"|"table_ids"|"table_id"|"guests"|"opened_at"|"total_cached"|"group_number", unknown>>;
type RawTableKitchenItem = Partial<Record<"id"|"product_name"|"productName"|"quantity"|"assigned_name"|"guest_number"|"guest_label"|"table_guest_id"|"table_guest_label"|"table_guest_seat_number"|"kitchen_status"|"kitchen_status_label"|"kitchen_sent_at"|"kitchen_ready_at"|"kitchen_delivered_at"|"kitchen_completed_at"|"kitchen_served_at"|"is_pending_kitchen"|"is_in_kitchen"|"is_completed"|"is_served"|"modifiers"|"line_total", unknown>>;
type RawTableKitchenPerson = Partial<Record<"label"|"total"|"items", unknown>>;
type RawTableKitchenSession = Partial<Record<"session_id"|"order_id"|"status"|"tables"|"table_label"|"guests_count"|"order_mode"|"total"|"remaining"|"items"|"people", unknown>>;
type RawTableReadySummary = Partial<Record<"table_id"|"table_ids"|"table_name"|"session_id"|"order_id"|"ready_count"|"group_label"|"items", unknown>>;
type TableKitchenStatus = TableKitchenItem["kitchenStatus"];

const normalizeKitchenStatus = (value: unknown): TableKitchenStatus => {
  if (value === "sent" || value === "ready" || value === "delivered") return value;
  return "pending";
};
const mapDiningArea = (x: RawDiningArea): DiningArea => ({ id: Number(x.id), name: String(x.name ?? ""), sortOrder: Number(x.sort_order ?? 0), isActive: Boolean(x.is_active), x:Number(x.x??0), y:Number(x.y??0), width:Number(x.width??320), height:Number(x.height??220), color:String(x.color??""), operationalZoom:Number(x.operational_zoom??1), operationalOffsetX:Number(x.operational_offset_x??0), operationalOffsetY:Number(x.operational_offset_y??0) });
const mapRestaurantTable = (x: RawRestaurantTable): RestaurantTable => ({ id: Number(x.id), area: Number(x.area), areaName: x.area_name ? String(x.area_name) : undefined, name: String(x.name ?? ""), number: Number(x.number ?? 0), capacity: Number(x.capacity ?? 1), shape: x.shape === "square" || x.shape === "rectangle" || x.shape === "booth" || x.shape === "bar" ? x.shape : "round", x: Number(x.x ?? 0), y: Number(x.y ?? 0), width: Number(x.width ?? 120), height: Number(x.height ?? 80), rotation: Number(x.rotation ?? 0), color: String(x.color ?? ''), isActive: Boolean(x.is_active), sortOrder: Number(x.sort_order ?? 0) });
const mapTableGuest = (guest: RawTableGuest): TableGuest => {
  const baseLabel = String(guest.base_label ?? guest.label ?? "");
  const displayName = String(guest.display_name ?? guest.custom_name ?? "");
  const label = String(guest.label ?? (displayName || baseLabel));
  return {
    id: Number(guest.id),
    label,
    baseLabel,
    displayName,
    customName: displayName,
    seatNumber: Number(guest.seat_number ?? 1),
    isActive: Boolean(guest.is_active),
    isPaid: Boolean(guest.is_paid),
  };
};
const mapTableSession = (x: RawTableSession): TableSession => ({ id: Number(x.id), status: String(x.status ?? ""), guestsCount: Number(x.guests_count ?? x.guest_count ?? 1), orderMode: x.order_mode === "per_person" ? "per_person" : "table", primaryOrder: typeof x.primary_order === "number" || typeof x.primary_order === "string" ? Number(x.primary_order) : typeof x.order_id === "number" || typeof x.order_id === "string" ? Number(x.order_id) : null, tableIds: Array.isArray(x.table_ids) ? x.table_ids.map(Number) : (x.table_id ? [Number(x.table_id)] : []), guests: (Array.isArray(x.guests) ? x.guests : []).map((g) => mapTableGuest(g as RawTableGuest)), openedAt: x.opened_at ? String(x.opened_at) : null, totalCached: Number(x.total_cached ?? 0), groupNumber: x.group_number == null ? null : Number(x.group_number) });

export const getDiningAreas = async (): Promise<DiningArea[]> => {
  const response = await request('/orders/tables/areas/');
  const data = await handleJson<RawDiningArea[]>(response);
  return data.map(mapDiningArea);
};
export const createTableArea = async (payload: { name: string; sortOrder?: number; isActive?: boolean; x?:number; y?:number; width?:number; height?:number; color?:string; operationalZoom?:number; operationalOffsetX?:number; operationalOffsetY?:number }): Promise<DiningArea> => {
  const response = await request('/orders/tables/areas/', { method: 'POST', body: JSON.stringify({ name: payload.name, sort_order: payload.sortOrder ?? 0, is_active: payload.isActive ?? true, x: payload.x ?? 0, y: payload.y ?? 0, width: payload.width ?? 320, height: payload.height ?? 220, color: payload.color ?? '', operational_zoom: payload.operationalZoom ?? 1, operational_offset_x: payload.operationalOffsetX ?? 0, operational_offset_y: payload.operationalOffsetY ?? 0 }) });
  return mapDiningArea(await handleJson<RawDiningArea>(response));
};
export const updateTableArea = async (id: number, payload: Partial<{ name: string; sortOrder: number; isActive: boolean; x:number; y:number; width:number; height:number; color:string; operationalZoom:number; operationalOffsetX:number; operationalOffsetY:number }>): Promise<DiningArea> => {
  const response = await request(`/orders/tables/areas/${id}/`, { method: 'PATCH', body: JSON.stringify({ ...(payload.name !== undefined ? { name: payload.name } : {}), ...(payload.sortOrder !== undefined ? { sort_order: payload.sortOrder } : {}), ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {}), ...(payload.x !== undefined ? { x: payload.x } : {}), ...(payload.y !== undefined ? { y: payload.y } : {}), ...(payload.width !== undefined ? { width: payload.width } : {}), ...(payload.height !== undefined ? { height: payload.height } : {}), ...(payload.color !== undefined ? { color: payload.color } : {}), ...(payload.operationalZoom !== undefined ? { operational_zoom: payload.operationalZoom } : {}), ...(payload.operationalOffsetX !== undefined ? { operational_offset_x: payload.operationalOffsetX } : {}), ...(payload.operationalOffsetY !== undefined ? { operational_offset_y: payload.operationalOffsetY } : {}) }) });
  return mapDiningArea(await handleJson<RawDiningArea>(response));
};
export const deleteTableArea = async (id: number): Promise<{ detail: string }> => {
  const response = await request(`/orders/tables/areas/${id}/`, { method: 'DELETE' });
  return handleJson<{ detail: string }>(response);
};
export const getRestaurantTables = async (): Promise<RestaurantTable[]> => {
  const response = await request('/orders/tables/');
  const data = await handleJson<RawRestaurantTable[]>(response);
  return data.map(mapRestaurantTable);
};
export const createRestaurantTable = async (payload: { area: number; name: string; number?: number; capacity?: number; shape?: RestaurantTable['shape']; x?: number; y?: number; width?: number; height?: number; rotation?: number; color?: string; isActive?: boolean; sortOrder?: number; }): Promise<RestaurantTable> => {
  const response = await request('/orders/tables/', { method: 'POST', body: JSON.stringify({ area: payload.area, name: payload.name, number: payload.number ?? 1, capacity: payload.capacity ?? 4, shape: payload.shape ?? 'round', x: payload.x ?? 0, y: payload.y ?? 0, width: payload.width ?? 110, height: payload.height ?? 110, rotation: payload.rotation ?? 0, color: payload.color ?? '', is_active: payload.isActive ?? true, sort_order: payload.sortOrder ?? 0 }) });
  return mapRestaurantTable(await handleJson<RawRestaurantTable>(response));
};
export const updateRestaurantTable = async (id: number, payload: Partial<{ area: number; name: string; number: number; capacity: number; shape: RestaurantTable['shape']; x: number; y: number; width: number; height: number; rotation: number; color: string; isActive: boolean; sortOrder: number; }>): Promise<RestaurantTable> => {
  const response = await request(`/orders/tables/${id}/`, { method: 'PATCH', body: JSON.stringify({ ...(payload.area !== undefined ? { area: payload.area } : {}), ...(payload.name !== undefined ? { name: payload.name } : {}), ...(payload.number !== undefined ? { number: payload.number } : {}), ...(payload.capacity !== undefined ? { capacity: payload.capacity } : {}), ...(payload.shape !== undefined ? { shape: payload.shape } : {}), ...(payload.x !== undefined ? { x: payload.x } : {}), ...(payload.y !== undefined ? { y: payload.y } : {}), ...(payload.width !== undefined ? { width: payload.width } : {}), ...(payload.height !== undefined ? { height: payload.height } : {}), ...(payload.rotation !== undefined ? { rotation: payload.rotation } : {}), ...(payload.color !== undefined ? { color: payload.color } : {}), ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {}), ...(payload.sortOrder !== undefined ? { sort_order: payload.sortOrder } : {}) }) });
  return mapRestaurantTable(await handleJson<RawRestaurantTable>(response));
};
export const deleteRestaurantTable = async (id: number): Promise<{ detail: string }> => {
  const response = await request(`/orders/tables/${id}/`, { method: 'DELETE' });
  if (response.status === 204) return { detail: 'Mesa eliminada.' };
  return handleJson<{ detail: string }>(response);
};
export const getTableLayout = async (): Promise<TableLayout> => {
  const response = await request('/orders/tables/layout/');
  const data = await handleJson<{ areas?: RawDiningArea[]; tables?: RawRestaurantTable[]; sessions?: RawTableSession[] }>(response);
  return { areas: (data.areas ?? []).map(mapDiningArea), tables: (data.tables ?? []).map(mapRestaurantTable), sessions: (data.sessions ?? []).map(mapTableSession) };
};
const mapTableKitchenItem = (item: RawTableKitchenItem): TableKitchenItem => ({
  id: Number(item.id),
  productName: String(item.product_name ?? item.productName ?? ""),
  quantity: Number(item.quantity ?? 0),
  assignedName: item.assigned_name ? String(item.assigned_name) : undefined,
  guestNumber: item.guest_number == null ? item.table_guest_seat_number == null ? null : Number(item.table_guest_seat_number) : Number(item.guest_number),
  guestLabel: item.guest_label ? String(item.guest_label) : item.table_guest_label ? String(item.table_guest_label) : undefined,
  tableGuestId: item.table_guest_id == null ? null : Number(item.table_guest_id),
  tableGuestLabel: item.table_guest_label ? String(item.table_guest_label) : undefined,
  tableGuestSeatNumber: item.table_guest_seat_number == null ? null : Number(item.table_guest_seat_number),
  kitchenStatus: normalizeKitchenStatus(item.kitchen_status),
  kitchenStatusLabel: item.kitchen_status_label ? String(item.kitchen_status_label) : undefined,
  kitchenSentAt: item.kitchen_sent_at ? String(item.kitchen_sent_at) : null,
  kitchenReadyAt: item.kitchen_ready_at ? String(item.kitchen_ready_at) : null,
  kitchenDeliveredAt: item.kitchen_delivered_at ? String(item.kitchen_delivered_at) : null,
  kitchenCompletedAt: item.kitchen_completed_at ? String(item.kitchen_completed_at) : item.kitchen_ready_at ? String(item.kitchen_ready_at) : null,
  kitchenServedAt: item.kitchen_served_at ? String(item.kitchen_served_at) : item.kitchen_delivered_at ? String(item.kitchen_delivered_at) : null,
  isPendingKitchen: Boolean(item.is_pending_kitchen ?? normalizeKitchenStatus(item.kitchen_status) === "pending"),
  isInKitchen: Boolean(item.is_in_kitchen ?? item.kitchen_status === "sent"),
  isCompleted: Boolean(item.is_completed ?? item.kitchen_status === "ready"),
  isServed: Boolean(item.is_served ?? item.kitchen_status === "delivered"),
  modifiers: Array.isArray(item.modifiers) ? item.modifiers.map(String) : [],
  lineTotal: Number(item.line_total ?? 0),
});
const mapTableKitchenSession = (session: RawTableKitchenSession): TableKitchenSessionSummary => ({
  sessionId: Number(session.session_id),
  orderId: typeof session.order_id === "number" || typeof session.order_id === "string" ? Number(session.order_id) : null,
  status: String(session.status ?? ""),
  tables: (Array.isArray(session.tables) ? session.tables : []).map(String),
  tableLabel: String(session.table_label ?? ""),
  guestsCount: Number(session.guests_count ?? 1),
  orderMode: session.order_mode === "per_person" ? "per_person" : "table",
  total: Number(session.total ?? 0),
  remaining: Number(session.remaining ?? 0),
  items: (Array.isArray(session.items) ? session.items : []).map((item) => mapTableKitchenItem(item as RawTableKitchenItem)),
  people: (Array.isArray(session.people) ? session.people : []).map((rawPerson) => {
    const person = rawPerson as RawTableKitchenPerson;
    return {
    label: String(person.label ?? ""),
    total: Number(person.total ?? 0),
    items: (Array.isArray(person.items) ? person.items : []).map((item) => mapTableKitchenItem(item as RawTableKitchenItem)),
    };
  }),
});
const mapTableReadySummary = (row: RawTableReadySummary): TableReadySummary => ({
  tableId: row.table_id == null ? null : Number(row.table_id),
  tableIds: (Array.isArray(row.table_ids) ? row.table_ids : []).map(Number),
  tableName: String(row.table_name ?? ""),
  sessionId: Number(row.session_id),
  orderId: typeof row.order_id === "number" || typeof row.order_id === "string" ? Number(row.order_id) : null,
  readyCount: Number(row.ready_count ?? 0),
  groupLabel: row.group_label == null ? null : String(row.group_label),
  items: (Array.isArray(row.items) ? row.items : []).map((item) => mapTableKitchenItem(item as RawTableKitchenItem)),
});
export const getTableKitchenSummary = async (): Promise<TableKitchenSessionSummary[]> => {
  const response = await request('/orders/tables/kitchen-summary/');
  const data = await handleJson<{ sessions?: RawTableKitchenSession[] }>(response);
  return (data.sessions ?? []).map(mapTableKitchenSession);
};
export const getTableReadySummary = async (): Promise<{ tables: TableReadySummary[]; totalReady: number }> => {
  const response = await request('/orders/tables/ready-summary/');
  const data = await handleJson<{ tables?: RawTableReadySummary[]; total_ready?: unknown }>(response);
  return { tables: (data.tables ?? []).map(mapTableReadySummary), totalReady: Number(data.total_ready ?? 0) };
};
export const saveTableLayout = async (payload: { tables: Array<{ id: number; x: number; y: number; width: number; height: number; rotation: number }> }): Promise<{ detail: string }> => {
  const response = await request('/orders/tables/layout/', { method: 'PATCH', body: JSON.stringify(payload) });
  return handleJson<{ detail: string }>(response);
};
export const getTableSessions = async (): Promise<TableSession[]> => {
  const response = await request('/orders/tables/sessions/');
  const data = await handleJson<RawTableSession[]>(response);
  return data.map(mapTableSession);
};
export const createTableSession = async (payload: { tableIds: number[]; guestsCount: number; orderMode: 'table'|'per_person'; notes?: string; }): Promise<TableSession> => {
  const response = await request('/orders/tables/sessions/', { method: 'POST', body: JSON.stringify({ table_ids: payload.tableIds, guests_count: payload.guestsCount, order_mode: payload.orderMode, notes: payload.notes ?? '' }) });
  if (response.status === 409) {
    const conflict = await response.json().catch(() => null);
    if (conflict?.code === "table_already_has_active_session" && conflict.session) {
      return mapTableSession(conflict.session);
    }
    throw new ApiRequestError(conflict?.message || conflict?.detail || "La mesa ya tiene una orden activa.", {
      code: conflict?.code,
      status: response.status,
      payload: conflict,
    });
  }
  const x = await handleJson<{ session?: RawTableSession } & RawTableSession>(response);
  return mapTableSession(x.session ?? x);
};
export const mergeTableSessionTables = async (sessionId: number, tableIds: number[]): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/merge/`, { method: 'POST', body: JSON.stringify({ table_ids: tableIds }) });
  const data = await handleJson<{ session?: RawTableSession } & RawTableSession>(response);
  return mapTableSession(data.session ?? data);
};
export const splitTableSessionTable = async (sessionId: number, tableId: number): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/split-table/`, { method: 'POST', body: JSON.stringify({ table_id: tableId }) });
  const data = await handleJson<{ session?: RawTableSession } & RawTableSession>(response);
  return mapTableSession(data.session ?? data);
};
export const sendTableSessionToKitchen = async (sessionId: number, payload?: { scope?: "guest" | "table"; guestId?: number | null; guestNumber?: number | null }): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/send-to-kitchen/`, {
    method: 'POST',
    body: JSON.stringify({
      scope: payload?.scope ?? "table",
      guest_id: payload?.guestId ?? null,
      guest_number: payload?.guestNumber ?? null,
    }),
  });
  const data = await handleJson<({ session?: RawTableSession; sent_count?: unknown; saved_count?: unknown; detail?: unknown; order?: unknown; summary?: unknown } & RawTableSession)>(response);
  return { ...mapTableSession(data.session ?? data), sentCount: Number(data.sent_count ?? 0), savedCount: Number(data.saved_count ?? 0), detail: data.detail ? String(data.detail) : undefined };
};
export const renameTableSessionGuest = async (sessionId: number, guestNumber: number, name: string): Promise<{ detail?: string; guest: TableGuest; session: TableSession }> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/guests/${guestNumber}/rename/`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
  const data = await handleJson<{ detail?: unknown; guest?: RawTableGuest; session?: RawTableSession }>(response);
  const session = mapTableSession(data.session ?? {});
  const guest = data.guest ? mapTableGuest(data.guest) : session.guests.find((row) => row.seatNumber === guestNumber);
  if (!guest) {
    throw new ApiRequestError("No se pudo actualizar la persona.", { status: response.status, payload: data });
  }
  return {
    detail: data.detail ? String(data.detail) : undefined,
    guest,
    session,
  };
};
export const forceReleaseTableSession = async (sessionId: number, payload: { reason: string; authorizationPin?: string }): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/force-release/`, { method: 'POST', body: JSON.stringify({ reason: payload.reason, authorization_pin: payload.authorizationPin ?? "" }) });
  const data = await handleJson<{ session?: RawTableSession; detail?: unknown } & RawTableSession>(response);
  return { ...mapTableSession(data.session ?? data), detail: data.detail ? String(data.detail) : undefined };
};
export const markTableKitchenItemReady = async (itemId: number): Promise<TableKitchenItem> => {
  const response = await request(`/kitchen/items/${itemId}/complete/`, { method: 'POST' });
  const data = await handleJson<{ item?: RawTableKitchenItem } & RawTableKitchenItem>(response);
  return mapTableKitchenItem(data.item ?? data);
};
export const markTableKitchenItemDelivered = async (itemId: number): Promise<TableKitchenItem> => {
  const response = await request(`/kitchen/items/${itemId}/serve/`, { method: 'POST' });
  const data = await handleJson<{ item?: RawTableKitchenItem } & RawTableKitchenItem>(response);
  return mapTableKitchenItem(data.item ?? data);
};
export const serveTableSessionReadyItems = async (sessionId: number, itemIds?: number[]): Promise<{ servedCount: number; summary?: TableReadySummary; session?: TableSession; detail?: string }> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/serve-ready/`, {
    method: 'POST',
    body: JSON.stringify({ item_ids: itemIds ?? [] }),
  });
  const data = await handleJson<{ served_count?: unknown; summary?: RawTableReadySummary; session?: RawTableSession; detail?: unknown }>(response);
  return {
    servedCount: Number(data.served_count ?? 0),
    summary: data.summary ? mapTableReadySummary(data.summary) : undefined,
    session: data.session ? mapTableSession(data.session) : undefined,
    detail: data.detail ? String(data.detail) : undefined,
  };
};
export const moveTableSessionTable = async (sessionId: number, payload: { targetTableId: number; sourceTableId?: number | null }): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/move-table/`, { method: 'POST', body: JSON.stringify({ target_table_id: payload.targetTableId, source_table_id: payload.sourceTableId ?? null }) });
  const data = await handleJson<{ session?: RawTableSession } & RawTableSession>(response);
  return mapTableSession(data.session ?? data);
};
export const releaseTableSession = async (sessionId: number): Promise<TableSession> => {
  const response = await request(`/orders/tables/sessions/${sessionId}/release/`, { method: 'POST' });
  const data = await handleJson<{ session?: RawTableSession } & RawTableSession>(response);
  return mapTableSession(data.session ?? data);
};
