import { getPublicAppearanceSettings, type AppearanceSettings } from "@/lib/api";

const hexToHsl = (hex: string): string => {
  const cleaned = hex.replace("#", "");
  const r = parseInt(cleaned.slice(0, 2), 16) / 255;
  const g = parseInt(cleaned.slice(2, 4), 16) / 255;
  const b = parseInt(cleaned.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
};

export const applyAppearanceSettings = (settings: AppearanceSettings) => {
  const root = document.documentElement;
  Object.entries(settings.cssVariables).forEach(([key, value]) => root.style.setProperty(key, value));
  root.style.setProperty("--primary", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--primary-light", hexToHsl(settings.colorPrimaryHover));
  root.style.setProperty("--primary-foreground", hexToHsl(settings.colorPrimaryContrast));
  root.style.setProperty("--secondary", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--secondary-light", hexToHsl(settings.colorPrimarySoft));
  root.style.setProperty("--accent", hexToHsl(settings.colorPrimarySoft));
  root.style.setProperty("--accent-foreground", hexToHsl(settings.colorPrimaryText));
  root.style.setProperty("--ring", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--gradient-accent", `linear-gradient(135deg, ${settings.colorPrimary}, ${settings.colorPrimaryHover})`);
};

export const loadAppearanceSettings = async () => {
  try {
    applyAppearanceSettings(await getPublicAppearanceSettings());
  } catch {
    // Apariencia no debe bloquear el arranque de la app.
  }
};
