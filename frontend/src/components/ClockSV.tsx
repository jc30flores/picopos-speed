import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

const TIME_ZONE = "America/El_Salvador";

const formatSVTime = (date: Date) => {
  const value = new Intl.DateTimeFormat("es-SV", {
    timeZone: TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(date);
  return value.replace("a.\u00a0m.", "a. m.").replace("p.\u00a0m.", "p. m.");
};

type ClockSVProps = {
  className?: string;
  timeClassName?: string;
  showLabel?: boolean;
};

export const ClockSV = ({ className, timeClassName, showLabel = true }: ClockSVProps) => {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const formatted = useMemo(() => formatSVTime(now), [now]);

  return (
    <div className={cn("rounded-2xl border border-emerald-500/40 bg-card/70 px-4 py-3 text-center shadow-sm", className)}>
      {showLabel ? <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">El Salvador</p> : null}
      <p className={cn("font-mono text-3xl font-bold leading-none text-emerald-400 sm:text-4xl", timeClassName)}>{formatted}</p>
    </div>
  );
};
