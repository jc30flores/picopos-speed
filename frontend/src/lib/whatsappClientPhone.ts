export type WhatsAppCountry = "ESA" | "USA";

const digitsOnly = (value: string): string => value.replace(/\D/g, "");

export const formatWhatsAppClientPhone = (country: WhatsAppCountry, input: string): string => {
  const digits = digitsOnly(input);
  if (!digits) return "";
  if (country === "ESA") {
    const local = digits.startsWith("503") ? digits.slice(3) : digits;
    const head = local.slice(0, 4);
    const tail = local.slice(4, 8);
    if (!tail) return `+503 ${head}`;
    return `+503 ${head}-${tail}`;
  }
  const local = digits.startsWith("1") ? digits.slice(1) : digits;
  const a = local.slice(0, 3);
  const b = local.slice(3, 7);
  const c = local.slice(7, 10);
  if (local.length <= 3) return `+1 (${a}`;
  if (local.length <= 7) return `+1 (${a}) ${b}`;
  return `+1 (${a}) ${b}-${c}`;
};

export const normalizeWhatsAppClientPhone = (
  country: WhatsAppCountry,
  input: string
): { ok: true; e164: string } | { ok: false; error: string } => {
  const digits = digitsOnly(input);
  if (!digits) return { ok: false, error: "Ingresa un número válido." };
  if (country === "ESA") {
    const local = digits.startsWith("503") ? digits.slice(3) : digits;
    if (local.length !== 8) return { ok: false, error: "Para ESA usa 8 dígitos." };
    return { ok: true, e164: `+503${local}` };
  }
  const local = digits.startsWith("1") ? digits.slice(1) : digits;
  if (local.length !== 10) return { ok: false, error: "Para USA usa 10 dígitos." };
  return { ok: true, e164: `+1${local}` };
};

export const validateWhatsAppClientPhone = (country: WhatsAppCountry, input: string): string | null => {
  if (!input.trim()) return null;
  const normalized = normalizeWhatsAppClientPhone(country, input);
  return normalized.ok ? null : normalized.error;
};

export const resolveWhatsappDestination = (params: {
  manualPhone: string;
  manualCountry: WhatsAppCountry;
  receptorPhone: string;
}) => {
  const manualTrim = params.manualPhone.trim();
  const receptorTrim = params.receptorPhone.trim();
  if (manualTrim) {
    const normalizedManual = normalizeWhatsAppClientPhone(params.manualCountry, manualTrim);
    if (!normalizedManual.ok) {
      return { ok: false as const, reason: normalizedManual.error };
    }
    return { ok: true as const, phone: normalizedManual.e164, source: "manual" as const };
  }
  if (!receptorTrim) {
    return { ok: false as const, reason: "No hay teléfono manual y el DTE no tiene receptor.telefono válido." };
  }
  const fallbackCountry: WhatsAppCountry = digitsOnly(receptorTrim).startsWith("1") ? "USA" : "ESA";
  const normalizedFallback = normalizeWhatsAppClientPhone(fallbackCountry, receptorTrim);
  if (!normalizedFallback.ok) {
    return { ok: false as const, reason: "receptor.telefono del DTE es inválido." };
  }
  return { ok: true as const, phone: normalizedFallback.e164, source: "receptor_json" as const };
};

export const maskPhoneForLog = (value: string): string => {
  const digits = digitsOnly(value);
  if (!digits) return "***";
  return `***${digits.slice(-4)}`;
};
