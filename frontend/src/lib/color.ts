const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

export const isValidHexColor = (value?: string | null) => Boolean(value && HEX_COLOR_RE.test(value));

export const getReadableTextColor = (backgroundColor?: string | null) => {
  if (!isValidHexColor(backgroundColor)) return undefined;
  const hex = String(backgroundColor).slice(1);
  const r = parseInt(hex.slice(0, 2), 16) / 255;
  const g = parseInt(hex.slice(2, 4), 16) / 255;
  const b = parseInt(hex.slice(4, 6), 16) / 255;
  const linear = [r, g, b].map((channel) => (channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)));
  const luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  return luminance > 0.45 ? '#111827' : '#FFFFFF';
};
