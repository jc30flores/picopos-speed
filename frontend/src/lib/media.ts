export const getProductImageSrc = (product: {
  image_url?: unknown;
  image_path?: unknown;
  imageUrl?: unknown;
  imagePath?: unknown;
}): string | null => {
  const preferred = product.image_url ?? product.imageUrl ?? null;
  if (typeof preferred === "string" && preferred.trim()) {
    const trimmed = preferred.trim();
    return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  }

  const path = product.image_path ?? product.imagePath ?? null;
  if (typeof path === "string" && path.trim()) {
    const trimmed = path.trim();
    return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  }

  return null;
};
