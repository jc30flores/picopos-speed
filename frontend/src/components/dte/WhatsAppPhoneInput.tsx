import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatWhatsAppClientPhone, type WhatsAppCountry } from "@/lib/whatsappClientPhone";

type Props = {
  label: string;
  helpText?: string;
  country: WhatsAppCountry;
  onCountryChange: (country: WhatsAppCountry) => void;
  value: string;
  onValueChange: (value: string) => void;
  error?: string;
};

export function WhatsAppPhoneInput({
  label,
  helpText,
  country,
  onCountryChange,
  value,
  onValueChange,
  error,
}: Props) {
  return (
    <div className="space-y-2 rounded-md border p-3">
      <Label>{label}</Label>
      {helpText ? <p className="text-xs text-muted-foreground">{helpText}</p> : null}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[120px_minmax(0,1fr)]">
        <Select
          value={country}
          onValueChange={(raw) => onCountryChange(raw === "USA" ? "USA" : "ESA")}
        >
          <SelectTrigger className="h-11">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ESA">ESA (+503)</SelectItem>
            <SelectItem value="USA">USA (+1)</SelectItem>
          </SelectContent>
        </Select>
        <Input
          className="h-11"
          value={value}
          placeholder={country === "USA" ? "+1 (000) 0000-000" : "+503 0000-0000"}
          onChange={(event) => onValueChange(event.target.value)}
          onBlur={() => {
            const formatted = formatWhatsAppClientPhone(country, value);
            if (formatted !== value) onValueChange(formatted);
          }}
        />
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
