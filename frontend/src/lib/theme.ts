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

const setOrUpdateLinkRel = (rel: string, href: string, attributes: Record<string, string> = {}) => {
  const existingLinks = Array.from(document.head.querySelectorAll<HTMLLinkElement>(`link[rel="${rel}"]`));
  let element = existingLinks[0];
  existingLinks.slice(1).forEach((link) => link.remove());
  if (!element) {
    element = document.createElement("link");
    document.head.appendChild(element);
  }
  element.setAttribute("rel", rel);
  element.setAttribute("href", href);
  Object.entries(attributes).forEach(([key, value]) => element?.setAttribute(key, value));
};

export const updatePwaLinks = (metadata: PublicPwaMetadata) => {
  setOrUpdateLinkRel("manifest", metadata.manifestUrl);
  setOrUpdateLinkRel("icon", metadata.faviconUrl);
  setOrUpdateLinkRel("shortcut icon", metadata.faviconUrl);
  setOrUpdateLinkRel("apple-touch-icon", metadata.appleTouchIconUrl);
};

export const applyPwaMetadata = (metadata: PublicPwaMetadata) => {
  const title = `${metadata.appName} - Sistema de Punto de Venta`;
  document.title = title;
  updatePwaLinks(metadata);
  upsertMeta('meta[name="theme-color"]', { name: "theme-color", content: metadata.themeColor });
  upsertMeta('meta[name="application-name"]', { name: "application-name", content: metadata.appName });
  upsertMeta('meta[name="apple-mobile-web-app-title"]', { name: "apple-mobile-web-app-title", content: metadata.shortName });
  upsertMeta('meta[name="apple-mobile-web-app-capable"]', { name: "apple-mobile-web-app-capable", content: "yes" });
  upsertMeta('meta[name="mobile-web-app-capable"]', { name: "mobile-web-app-capable", content: "yes" });
  upsertMeta('meta[name="description"]', { name: "description", content: metadata.description });
  upsertMeta('meta[name="author"]', { name: "author", content: metadata.appName });
  upsertMeta('meta[property="og:type"]', { property: "og:type", content: "website" });
  upsertMeta('meta[property="og:title"]', { property: "og:title", content: title });
  upsertMeta('meta[property="og:description"]', { property: "og:description", content: metadata.description });
  upsertMeta('meta[property="og:site_name"]', { property: "og:site_name", content: metadata.siteName });
  upsertMeta('meta[property="og:image"]', { property: "og:image", content: metadata.shareImageUrl });
  upsertMeta('meta[property="og:image:width"]', { property: "og:image:width", content: "1200" });
  upsertMeta('meta[property="og:image:height"]', { property: "og:image:height", content: "630" });
  upsertMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary_large_image" });
  upsertMeta('meta[name="twitter:title"]', { name: "twitter:title", content: title });
  upsertMeta('meta[name="twitter:description"]', { name: "twitter:description", content: metadata.description });
  upsertMeta('meta[name="twitter:image"]', { name: "twitter:image", content: metadata.shareImageUrl });
};

const APPEARANCE_CACHE_KEY = "gastroposv.publicAppearance";
const PWA_METADATA_CACHE_KEY = "gastroposv.publicPwaMetadata";
const PWA_METADATA_VERSION_KEY = "gastroposv.publicPwaMetadataVersion";

const clearDynamicPwaCaches = async () => {
  if (!("caches" in window)) return;
  try {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("gastroposv-pwa-")).map((key) => caches.delete(key)));
  } catch {
    // Cache cleanup is best-effort; fresh metadata links still force the current version.
  }
};

export const loadAppearanceSettings = async () => {
  try {
    const cached = localStorage.getItem(APPEARANCE_CACHE_KEY);
    if (cached) {
      applyAppearanceSettings(JSON.parse(cached) as AppearanceSettings);
    }
  } catch {
    localStorage.removeItem(APPEARANCE_CACHE_KEY);
    localStorage.removeItem(PWA_METADATA_CACHE_KEY);
    localStorage.removeItem(PWA_METADATA_VERSION_KEY);
  }
  const [appearanceResult, pwaResult] = await Promise.allSettled([getPublicAppearanceSettings(), getPublicPwaMetadata()]);
  if (appearanceResult.status === "fulfilled") {
    applyAppearanceSettings(appearanceResult.value);
    localStorage.setItem(APPEARANCE_CACHE_KEY, JSON.stringify(appearanceResult.value));
  }
  if (pwaResult.status === "fulfilled") {
    const currentVersion = pwaResult.value.brandingVersion || pwaResult.value.version;
    const previousVersion = localStorage.getItem(PWA_METADATA_VERSION_KEY);
    applyPwaMetadata(pwaResult.value);
    localStorage.setItem(PWA_METADATA_CACHE_KEY, JSON.stringify(pwaResult.value));
    localStorage.setItem(PWA_METADATA_VERSION_KEY, currentVersion);
    if (previousVersion && previousVersion !== currentVersion) {
      void clearDynamicPwaCaches();
    }
  }
};
