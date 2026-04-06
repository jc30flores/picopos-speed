import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const toOrderKey = <T,>(items: T[], getId: (item: T) => number | string): string =>
  items.map((item) => String(getId(item))).join("|");

export const useReorderableList = <T,>(items: T[], getId: (item: T) => number | string) => {
  const [originalItems, setOriginalItems] = useState<T[]>(items);
  const [currentItems, setCurrentItems] = useState<T[]>(items);
  const lastSyncedKeyRef = useRef(toOrderKey(items, getId));

  const isDirty = useMemo(
    () => toOrderKey(originalItems, getId) !== toOrderKey(currentItems, getId),
    [currentItems, getId, originalItems]
  );

  useEffect(() => {
    const incomingKey = toOrderKey(items, getId);
    if (incomingKey === lastSyncedKeyRef.current) return;
    if (isDirty) return;
    lastSyncedKeyRef.current = incomingKey;
    setOriginalItems(items);
    setCurrentItems(items);
  }, [getId, isDirty, items]);

  const moveById = useCallback(
    (activeId: number | string, targetId: number | string) => {
      setCurrentItems((prev) => {
        if (activeId === targetId) return prev;
        const next = [...prev];
        const from = next.findIndex((item) => String(getId(item)) === String(activeId));
        const to = next.findIndex((item) => String(getId(item)) === String(targetId));
        if (from < 0 || to < 0) return prev;
        const [moved] = next.splice(from, 1);
        next.splice(to, 0, moved);
        return next;
      });
    },
    [getId]
  );

  const reset = useCallback(() => {
    setCurrentItems(originalItems);
  }, [originalItems]);

  const markSaved = useCallback(() => {
    setOriginalItems(currentItems);
    lastSyncedKeyRef.current = toOrderKey(currentItems, getId);
  }, [currentItems, getId]);

  return {
    currentItems,
    setCurrentItems,
    isDirty,
    moveById,
    reset,
    markSaved,
  };
};
