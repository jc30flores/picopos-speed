export const getProductImageSrc = (product: {
  image_url?: unknown;
  image_path?: unknown;
  image?: unknown;
  imageUrl?: unknown;
  imagePath?: unknown;
}): string | null => {
  const preferred = product.image_url ?? product.imageUrl ?? null;
  if (typeof preferred === "string" && preferred) {
    if (preferred.startsWith("http://") || preferred.startsWith("https://")) {
      try {
        const url = new URL(preferred);
        return `${url.pathname}${url.search}`;
      } catch {
        return null;
      }
    }
    return preferred.startsWith("/") ? preferred : `/${preferred}`;
  }

  const path = product.image_path ?? product.imagePath ?? null;
  if (typeof path === "string" && path) {
    if (path.startsWith("http://") || path.startsWith("https://")) {
      try {
        const url = new URL(path);
        return `${url.pathname}${url.search}`;
      } catch {
        return null;
      }
    }
    return path.startsWith("/") ? path : `/${path}`;
  }

  const image = product.image ?? null;
  if (typeof image !== "string" || !image) return null;
  if (image.startsWith("http://") || image.startsWith("https://")) {
    try {
      const url = new URL(image);
      return `${url.pathname}${url.search}`;
    } catch {
      return null;
    }
  }
  if (image.startsWith("/")) return image;
  return `/media/menu_image/${image}`;
};
