import { cn } from "@/lib/utils";
import { useElSalvadorClock } from "@/hooks/useElSalvadorClock";

type ClockSVProps = {
  className?: string;
  timeClassName?: string;
  showLabel?: boolean;
};

export const ClockSV = ({ className, timeClassName, showLabel = true }: ClockSVProps) => {
  const formatted = useElSalvadorClock();

  return (
    <div className={cn("rounded-2xl border border-emerald-500/40 bg-card/70 px-4 py-3 text-center shadow-sm", className)}>
      {showLabel ? <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">El Salvador</p> : null}
      <p suppressHydrationWarning className={cn("whitespace-nowrap font-mono text-3xl font-bold leading-none tracking-tight text-emerald-400 sm:text-4xl", timeClassName)}>
        {formatted}
      </p>
    </div>
  );
};
