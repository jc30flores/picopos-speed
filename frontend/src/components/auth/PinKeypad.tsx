import { useCallback, useEffect, useRef, type PointerEvent } from "react";
import { Button } from "@/components/ui/button";

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
  const valueRef = useRef(value);
  const lastPointerPressRef = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

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
    if (key === "C") commitValue("");
    else if (key === "⌫") commitValue(valueRef.current.slice(0, -1));
    else appendDigit(key);
  }, [appendDigit, commitValue, disabled]);

  const handlePointerDown = useCallback((event: PointerEvent<HTMLButtonElement>, key: string) => {
    if (disabled) return;
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
            variant={key === "C" ? "secondary" : "outline"}
            aria-label={key === "C" ? "Limpiar PIN" : key === "⌫" ? "Borrar dígito" : `Número ${key}`}
            className="h-20 touch-manipulation select-none text-3xl font-semibold shadow-none transition-[background-color,border-color,color,transform] duration-75 active:translate-y-px active:scale-[0.99] sm:h-24 [-webkit-tap-highlight-color:transparent] [-webkit-user-select:none]"
            disabled={disabled}
            onPointerDown={(event) => handlePointerDown(event, key)}
            onClick={() => handleClick(key)}
          >
            {key}
          </Button>
        ))}
      </div>
    </div>
  );
};
