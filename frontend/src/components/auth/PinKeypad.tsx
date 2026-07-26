import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PinKeypadProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  maxLength?: number;
  className?: string;
}

export const PinKeypad = ({
  value,
  onChange,
  disabled = false,
  maxLength = 6,
  className = "",
}: PinKeypadProps) => {
  const [pressedKey, setPressedKey] = useState<string | null>(null);
  const valueRef = useRef(value);
  const lastPointerPressRef = useRef<{ key: string; at: number } | null>(null);
  const clearPressedTimerRef = useRef<number | null>(null);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const clearPressedState = useCallback(() => {
    if (clearPressedTimerRef.current != null) {
      window.clearTimeout(clearPressedTimerRef.current);
      clearPressedTimerRef.current = null;
    }
    setPressedKey(null);
  }, []);

  const schedulePressedCleanup = useCallback(() => {
    if (clearPressedTimerRef.current != null) {
      window.clearTimeout(clearPressedTimerRef.current);
    }
    clearPressedTimerRef.current = window.setTimeout(() => {
      clearPressedTimerRef.current = null;
      setPressedKey(null);
    }, 80);
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible") clearPressedState();
    };
    window.addEventListener("blur", clearPressedState);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("blur", clearPressedState);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      clearPressedState();
    };
  }, [clearPressedState]);

  useEffect(() => {
    if (disabled) clearPressedState();
  }, [clearPressedState, disabled]);

  const commitValue = useCallback((nextValue: string) => {
    valueRef.current = nextValue;
    onChange(nextValue);
  }, [onChange]);

  const appendDigit = useCallback((digit: string) => {
    if (disabled || valueRef.current.length >= maxLength) return;
    commitValue(`${valueRef.current}${digit}`.slice(0, maxLength));
  }, [commitValue, disabled, maxLength]);

  const pressKey = useCallback((key: string) => {
    if (disabled) return;
    setPressedKey(key);
    schedulePressedCleanup();
    if (key === "C") commitValue("");
    else if (key === "⌫") commitValue(valueRef.current.slice(0, -1));
    else appendDigit(key);
  }, [appendDigit, commitValue, disabled, schedulePressedCleanup]);

  const handlePointerDown = useCallback((event: PointerEvent<HTMLButtonElement>, key: string) => {
    if (disabled) return;
    if (!event.isPrimary) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.preventDefault();
    lastPointerPressRef.current = { key, at: performance.now() };
    pressKey(key);
  }, [disabled, pressKey]);

  const handleClick = useCallback((key: string) => {
    const lastPointerPress = lastPointerPressRef.current;
    if (lastPointerPress?.key === key && performance.now() - lastPointerPress.at < 500) return;
    pressKey(key);
  }, [pressKey]);

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="grid grid-cols-3 gap-3">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"].map((key) => (
          <Button
            key={key}
            type="button"
            variant="outline"
            aria-label={key === "C" ? "Limpiar PIN" : key === "⌫" ? "Borrar dígito" : `Número ${key}`}
            data-pressed={pressedKey === key ? "true" : "false"}
            className={cn(
              "pin-key h-20 text-3xl font-semibold focus:bg-background focus:text-foreground sm:h-24",
              pressedKey === key && "border-secondary bg-secondary/15 text-foreground"
            )}
            disabled={disabled}
            onPointerDown={(event) => handlePointerDown(event, key)}
            onPointerUp={schedulePressedCleanup}
            onPointerCancel={clearPressedState}
            onPointerLeave={clearPressedState}
            onClick={() => handleClick(key)}
          >
            {key}
          </Button>
        ))}
      </div>
    </div>
  );
};
