const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

export const isValidHexColor = (value?: string | null) => Boolean(value && HEX_COLOR_RE.test(value));

const hexToRgb = (value?: string | null) => {
  if (!isValidHexColor(value)) return undefined;
  const hex = String(value).slice(1);
  return {
    r: parseInt(hex.slice(0, 2), 16),
    g: parseInt(hex.slice(2, 4), 16),
    b: parseInt(hex.slice(4, 6), 16),
  };
};

const relativeLuminance = (value?: string | null) => {
  const rgb = hexToRgb(value);
  if (!rgb) return undefined;
  const linear = [rgb.r, rgb.g, rgb.b]
    .map((channel) => channel / 255)
    .map((channel) => (channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
};

export const getContrastRatio = (foreground?: string | null, background?: string | null) => {
  const fg = relativeLuminance(foreground);
  const bg = relativeLuminance(background);
  if (fg === undefined || bg === undefined) return 1;
  const lighter = Math.max(fg, bg);
  const darker = Math.min(fg, bg);
  return (lighter + 0.05) / (darker + 0.05);
};

export const getReadableTextColor = (backgroundColor?: string | null) => {
  if (!isValidHexColor(backgroundColor)) return undefined;
  const luminance = relativeLuminance(backgroundColor) ?? 0;
  return luminance > 0.45 ? "#111827" : "#FFFFFF";
};

export const ensureReadableColor = (foreground?: string | null, background?: string | null, minimumRatio = 4.5) => {
  if (!isValidHexColor(background)) return foreground || undefined;
  if (isValidHexColor(foreground) && getContrastRatio(foreground, background) >= minimumRatio) return String(foreground);
  return getReadableTextColor(background);
};

export const deriveThemeTokens = (primaryColor?: string | null, mode: "light" | "dark" = "light") => {
  const primary = isValidHexColor(primaryColor) ? String(primaryColor) : "#1F7A4D";
  const primaryContrast = getReadableTextColor(primary) ?? (mode === "dark" ? "#0F172A" : "#FFFFFF");
  return {
    "--color-primary": primary,
    "--color-primary-contrast": primaryContrast,
    "--badge-bg": mode === "dark" ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.07)",
    "--badge-text": mode === "dark" ? "#F8FAFC" : "#0F172A",
  };
};
