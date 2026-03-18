import { useMemo, useState } from "react";
import { Minus, Plus, RotateCcw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/money";
import { recalcParts, SplitPart, splitEvenly, validateParts } from "@/lib/splitPayments";
import { toast } from "sonner";

type SplitPanelProps = {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  totalCents: number;
  parts: SplitPart[];
  onPartsChange: (parts: SplitPart[]) => void;
  activePartId: string | null;
  onActivePartIdChange: (partId: string | null) => void;
};

const MAX_PARTS = 20;
const QUICK_SPLITS = [2, 3, 4, 5];

const nextPartId = (): string => `part-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

export function SplitPanel({
  enabled,
  onEnabledChange,
  totalCents,
  parts,
  onPartsChange,
  activePartId,
  onActivePartIdChange,
}: SplitPanelProps) {
  const [editingPartId, setEditingPartId] = useState<string | null>(null);
  const [editingRawValue, setEditingRawValue] = useState("");

  const safeParts = useMemo(() => (parts.length ? parts : splitEvenly(totalCents, 1)), [parts, totalCents]);
  const validation = useMemo(() => validateParts(totalCents, safeParts), [safeParts, totalCents]);
  const hasLocks = safeParts.some((part) => part.locked);

  const chooseFallbackActive = (list: SplitPart[]): string | null => {
    if (!list.length) return null;
    const unpaid = list.find((part) => !part.isPaid);
    return unpaid?.id ?? list[0]?.id ?? null;
  };

  const setPartCount = (count: number, resetLocks = false) => {
    const target = Math.max(1, Math.min(MAX_PARTS, Math.floor(count || 1)));
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
          toast.error("Desbloquea una parte o usa Reset para reducir.");
          break;
        }
        resized.splice(removeIndex, 1);
      }
    }

    const normalized = resized.length ? recalcParts(totalCents, resized) : splitEvenly(totalCents, 1);
    onPartsChange(normalized);
    onActivePartIdChange(chooseFallbackActive(normalized));
  };

  const incrementParts = () => setPartCount(safeParts.length + 1);

  const decrementParts = () => {
    if (safeParts.length <= 1) return;
    const candidate = [...safeParts]
      .map((part, index) => ({ part, index }))
      .reverse()
      .find(({ part }) => !part.isPaid && !part.locked)?.index;

    if (candidate === undefined) {
      toast.error("Todas las partes restantes están bloqueadas. Desbloquea o haz Reset.");
      return;
    }

    const next = safeParts.filter((_, index) => index !== candidate);
    const normalized = recalcParts(totalCents, next.length ? next : splitEvenly(totalCents, 1));
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
    const normalized = recalcParts(totalCents, next.length ? next : splitEvenly(totalCents, 1));
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

  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">Dividir cuenta</div>
          <p className="text-xs text-muted-foreground">Controla y cobra cada parte con precisión</p>
        </div>
        <Checkbox checked={enabled} onCheckedChange={(checked) => onEnabledChange(checked === true)} />
      </div>

      {enabled && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Label className="text-xs text-muted-foreground">Partes</Label>
            <div className="flex items-center rounded-md border">
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8 rounded-none" onClick={decrementParts}>
                <Minus className="h-4 w-4" />
              </Button>
              <Input
                value={String(safeParts.length)}
                onChange={(event) => setPartCount(Number(event.target.value || 1))}
                className="h-8 w-14 rounded-none border-x text-center"
                inputMode="numeric"
                min={1}
                max={MAX_PARTS}
              />
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8 rounded-none" onClick={incrementParts}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            <div className="ml-auto flex gap-1">
              {QUICK_SPLITS.map((quick) => (
                <Button key={quick} type="button" variant="outline" size="sm" onClick={() => quickSplit(quick)}>
                  {quick}
                </Button>
              ))}
            </div>

            <Button type="button" variant="ghost" size="sm" onClick={resetAll} className="gap-1">
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </Button>
          </div>

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
                      <div className="text-[11px] text-muted-foreground">{part.locked ? "Manual" : "Auto"}</div>
                    </button>
                    <div className="flex items-center gap-1">
                      {part.locked && !part.isPaid && (
                        <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={() => setAuto(part.id)} title="Volver a auto">
                          <RotateCcw className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
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
      )}
    </div>
  );
}
