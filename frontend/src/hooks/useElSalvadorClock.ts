import { useEffect, useMemo, useState } from "react";

const TIMEZONE = "America/El_Salvador";

export const formatElSalvadorTime = (date: Date = new Date()): string => {
  const parts = new Intl.DateTimeFormat("es-SV", {
    timeZone: TIMEZONE,
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).formatToParts(date);

  return parts
    .filter((part) => part.type !== "dayPeriod")
    .map((part) => part.value)
    .join("")
    .replace(/\s+/g, " ")
    .trim();
};

export const useElSalvadorClock = () => {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const value = useMemo(() => (now ? formatElSalvadorTime(now) : ""), [now]);
  return value;
};
