import type { Discount, Product } from "@/lib/api";

export type CartPricingItem = {
  productId: number | null;
  quantity: number;
  unitTotal: number;
};

export type ServiceTypeLike = { key: string; disposablesEnabled?: boolean };

export type AppliedDiscountLine = {
  id: number;
  name: string;
  amount: number;
  source: "manual" | "automatic";
};

const getEligibleLineTotalForDiscount = (item: CartPricingItem, discount: Discount, products: Product[]): number => {
  if (discount.appliesTo === "order") return item.unitTotal * item.quantity;
  if (!item.productId) return 0;
  const product = products.find((candidate) => candidate.id === item.productId);
  if (!product) return 0;
  if (discount.appliesTo === "products") {
    return (discount.targetProductIds ?? []).includes(product.id) ? item.unitTotal * item.quantity : 0;
  }
  if (discount.appliesTo === "categories") {
    return (discount.targetCategoryIds ?? []).includes(product.categoryId) ? item.unitTotal * item.quantity : 0;
  }
  return 0;
};

const getEligibleQuantityForDiscount = (item: CartPricingItem, discount: Discount, products: Product[]): number =>
  getEligibleLineTotalForDiscount(item, discount, products) > 0 ? item.quantity : 0;

const getOrderDisposableTotal = (
  items: CartPricingItem[],
  products: Product[],
  serviceType: string,
  serviceTypes: ServiceTypeLike[]
) =>
  items.reduce((sum, item) => {
    if (!item.productId) return sum;
    const product = products.find((candidate) => candidate.id === item.productId);
    if (!product) return sum;
    const selectedOrderType = serviceTypes.find((type) => type.key === serviceType);
    const fee = Number(product.disposableFee ?? 0);
    const allowedServiceTypes = product.disposableApplyTo ?? [];
    const appliesByType = allowedServiceTypes.length === 0 || allowedServiceTypes.includes(serviceType);
    if (fee <= 0 || selectedOrderType?.disposablesEnabled !== true || !appliesByType) return sum;
    return sum + fee * item.quantity;
  }, 0);

const getDiscountAmount = (items: CartPricingItem[], discount: Discount, products: Product[]): number => {
  const eligible = items.reduce((sum, item) => sum + getEligibleLineTotalForDiscount(item, discount, products), 0);
  if (eligible <= 0) return 0;
  if (discount.type === "percent") return Math.min(eligible, (eligible * discount.value) / 100);
  if (discount.type === "fixed") {
    const units = discount.appliesTo === "order" ? 1 : items.reduce((sum, item) => sum + getEligibleQuantityForDiscount(item, discount, products), 0);
    return Math.min(eligible, discount.value * Math.max(units, 1));
  }
  return 0;
};

export const calculatePosPricing = ({
  items,
  products,
  serviceType,
  serviceTypes,
  selectedDiscount,
  availableDiscounts,
}: {
  items: CartPricingItem[];
  products: Product[];
  serviceType: string;
  serviceTypes: ServiceTypeLike[];
  selectedDiscount: Discount | null;
  availableDiscounts: Discount[];
}) => {
  const itemsGross = items.reduce((sum, item) => sum + item.unitTotal * item.quantity, 0);
  const disposableTotal = getOrderDisposableTotal(items, products, serviceType, serviceTypes);

  const discountLines: AppliedDiscountLine[] = [];
  let discountTotal = 0;

  if (selectedDiscount) {
    const amount = getDiscountAmount(items, selectedDiscount, products);
    if (amount > 0) {
      discountLines.push({ id: selectedDiscount.id, name: selectedDiscount.name, amount, source: "manual" });
      discountTotal += amount;
    }
  }

  const autoDiscounts = (availableDiscounts ?? [])
    // Auto discounts are only valid when backend confirms conditions are currently met.
    .filter(
      (discount) =>
        discount.autoApply &&
        discount.availableNow === true &&
        discount.id !== selectedDiscount?.id
    )
    .sort((a, b) => (a.priority ?? 100) - (b.priority ?? 100));

  for (const autoDiscount of autoDiscounts) {
    const amount = getDiscountAmount(items, autoDiscount, products);
    if (amount <= 0) continue;
    discountLines.push({ id: autoDiscount.id, name: autoDiscount.name, amount, source: "automatic" });
    discountTotal += amount;
    if (!autoDiscount.stackable) break;
  }

  const total = Math.max(itemsGross - discountTotal, 0) + disposableTotal;

  return {
    itemsGross,
    subtotal: itemsGross,
    disposableTotal,
    discountTotal,
    discountLines,
    total,
  };
};
