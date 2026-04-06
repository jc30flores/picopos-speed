import { cn } from "@/lib/utils";
import { useElSalvadorClock } from "@/hooks/useElSalvadorClock";

type ClockSVProps = {
  className?: string;
  timeClassName?: string;
};

export const ClockSV = ({ className, timeClassName }: ClockSVProps) => {
  const formatted = useElSalvadorClock();

  return (
    <div className={cn("rounded-2xl border border-emerald-500/40 bg-card/70 px-4 py-3 text-center shadow-sm", className)}>
      <p suppressHydrationWarning className={cn("whitespace-nowrap font-mono text-3xl font-bold leading-none tracking-tight text-emerald-400 sm:text-4xl", timeClassName)}>
        {formatted}
      </p>
    </div>
  );
};
