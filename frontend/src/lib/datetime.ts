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
    month: "2-digit",
    day: "2-digit",
  }).format(date);
};

export const formatDateTimeSV = (value: DateInput): string => {
  const date = toDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("es-SV", {
    timeZone: APP_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
};

export const formatTimeSV = (value: DateInput): string => {
  const date = toDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("es-SV", {
    timeZone: APP_TZ,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
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
