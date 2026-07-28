import type { Discount, Product } from "@/lib/api";
import { fromCents, toCents } from "@/lib/money";

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

export type CartLineDiscount = {
  index: number;
  productId: number | null;
  discountId: number;
  discountName: string;
  discountType: Discount["type"];
  discountValue: number;
  amount: number;
  unitDiscount: number;
  lineTotalBefore: number;
  lineTotalAfter: number;
  source: "manual" | "automatic";
};

const getEligibleLineTotalCentsForDiscount = (item: CartPricingItem, discount: Discount, products: Product[]): number => {
  const lineTotalCents = toCents(item.unitTotal) * Math.max(0, Math.floor(item.quantity || 0));
  if (discount.appliesTo === "order") return lineTotalCents;
  if (!item.productId) return 0;
  const product = products.find((candidate) => candidate.id === item.productId);
  if (!product) return 0;
  if (discount.appliesTo === "products") {
    return (discount.targetProductIds ?? []).includes(product.id) ? lineTotalCents : 0;
  }
  if (discount.appliesTo === "categories") {
    return (discount.targetCategoryIds ?? []).includes(product.categoryId) ? lineTotalCents : 0;
  }
  return 0;
};

const getEligibleQuantityForDiscount = (item: CartPricingItem, discount: Discount, products: Product[]): number =>
  getEligibleLineTotalCentsForDiscount(item, discount, products) > 0 ? Math.max(0, Math.floor(item.quantity || 0)) : 0;

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

const getDiscountAmountCents = (items: CartPricingItem[], discount: Discount, products: Product[]): number => {
  const eligibleCents = items.reduce((sum, item) => sum + getEligibleLineTotalCentsForDiscount(item, discount, products), 0);
  if (eligibleCents <= 0) return 0;
  if (discount.type === "percent") return Math.min(eligibleCents, Math.round((eligibleCents * discount.value) / 100));
  if (discount.type === "fixed") {
    const units = discount.appliesTo === "order" ? 1 : items.reduce((sum, item) => sum + getEligibleQuantityForDiscount(item, discount, products), 0);
    return Math.min(eligibleCents, toCents(discount.value) * Math.max(units, 1));
  }
  return 0;
};

const allocateLineDiscounts = (
  items: CartPricingItem[],
  discount: Discount,
  products: Product[],
  source: "manual" | "automatic"
): { amountCents: number; lineDiscounts: CartLineDiscount[] } => {
  const lineDiscountCents = items.map(() => 0);
  const eligibleCentsByLine = items.map((item) => getEligibleLineTotalCentsForDiscount(item, discount, products));
  const totalEligibleCents = eligibleCentsByLine.reduce((sum, value) => sum + value, 0);
  if (totalEligibleCents <= 0) return { amountCents: 0, lineDiscounts: [] };

  if (discount.appliesTo === "order") {
    const amountCents = getDiscountAmountCents(items, discount, products);
    let allocated = 0;
    const allocations = eligibleCentsByLine.map((eligibleCents, index) => {
      const raw = (amountCents * eligibleCents) / totalEligibleCents;
      const cents = Math.floor(raw);
      allocated += cents;
      return { index, cents, remainder: raw - cents };
    });
    allocations
      .sort((a, b) => b.remainder - a.remainder || a.index - b.index)
      .slice(0, amountCents - allocated)
      .forEach((row) => {
        row.cents += 1;
      });
    allocations.forEach((row) => {
      lineDiscountCents[row.index] = row.cents;
    });
  } else {
    items.forEach((item, index) => {
      const eligibleCents = eligibleCentsByLine[index] ?? 0;
      if (eligibleCents <= 0) return;
      if (discount.type === "percent") {
        lineDiscountCents[index] = Math.min(eligibleCents, Math.round((eligibleCents * discount.value) / 100));
      } else if (discount.type === "fixed") {
        lineDiscountCents[index] = Math.min(eligibleCents, toCents(discount.value) * Math.max(1, Math.floor(item.quantity || 1)));
      }
    });
  }

  const lineDiscounts = lineDiscountCents
    .map((amountCents, index): CartLineDiscount | null => {
      if (amountCents <= 0) return null;
      const item = items[index];
      const quantity = Math.max(1, Math.floor(item.quantity || 1));
      const lineTotalBeforeCents = toCents(item.unitTotal) * quantity;
      return {
        index,
        productId: item.productId,
        discountId: discount.id,
        discountName: discount.name,
        discountType: discount.type,
        discountValue: discount.value,
        amount: fromCents(amountCents),
        unitDiscount: fromCents(Math.round(amountCents / quantity)),
        lineTotalBefore: fromCents(lineTotalBeforeCents),
        lineTotalAfter: fromCents(Math.max(lineTotalBeforeCents - amountCents, 0)),
        source,
      };
    })
    .filter((line): line is CartLineDiscount => Boolean(line));

  return {
    amountCents: lineDiscountCents.reduce((sum, value) => sum + value, 0),
    lineDiscounts,
  };
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
  const itemsGrossCents = items.reduce((sum, item) => sum + toCents(item.unitTotal) * Math.max(0, Math.floor(item.quantity || 0)), 0);
  const disposableTotalCents = toCents(getOrderDisposableTotal(items, products, serviceType, serviceTypes));

  const discountLines: AppliedDiscountLine[] = [];
  const lineDiscounts: CartLineDiscount[] = [];
  let discountTotalCents = 0;

  if (selectedDiscount) {
    const result = allocateLineDiscounts(items, selectedDiscount, products, "manual");
    if (result.amountCents > 0) {
      discountLines.push({ id: selectedDiscount.id, name: selectedDiscount.name, amount: fromCents(result.amountCents), source: "manual" });
      lineDiscounts.push(...result.lineDiscounts);
      discountTotalCents += result.amountCents;
    }
  }

  const autoDiscounts = selectedDiscount ? [] : (availableDiscounts ?? [])
    // Auto discounts are only valid when backend confirms conditions are currently met.
    .filter(
      (discount) =>
        discount.autoApply &&
        discount.availableNow === true
    )
    .sort((a, b) => (a.priority ?? 100) - (b.priority ?? 100) || a.id - b.id);

  const autoDiscount = autoDiscounts[0];
  if (autoDiscount) {
    const result = allocateLineDiscounts(items, autoDiscount, products, "automatic");
    if (result.amountCents > 0) {
      discountLines.push({ id: autoDiscount.id, name: autoDiscount.name, amount: fromCents(result.amountCents), source: "automatic" });
      lineDiscounts.push(...result.lineDiscounts);
      discountTotalCents += result.amountCents;
    }
  }

  const totalCents = Math.max(itemsGrossCents - discountTotalCents, 0) + disposableTotalCents;

  return {
    itemsGross: fromCents(itemsGrossCents),
    subtotal: fromCents(itemsGrossCents),
    disposableTotal: fromCents(disposableTotalCents),
    discountTotal: fromCents(discountTotalCents),
    discountLines,
    lineDiscounts,
    total: fromCents(totalCents),
  };
};
