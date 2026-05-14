export type DteExportType = "json" | "f07" | "pdf";

export const DTE_EXPORT_MONTHS = [
  { value: 1, label: "Enero" },
  { value: 2, label: "Febrero" },
  { value: 3, label: "Marzo" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Mayo" },
  { value: 6, label: "Junio" },
  { value: 7, label: "Julio" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Septiembre" },
  { value: 10, label: "Octubre" },
  { value: 11, label: "Noviembre" },
  { value: 12, label: "Diciembre" },
] as const;

const MONTHS_ES_ZIP = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

export const getPreviousMonthPeriod = (now = new Date()): { year: number; month: number } => {
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  if (currentMonth === 1) {
    return { year: currentYear - 1, month: 12 };
  }

  return { year: currentYear, month: currentMonth - 1 };
};

export const getExportZipName = (month: number, year: number, type: DteExportType | string): string => {
  const monthName = MONTHS_ES_ZIP[month - 1] ?? "periodo";
  const typeLower = String(type || "").toLowerCase();
  return `${monthName}_${typeLower}_${year}.zip`;
};
