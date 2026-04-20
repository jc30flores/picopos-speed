export type WhatsAppCountry = "ESA" | "USA";

const digitsOnly = (value: string): string => value.replace(/\D/g, "");

export const formatWhatsAppClientPhone = (country: WhatsAppCountry, input: string): string => {
  const digits = digitsOnly(input);
  if (country === "ESA") {
    const head = digits.slice(0, 4);
    const tail = digits.slice(4, 8);
    if (!digits) return "+503 ";
    if (!tail) return `+503 ${head}`;
    return `+503 ${head}-${tail}`;
  }
  const local = digits.startsWith("1") ? digits.slice(1) : digits;
  const a = local.slice(0, 3);
  const b = local.slice(3, 7);
  const c = local.slice(7, 10);
  if (!local) return "+1 ";
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
