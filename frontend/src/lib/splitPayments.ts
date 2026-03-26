export type SplitPart = {
  id: string;
  amountCents: number;
  locked: boolean;
  isPaid?: boolean;
};

export type PartsValidation = {
  isValid: boolean;
  error: string | null;
  totalCents: number;
  partsSumCents: number;
  diffCents: number;
};

const clampCents = (value: number): number => Math.max(0, Math.round(value || 0));

export const splitEvenly = (totalCents: number, n: number): SplitPart[] => {
  const safeTotal = clampCents(totalCents);
  const safeCount = Math.max(1, Math.min(20, Math.floor(n || 1)));
  const base = Math.floor(safeTotal / safeCount);
  const rem = safeTotal % safeCount;

  return Array.from({ length: safeCount }, (_, index) => ({
    id: `part-${index + 1}`,
    amountCents: base + (index < rem ? 1 : 0),
    locked: false,
    isPaid: false,
  }));
};

export const recalcParts = (totalCents: number, parts: SplitPart[]): SplitPart[] => {
  if (!parts.length) return splitEvenly(totalCents, 1);

  const safeTotal = clampCents(totalCents);
  const lockedIndices = parts
    .map((part, index) => ({ part, index }))
    .filter(({ part }) => part.locked || part.isPaid)
    .map(({ index }) => index);
  const unlockedIndices = parts
    .map((part, index) => ({ part, index }))
    .filter(({ part }) => !(part.locked || part.isPaid))
    .map(({ index }) => index);

  const lockedSum = lockedIndices.reduce((sum, index) => sum + clampCents(parts[index].amountCents), 0);
  const available = Math.max(0, safeTotal - lockedSum);

  if (!unlockedIndices.length) {
    return parts.map((part) => ({ ...part, amountCents: clampCents(part.amountCents) }));
  }

  const base = Math.floor(available / unlockedIndices.length);
  const rem = available % unlockedIndices.length;

  let unlockedCursor = 0;
  return parts.map((part, index) => {
    if (lockedIndices.includes(index)) {
      return { ...part, amountCents: clampCents(part.amountCents) };
    }
    const amountCents = base + (unlockedCursor < rem ? 1 : 0);
    unlockedCursor += 1;
    return {
      ...part,
      amountCents,
    };
  });
};

export const validateParts = (totalCents: number, parts: SplitPart[]): PartsValidation => {
  const safeTotal = clampCents(totalCents);
  if (!parts.length) {
    return {
      isValid: false,
      error: "Agrega al menos una parte",
      totalCents: safeTotal,
      partsSumCents: 0,
      diffCents: safeTotal,
    };
  }

  const lockedSum = parts
    .filter((part) => part.locked || part.isPaid)
    .reduce((sum, part) => sum + clampCents(part.amountCents), 0);
  const unlockedCount = parts.filter((part) => !(part.locked || part.isPaid)).length;
  const partsSumCents = parts.reduce((sum, part) => sum + clampCents(part.amountCents), 0);
  const diffCents = safeTotal - partsSumCents;

  if (lockedSum > safeTotal) {
    return {
      isValid: false,
      error: "Excede el total",
      totalCents: safeTotal,
      partsSumCents,
      diffCents,
    };
  }

  if (unlockedCount === 0 && lockedSum !== safeTotal) {
    return {
      isValid: false,
      error: "Los montos no cuadran",
      totalCents: safeTotal,
      partsSumCents,
      diffCents,
    };
  }

  if (diffCents !== 0) {
    return {
      isValid: false,
      error: diffCents > 0 ? "Faltan montos por asignar" : "Los montos exceden el total",
      totalCents: safeTotal,
      partsSumCents,
      diffCents,
    };
  }

  return {
    isValid: true,
    error: null,
    totalCents: safeTotal,
    partsSumCents,
    diffCents,
  };
};
