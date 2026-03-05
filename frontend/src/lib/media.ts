export const getMediaUrl = (raw: unknown): string | null => {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }

  const normalized = trimmed
    .replace(/^\/+/, "")
    .replace(/^media\/menu_image\/menu_image\//, "media/menu_image/")
    .replace(/^menu_image\/menu_image\//, "menu_image/");

  const path = normalized.startsWith("media/")
    ? normalized
    : normalized.startsWith("menu_image/")
      ? `media/${normalized}`
      : normalized;

  return `${window.location.origin}/${path}`.replace(/([^:]\/)\/+/g, "$1");
};

export const getEntityImageSrc = (entity: {
  image_url?: unknown;
  imageUrl?: unknown;
  image_path?: unknown;
  imagePath?: unknown;
  image?: unknown;
}): string | null => {
  return (
    getMediaUrl(entity.image_url) ??
    getMediaUrl(entity.imageUrl) ??
    getMediaUrl(entity.image_path) ??
    getMediaUrl(entity.imagePath) ??
    getMediaUrl(entity.image)
  );
};

export const getProductImageSrc = getEntityImageSrc;
