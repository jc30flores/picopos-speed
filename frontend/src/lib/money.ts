export const toNumber = (value: unknown): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const normalized = value.replace(/[$,\s]/g, "");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export const formatMoney = (value: number): string => {
  const safe = Number.isFinite(value) ? value : 0;
  return `$${safe.toFixed(2)}`;
};

export const calculateCartTotals = (
  items: Array<{ price: number; quantity: number }>,
  taxRate: number
) => {
  const safeItems = Array.isArray(items) ? items : [];
  const safeTax = Number.isFinite(taxRate) ? taxRate : 0;
  const total = safeItems.reduce((sum, item) => sum + toNumber(item.price) * toNumber(item.quantity), 0);
  const subtotal = safeTax >= 0 ? total / (1 + safeTax) : total;
  const tax = total - subtotal;
  return {
    subtotal,
    tax,
    total,
  };
};
