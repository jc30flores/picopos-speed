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
  const appendDigit = (digit: string) => {
    if (disabled || value.length >= maxLength) return;
    onChange(`${value}${digit}`);
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="grid grid-cols-3 gap-2">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"].map((key) => (
          <Button
            key={key}
            type="button"
            variant={key === "C" ? "secondary" : "outline"}
            className="h-14 text-xl active:scale-[0.98]"
            disabled={disabled}
            onClick={() => {
              if (key === "C") onChange("");
              else if (key === "⌫") onChange(value.slice(0, -1));
              else appendDigit(key);
            }}
          >
            {key}
          </Button>
        ))}
      </div>
    </div>
  );
};
