export const getProductImageSrc = (product: {
  image_url?: unknown;
  image_path?: unknown;
  imageUrl?: unknown;
  imagePath?: unknown;
}): string | null => {
  const preferred = product.image_url ?? product.imageUrl ?? null;
  if (typeof preferred === "string" && preferred) {
    return preferred.startsWith("/") ? preferred : `/${preferred}`;
  }

  const path = product.image_path ?? product.imagePath ?? null;
  if (typeof path === "string" && path) {
    return path.startsWith("/") ? path : `/${path}`;
  }

  return null;
};
