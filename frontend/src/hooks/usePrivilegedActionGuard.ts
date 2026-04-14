import { useState } from "react";
import { useAuth } from "@/context/useAuth";

export const usePrivilegedActionGuard = () => {
  const { user } = useAuth();
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const needsPrivilege = user?.role === "cashier";
  const requirePrivilege = (actionKey: string, action: () => void) => {
    if (!needsPrivilege) {
      action();
      return;
    }
    setPendingAction(actionKey);
  };

  const onPinSuccess = (handlers: Record<string, (pin?: string) => void>, pin?: string) => {
    if (!pendingAction) return;
    const handler = handlers[pendingAction];
    setPendingAction(null);
    handler?.(pin);
  };

  return {
    pendingAction,
    setPendingAction,
    requirePrivilege,
    onPinSuccess,
  };
};
