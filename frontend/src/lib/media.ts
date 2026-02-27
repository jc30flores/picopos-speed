export const getMediaUrl = (raw: unknown): string | null => {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }

  const path = trimmed.replace(/^\/+/, "");
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
