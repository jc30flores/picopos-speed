export const toNumber = (value: unknown): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const normalized = value.replace(/[$,\s]/g, "");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export const toCents = (value: unknown): number => {
  if (typeof value === "number" && Number.isFinite(value)) return Math.round(value * 100);
  const raw = String(value ?? "").replace(/[$,\s]/g, "");
  if (!raw) return 0;
  const sign = raw.startsWith("-") ? -1 : 1;
  const unsigned = raw.replace(/^[+-]/, "");
  const [whole, fraction = ""] = unsigned.split(".");
  const wholeDigits = whole.replace(/\D/g, "") || "0";
  const fractionDigits = (fraction.replace(/\D/g, "") + "000").slice(0, 3);
  const cents = Number(wholeDigits) * 100 + Number(fractionDigits.slice(0, 2));
  const third = Number(fractionDigits[2] || "0");
  return sign * (cents + (third >= 5 ? 1 : 0));
};

export const fromCents = (cents: number): number => {
  const safe = Number.isFinite(cents) ? cents : 0;
  return safe / 100;
};

export const addCents = (...values: Array<number>): number => values.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);

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
