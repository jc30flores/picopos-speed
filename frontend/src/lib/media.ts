export const getProductImageSrc = (product: {
  image_url?: unknown;
  image?: unknown;
  imageUrl?: unknown;
  imagePath?: unknown;
  photo_url?: unknown;
  photo?: unknown;
}): string | null => {
  const raw =
    product.image_url ??
    product.image ??
    product.imageUrl ??
    product.imagePath ??
    product.photo_url ??
    product.photo ??
    null;

  if (!raw || typeof raw !== "string") return null;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  if (!raw.startsWith("/")) return `/${raw}`;
  return raw;
};
