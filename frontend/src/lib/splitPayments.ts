export type SplitPart = {
  id: string;
  amount: number;
  locked?: boolean;
};

const roundMoney = (value: number): number => Math.round(value * 100) / 100;

export const splitEqually = (total: number, partCount: number): SplitPart[] => {
  const safeCount = Math.max(1, Math.min(12, Math.floor(partCount || 1)));
  const totalCents = Math.max(0, Math.round(total * 100));
  const base = Math.floor(totalCents / safeCount);
  const remainder = totalCents % safeCount;

  return Array.from({ length: safeCount }).map((_, idx) => ({
    id: `part-${idx + 1}`,
    amount: (base + (idx < remainder ? 1 : 0)) / 100,
    locked: false,
  }));
};

export const recalcUnlockedParts = (parts: SplitPart[], targetTotal: number): SplitPart[] => {
  if (!parts.length) return [];

  const roundedTarget = roundMoney(targetTotal);
  const lockedTotal = roundMoney(
    parts.filter((part) => part.locked).reduce((sum, part) => sum + roundMoney(part.amount), 0)
  );
  const unlockedIndices = parts
    .map((part, index) => ({ part, index }))
    .filter(({ part }) => !part.locked)
    .map(({ index }) => index);

  if (!unlockedIndices.length) {
    return parts;
  }

  const available = Math.max(0, roundMoney(roundedTarget - lockedTotal));
  const equalized = splitEqually(available, unlockedIndices.length);

  return parts.map((part, index) => {
    const unlockedPosition = unlockedIndices.indexOf(index);
    if (unlockedPosition === -1) {
      return { ...part, amount: roundMoney(part.amount) };
    }
    return {
      ...part,
      amount: equalized[unlockedPosition]?.amount ?? 0,
    };
  });
};

export const validateParts = (parts: SplitPart[], targetTotal: number): string | null => {
  if (!parts.length) return "Agrega al menos una parte";
  if (parts.some((part) => part.amount <= 0)) return "Cada parte debe ser mayor a 0";
  const partsTotal = roundMoney(parts.reduce((sum, part) => sum + roundMoney(part.amount), 0));
  const roundedTarget = roundMoney(targetTotal);
  if (Math.abs(partsTotal - roundedTarget) > 0.01) {
    return `Las partes deben sumar ${roundedTarget.toFixed(2)}`;
  }
  return null;
};
