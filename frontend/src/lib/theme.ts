import { getPublicAppearanceSettings, getPublicPwaMetadata, type AppearanceSettings, type PublicPwaMetadata } from "@/lib/api";
import { deriveThemeTokens, ensureReadableColor, getReadableTextColor, isValidHexColor } from "@/lib/color";

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
  const isDark = root.classList.contains("dark");
  const derivedTokens = deriveThemeTokens(settings.colorPrimary, isDark ? "dark" : "light");
  const primaryContrast = ensureReadableColor(settings.colorPrimaryContrast, settings.colorPrimary) ?? getReadableTextColor(settings.colorPrimary) ?? settings.colorPrimaryContrast;
  const primaryText = isValidHexColor(settings.colorPrimarySoft)
    ? ensureReadableColor(settings.colorPrimaryText, settings.colorPrimarySoft) ?? getReadableTextColor(settings.colorPrimarySoft) ?? settings.colorPrimaryText
    : settings.colorPrimaryText;
  Object.entries(settings.cssVariables).forEach(([key, value]) => root.style.setProperty(key, value));
  Object.entries(derivedTokens).forEach(([key, value]) => root.style.setProperty(key, value));
  root.style.setProperty("--color-primary-contrast", primaryContrast);
  root.style.setProperty("--color-primary-text", primaryText);
  root.style.setProperty("--color-primary-active", settings.cssVariables["--color-primary-active"] ?? settings.colorPrimaryHover);
  root.style.setProperty("--color-primary-ring", settings.cssVariables["--color-primary-ring"] ?? settings.colorPrimaryBorder);
  root.style.setProperty("--color-primary-chart", settings.cssVariables["--color-primary-chart"] ?? settings.colorPrimary);
  root.style.setProperty("--color-primary-muted", settings.cssVariables["--color-primary-muted"] ?? settings.colorPrimarySoft);
  root.style.setProperty("--color-primary-surface", settings.cssVariables["--color-primary-surface"] ?? settings.colorPrimarySoft);
  root.style.setProperty("--primary", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--primary-light", hexToHsl(settings.colorPrimaryHover));
  root.style.setProperty("--primary-foreground", hexToHsl(primaryContrast));
  root.style.setProperty("--secondary", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--secondary-light", hexToHsl(settings.colorPrimarySoft));
  root.style.setProperty("--accent", hexToHsl(settings.colorPrimarySoft));
  root.style.setProperty("--accent-foreground", hexToHsl(primaryText));
  root.style.setProperty("--ring", hexToHsl(settings.colorPrimary));
  root.style.setProperty("--gradient-accent", `linear-gradient(135deg, ${settings.colorPrimary}, ${settings.colorPrimaryHover})`);
};

const upsertMeta = (selector: string, attributes: Record<string, string>) => {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    document.head.appendChild(element);
  }
  Object.entries(attributes).forEach(([key, value]) => element?.setAttribute(key, value));
};

const upsertLink = (selector: string, attributes: Record<string, string>) => {
  let element = document.head.querySelector<HTMLLinkElement>(selector);
  if (!element) {
    element = document.createElement("link");
    document.head.appendChild(element);
  }
  Object.entries(attributes).forEach(([key, value]) => element?.setAttribute(key, value));
};

export const applyPwaMetadata = (metadata: PublicPwaMetadata) => {
  const title = `${metadata.appName} - Sistema de Punto de Venta`;
  document.title = title;
  upsertLink('link[rel="manifest"]', { rel: "manifest", href: metadata.manifestUrl });
  upsertLink('link[rel="icon"]', { rel: "icon", href: metadata.faviconUrl });
  upsertLink('link[rel="shortcut icon"]', { rel: "shortcut icon", href: metadata.faviconUrl });
  upsertLink('link[rel="apple-touch-icon"]', { rel: "apple-touch-icon", href: metadata.appleTouchIconUrl });
  upsertMeta('meta[name="theme-color"]', { name: "theme-color", content: metadata.themeColor });
  upsertMeta('meta[name="application-name"]', { name: "application-name", content: metadata.appName });
  upsertMeta('meta[name="apple-mobile-web-app-title"]', { name: "apple-mobile-web-app-title", content: metadata.shortName });
  upsertMeta('meta[name="apple-mobile-web-app-capable"]', { name: "apple-mobile-web-app-capable", content: "yes" });
  upsertMeta('meta[name="mobile-web-app-capable"]', { name: "mobile-web-app-capable", content: "yes" });
  upsertMeta('meta[property="og:title"]', { property: "og:title", content: title });
  upsertMeta('meta[property="og:description"]', { property: "og:description", content: metadata.description });
};

const APPEARANCE_CACHE_KEY = "gastroposv.publicAppearance";
const PWA_METADATA_CACHE_KEY = "gastroposv.publicPwaMetadata";

export const loadAppearanceSettings = async () => {
  try {
    const cached = localStorage.getItem(APPEARANCE_CACHE_KEY);
    if (cached) {
      applyAppearanceSettings(JSON.parse(cached) as AppearanceSettings);
    }
    const cachedPwa = localStorage.getItem(PWA_METADATA_CACHE_KEY);
    if (cachedPwa) {
      applyPwaMetadata(JSON.parse(cachedPwa) as PublicPwaMetadata);
    }
  } catch {
    localStorage.removeItem(APPEARANCE_CACHE_KEY);
    localStorage.removeItem(PWA_METADATA_CACHE_KEY);
  }
  const [appearanceResult, pwaResult] = await Promise.allSettled([getPublicAppearanceSettings(), getPublicPwaMetadata()]);
  if (appearanceResult.status === "fulfilled") {
    applyAppearanceSettings(appearanceResult.value);
    localStorage.setItem(APPEARANCE_CACHE_KEY, JSON.stringify(appearanceResult.value));
  }
  if (pwaResult.status === "fulfilled") {
    applyPwaMetadata(pwaResult.value);
    localStorage.setItem(PWA_METADATA_CACHE_KEY, JSON.stringify(pwaResult.value));
  }
};
