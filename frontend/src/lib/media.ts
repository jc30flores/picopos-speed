export const getProductImageSrc = (product: {
  image_url?: unknown;
  imageUrl?: unknown;
  image_path?: unknown;
  imagePath?: unknown;
  image?: unknown;
}): string | null => {

  const url =
    product.image_url ??
    product.imageUrl ??
    product.image_path ??
    product.imagePath ??
    product.image ??
    null;

  if (typeof url !== "string") return null;

  const trimmed = url.trim();
  if (!trimmed) return null;

  // SIEMPRE devolver URL absoluta del navegador
  if (trimmed.startsWith("http")) return trimmed;

  return `${window.location.origin}${trimmed.startsWith("/") ? "" : "/"}${trimmed}`;
};
