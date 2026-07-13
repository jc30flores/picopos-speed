export const APP_TZ = "America/El_Salvador";

type DateInput = string | Date | null | undefined;

const toDate = (value: DateInput): Date | null => {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const getYmdParts = (value: DateInput): { year: string; month: string; day: string } | null => {
  const date = toDate(value);
  if (!date) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: APP_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  return {
    year: parts.find((part) => part.type === "year")?.value ?? "",
    month: parts.find((part) => part.type === "month")?.value ?? "",
    day: parts.find((part) => part.type === "day")?.value ?? "",
  };
};

export const formatDateSV = (value: DateInput): string => {
  const date = toDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("es-SV", {
    timeZone: APP_TZ,
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(date);
};

export const formatDateTimeSV = (value: DateInput): string => {
  const date = toDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("es-SV", {
    timeZone: APP_TZ,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(date);
};

export const formatTimeSV = (value: DateInput): string => {
  const date = toDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("es-SV", {
    timeZone: APP_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(date);
};

export const formatDateShort = formatDateSV;
export const formatDateTime = formatDateTimeSV;
export const formatTime = formatTimeSV;

export const formatCurrency = (value: number | string | null | undefined): string => {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("es-SV", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
};

export const formatPercent = (value: number | string | null | undefined, digits = 1): string => {
  const amount = Number(value ?? 0);
  return `${Number.isFinite(amount) ? amount.toFixed(digits) : "0.0"}%`;
};

export const formatDurationMinutes = (minutes: number | string | null | undefined): string => {
  const total = Math.max(0, Math.round(Number(minutes ?? 0) || 0));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  return `${hours}h ${String(mins).padStart(2, "0")}m`;
};

export const formatPeriodLabel = (value: DateInput, granularity?: "hours" | "week" | "month" | "year" | string): string => {
  const date = toDate(value);
  if (!date) return String(value ?? "-");
  if (granularity === "hours") return formatTimeSV(date);
  if (granularity === "year") {
    return new Intl.DateTimeFormat("es-SV", { timeZone: APP_TZ, year: "numeric" }).format(date);
  }
  if (granularity === "month") {
    return new Intl.DateTimeFormat("es-SV", { timeZone: APP_TZ, month: "short", year: "numeric" }).format(date);
  }
  return new Intl.DateTimeFormat("es-SV", { timeZone: APP_TZ, day: "2-digit", month: "short" }).format(date);
};

export const getHourSV = (value: DateInput): number | null => {
  const date = toDate(value);
  if (!date) return null;
  const hour = new Intl.DateTimeFormat("en-US", {
    timeZone: APP_TZ,
    hour: "2-digit",
    hour12: false,
  }).format(date);
  const parsed = Number.parseInt(hour, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

export const getLocalDateSV = (value: DateInput = new Date()): string => {
  const parts = getYmdParts(value);
  if (!parts || !parts.year || !parts.month || !parts.day) return "";
  return `${parts.year}-${parts.month}-${parts.day}`;
};
