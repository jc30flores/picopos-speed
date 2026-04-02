export type EffectivePriceDisplay = {
  showOfferBadge: boolean;
  originalPrice: number;
  finalPrice: number;
  label: string;
};

export type EffectivePriceResult = {
  basePrice: number;
  effectivePrice: number;
  appliedRule: { name?: string | null; id?: number | null } | null;
  display: EffectivePriceDisplay;
};

export const resolveEffectiveUnitPrice = (
  product: {
    price: number;
    effectivePrice?: number;
    appliedSpecialPriceRuleId?: number | null;
    appliedSpecialPriceRuleName?: string | null;
  },
  _selectedOrderType: string,
  _now: Date,
  _timezone: string
): EffectivePriceResult => {
  const basePrice = Number(product.price || 0);
  const effectivePrice = Number(product.effectivePrice ?? basePrice);
  const showOfferBadge = effectivePrice < basePrice;
  return {
    basePrice,
    effectivePrice,
    appliedRule: product.appliedSpecialPriceRuleId
      ? { id: product.appliedSpecialPriceRuleId, name: product.appliedSpecialPriceRuleName ?? null }
      : null,
    display: {
      showOfferBadge,
      originalPrice: basePrice,
      finalPrice: effectivePrice,
      label: showOfferBadge ? "OFERTA" : "PRECIO NORMAL",
    },
  };
};
