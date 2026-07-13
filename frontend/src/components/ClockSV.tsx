import { cn } from "@/lib/utils";
import { useElSalvadorClock } from "@/hooks/useElSalvadorClock";

type ClockSVProps = {
  className?: string;
  timeClassName?: string;
};

export const ClockSV = ({ className, timeClassName }: ClockSVProps) => {
  const formatted = useElSalvadorClock();

  return (
    <div className={cn("rounded-2xl border gp-primary-border bg-card/70 px-4 py-3 text-center shadow-sm", className)}>
      <p suppressHydrationWarning className={cn("whitespace-nowrap font-mono text-3xl font-bold leading-none tracking-tight gp-primary-text sm:text-4xl", timeClassName)}>
        {formatted}
      </p>
    </div>
  );
};
