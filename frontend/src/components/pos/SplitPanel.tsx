import { useMemo, useState, type ReactNode } from "react";
import { Check, Minus, Plus, RotateCcw, SplitSquareHorizontal, Users, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/money";
import { recalcParts, SplitPart, splitEvenly, validateParts } from "@/lib/splitPayments";
import { toast } from "sonner";

type SplitPanelProps = {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  mode?: "none" | "person" | "equal";
  onModeChange?: (mode: "none" | "person" | "equal") => void;
  totalCents: number;
  parts: SplitPart[];
  onPartsChange: (parts: SplitPart[]) => void;
  activePartId: string | null;
  onActivePartIdChange: (partId: string | null) => void;
  canUsePersonMode?: boolean;
  personModeDisabledReason?: string;
  onPersonModeSelect?: () => void;
};

const MAX_PARTS = 20;
const QUICK_SPLITS = [2, 3, 4, 5];

const nextPartId = (): string => `part-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

export function SplitPanel({
  enabled,
  onEnabledChange,
  mode,
  onModeChange,
  totalCents,
  parts,
  onPartsChange,
  activePartId,
  onActivePartIdChange,
  canUsePersonMode = true,
  personModeDisabledReason = "Disponible solo para cuentas de mesa con personas.",
  onPersonModeSelect,
}: SplitPanelProps) {
  const [editingPartId, setEditingPartId] = useState<string | null>(null);
  const [editingRawValue, setEditingRawValue] = useState("");

  const safeParts = useMemo(
    () => (enabled ? (parts.length >= 2 ? parts : splitEvenly(totalCents, 2)) : splitEvenly(totalCents, 1)),
    [enabled, parts, totalCents]
  );
  const validation = useMemo(() => validateParts(totalCents, safeParts), [safeParts, totalCents]);
  const hasLocks = safeParts.some((part) => part.locked);
  const selectedMode = mode ?? (enabled ? "equal" : "none");

  const chooseFallbackActive = (list: SplitPart[]): string | null => {
    if (!list.length) return null;
    const unpaid = list.find((part) => !part.isPaid);
    return unpaid?.id ?? list[0]?.id ?? null;
  };

  const setPartCount = (count: number, resetLocks = false) => {
    const target = Math.max(2, Math.min(MAX_PARTS, Math.floor(count || 2)));
    const base = resetLocks
      ? splitEvenly(totalCents, target).map((part, index) => ({ ...part, id: `part-${index + 1}` }))
      : safeParts.map((part) => ({ ...part }));

    const resized = [...base];
    if (target > resized.length) {
      while (resized.length < target) {
        resized.push({ id: nextPartId(), amountCents: 0, locked: false, isPaid: false });
      }
    } else if (target < resized.length) {
      while (resized.length > target) {
        const removeIndex = [...resized]
          .map((part, index) => ({ part, index }))
          .reverse()
          .find(({ part }) => !part.isPaid && !part.locked)?.index;

        if (removeIndex === undefined) {
          toast.error("Desbloquea una parte o usa Reiniciar para reducir.");
          break;
        }
        resized.splice(removeIndex, 1);
      }
    }

    const normalized = resized.length >= 2 ? recalcParts(totalCents, resized) : splitEvenly(totalCents, 2);
    onPartsChange(normalized);
    onActivePartIdChange(chooseFallbackActive(normalized));
  };

  const incrementParts = () => setPartCount(safeParts.length + 1);

  const decrementParts = () => {
    if (safeParts.length <= 2) return;
    const candidate = [...safeParts]
      .map((part, index) => ({ part, index }))
      .reverse()
      .find(({ part }) => !part.isPaid && !part.locked)?.index;

    if (candidate === undefined) {
      toast.error("Todas las partes restantes están bloqueadas. Desbloquea o usa Reiniciar.");
      return;
    }

    const next = safeParts.filter((_, index) => index !== candidate);
    const normalized = recalcParts(totalCents, next.length >= 2 ? next : splitEvenly(totalCents, 2));
    onPartsChange(normalized);
    if (safeParts[candidate].id === activePartId) {
      onActivePartIdChange(chooseFallbackActive(normalized));
    }
  };

  const removePart = (partId: string) => {
    const target = safeParts.find((part) => part.id === partId);
    if (!target) return;
    if (target.isPaid) {
      toast.error("No puedes eliminar una parte ya pagada");
      return;
    }

    const next = safeParts.filter((part) => part.id !== partId);
    const normalized = recalcParts(totalCents, next.length >= 2 ? next : splitEvenly(totalCents, 2));
    onPartsChange(normalized);
    if (activePartId === partId) {
      onActivePartIdChange(chooseFallbackActive(normalized));
    }
  };

  const beginEdit = (part: SplitPart) => {
    setEditingPartId(part.id);
    setEditingRawValue((part.amountCents / 100).toFixed(2));
  };

  const commitEdit = (partId: string) => {
    const cents = Math.max(0, Math.round(Number(editingRawValue || 0) * 100));
    const updated = safeParts.map((part) =>
      part.id === partId
        ? {
            ...part,
            amountCents: cents,
            locked: true,
          }
        : part
    );
    const normalized = recalcParts(totalCents, updated);
    onPartsChange(normalized);
    setEditingPartId(null);
    setEditingRawValue("");
  };

  const setAuto = (partId: string) => {
    const updated = safeParts.map((part) => (part.id === partId ? { ...part, locked: false } : part));
    const normalized = recalcParts(totalCents, updated);
    onPartsChange(normalized);
  };

  const resetAll = () => {
    const reset = splitEvenly(totalCents, safeParts.length).map((part, index) => ({
      ...part,
      id: safeParts[index]?.id ?? part.id,
      isPaid: safeParts[index]?.isPaid ?? false,
    }));
    onPartsChange(reset);
    onActivePartIdChange(chooseFallbackActive(reset));
  };

  const quickSplit = (count: number) => {
    if (hasLocks) {
      const confirmed = window.confirm("Esto reiniciará los montos manuales. ¿Deseas continuar?");
      if (!confirmed) return;
      setPartCount(count, true);
      return;
    }
    setPartCount(count);
  };

  const selectNoSplit = () => {
    onModeChange?.("none");
    onEnabledChange(false);
    const reset = splitEvenly(totalCents, 1);
    onPartsChange(reset);
    onActivePartIdChange(reset[0]?.id ?? null);
  };

  const selectEqualParts = () => {
    const base = parts.length >= 2 ? parts : splitEvenly(totalCents, 2);
    const normalized = recalcParts(totalCents, base);
    onModeChange?.("equal");
    onEnabledChange(true);
    onPartsChange(normalized);
    onActivePartIdChange(chooseFallbackActive(normalized));
  };

  const selectPersonMode = () => {
    if (!canUsePersonMode) {
      toast.info(personModeDisabledReason);
      return;
    }
    onModeChange?.("person");
    if (!onModeChange) onPersonModeSelect?.();
  };

  const modeCard = ({
    mode,
    title,
    description,
    icon,
    disabled = false,
    onClick,
  }: {
    mode: "none" | "person" | "equal";
    title: string;
    description: string;
    icon: ReactNode;
    disabled?: boolean;
    onClick: () => void;
  }) => {
    const selected = selectedMode === mode;
    return (
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        disabled={disabled}
        onClick={onClick}
        className={cn(
          "tap-target flex w-full items-start gap-3 rounded-md border p-3 text-left transition-[background-color,border-color,box-shadow] duration-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          selected ? "border-primary bg-primary/10 shadow-sm" : "bg-background hover:bg-muted/40",
          disabled && "cursor-not-allowed opacity-55"
        )}
      >
        <span className={cn("mt-0.5 rounded-md border p-2", selected ? "border-primary bg-primary text-primary-foreground" : "bg-muted/40")}>
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-foreground">{title}</span>
          <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{description}</span>
        </span>
        <span
          className={cn(
            "mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
            selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40"
          )}
          aria-hidden="true"
        >
          {selected ? <Check className="h-3.5 w-3.5" /> : null}
        </span>
      </button>
    );
  };

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-md border">
      <div className="border-b bg-background px-3 py-2">
        <div>
          <div className="text-sm font-semibold">Dividir cuenta</div>
          <p className="text-xs text-muted-foreground">Elige cómo cobrar el saldo restante.</p>
        </div>
        <div className="mt-3 grid gap-2" role="radiogroup" aria-label="Modo de división">
          {modeCard({
            mode: "none",
            title: "Cuenta sin dividir",
            description: "Cobra el saldo completo en un solo pago.",
            icon: <X className="h-4 w-4" />,
            onClick: selectNoSplit,
          })}
          {modeCard({
            mode: "person",
            title: "Dividir por persona",
            description: "Cobra por separado lo consumido por cada persona.",
            icon: <Users className="h-4 w-4" />,
            disabled: !canUsePersonMode,
            onClick: selectPersonMode,
          })}
          {modeCard({
            mode: "equal",
            title: "Dividir en partes iguales",
            description: "Divide el saldo restante en 2 o más partes del mismo valor.",
            icon: <SplitSquareHorizontal className="h-4 w-4" />,
            onClick: selectEqualParts,
          })}
        </div>
      </div>

      {enabled && (
        <div className="flex min-h-0 flex-col">
          <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background px-3 py-2">
            <Label className="text-xs text-muted-foreground">Partes</Label>
            <div className="flex items-center rounded-md border">
              <Button type="button" variant="ghost" size="icon" className="h-11 w-11 rounded-none" onClick={decrementParts}>
                <Minus className="h-4 w-4" />
              </Button>
              <Input
                value={String(safeParts.length)}
                onChange={(event) => setPartCount(Number(event.target.value || 2))}
                className="h-11 w-16 rounded-none border-x text-center"
                inputMode="numeric"
                min={2}
                max={MAX_PARTS}
              />
              <Button type="button" variant="ghost" size="icon" className="h-11 w-11 rounded-none" onClick={incrementParts}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            <div className="ml-auto flex gap-1">
              {QUICK_SPLITS.map((quick) => (
                <Button key={quick} type="button" variant="outline" size="sm" className="h-11 min-w-11" onClick={() => quickSplit(quick)}>
                  {quick}
                </Button>
              ))}
            </div>

            <Button type="button" variant="ghost" size="sm" onClick={resetAll} className="h-11 gap-1">
              <RotateCcw className="h-3.5 w-3.5" /> Reiniciar
            </Button>
          </div>

          <div className="min-h-0 max-h-[clamp(220px,35vh,420px)] overflow-y-auto px-3 py-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {safeParts.map((part, index) => {
                const isActive = part.id === activePartId;
                const isEditing = editingPartId === part.id;

                return (
                  <div
                    key={part.id}
                    className={cn(
                      "rounded-lg border p-3 transition-colors",
                      isActive && "border-primary bg-primary/5",
                      part.isPaid && "opacity-70"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => onActivePartIdChange(part.id)}
                      >
                        <div className="text-sm font-semibold">Parte {index + 1}</div>
                        <div className="text-[11px] text-muted-foreground">{part.locked ? "Manual" : "Automático"}</div>
                      </button>
                      <div className="flex items-center gap-1">
                        {part.locked && !part.isPaid && (
                          <Button type="button" variant="ghost" size="icon" className="h-11 w-11" onClick={() => setAuto(part.id)} title="Volver a automático">
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11"
                          onClick={() => removePart(part.id)}
                          disabled={Boolean(part.isPaid)}
                          title={part.isPaid ? "No puedes eliminar una parte ya pagada" : "Eliminar parte"}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>

                    <div className="mt-3">
                      {isEditing ? (
                        <Input
                          value={editingRawValue}
                          onChange={(event) => setEditingRawValue(event.target.value.replace(/[^\d.]/g, ""))}
                          onBlur={() => commitEdit(part.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") commitEdit(part.id);
                            if (event.key === "Escape") {
                              setEditingPartId(null);
                              setEditingRawValue("");
                            }
                          }}
                          inputMode="decimal"
                          autoFocus
                        />
                      ) : (
                        <button
                          type="button"
                          className="text-left"
                          onClick={() => beginEdit(part)}
                          disabled={Boolean(part.isPaid)}
                        >
                          <div className="text-2xl font-bold tracking-tight">{formatMoney(part.amountCents / 100)}</div>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="sticky bottom-0 z-20 border-t bg-background px-3 py-2">
            <div className="rounded-md border bg-muted/30 p-2 text-xs">
              <div className="flex justify-between"><span>Total</span><span>{formatMoney(totalCents / 100)}</span></div>
              <div className={cn("flex justify-between", validation.diffCents === 0 ? "text-emerald-500" : "text-destructive")}>
                <span>Suma partes</span><span>{formatMoney(validation.partsSumCents / 100)}</span>
              </div>
              <div className={cn("flex justify-between", validation.diffCents === 0 ? "text-muted-foreground" : "text-destructive")}>
                <span>Diferencia</span>
                <span>{validation.diffCents >= 0 ? "Faltan" : "Exceden"} {formatMoney(Math.abs(validation.diffCents) / 100)}</span>
              </div>
              {validation.error && <div className="mt-1 text-destructive">{validation.error}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
