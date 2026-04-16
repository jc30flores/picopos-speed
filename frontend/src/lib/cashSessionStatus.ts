import type { CashSessionSnapshot } from "@/lib/api";

export type CashSessionStatus = {
  hasOpenCashSession: boolean;
  canOpenCash: boolean;
  canCloseCash: boolean;
};

export const getCashSessionStatus = (snapshot: CashSessionSnapshot | null | undefined): CashSessionStatus => {
  const hasOpenCashSession = Boolean(snapshot?.hasOpenCashSession ?? snapshot?.open);
  return {
    hasOpenCashSession,
    canOpenCash: Boolean(snapshot?.canOpenCash ?? !hasOpenCashSession),
    canCloseCash: Boolean(snapshot?.canCloseCash ?? hasOpenCashSession),
  };
};
