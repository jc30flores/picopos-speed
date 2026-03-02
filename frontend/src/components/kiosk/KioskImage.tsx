import { memo, useEffect, useState } from "react";
import { Eye } from "lucide-react";
import { cn } from "@/lib/utils";

interface KioskImageProps {
  src?: string | null;
  alt: string;
  ratio?: string;
  className?: string;
  imageClassName?: string;
  loading?: "lazy" | "eager";
  sizes?: string;
  onPreview?: () => void;
  onImageError?: () => void;
}

export const KioskImage = memo(
  ({
    src,
    alt,
    ratio = "4 / 3",
    className,
    imageClassName,
    loading = "lazy",
    sizes,
    onPreview,
    onImageError,
  }: KioskImageProps) => {
    const [isLoading, setIsLoading] = useState(Boolean(src));
    const [hasError, setHasError] = useState(false);

    useEffect(() => {
      setHasError(false);
      setIsLoading(Boolean(src));
    }, [src]);

    if (!src || hasError) {
      return null;
    }

    return (
      <div
        className={cn(
          "relative overflow-hidden rounded-2xl border border-white/10 bg-muted/60",
          onPreview && "cursor-zoom-in",
          className,
        )}
        style={{ aspectRatio: ratio }}
      >
        <img
          src={src}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full scale-110 object-cover blur-xl opacity-35"
          loading={loading}
          decoding="async"
          sizes={sizes}
        />
        <img
          src={src}
          alt={alt}
          loading={loading}
          decoding="async"
          sizes={sizes}
          className={cn("relative z-10 h-full w-full object-contain p-2 md:p-3", imageClassName)}
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setHasError(true);
            setIsLoading(false);
            onImageError?.();
          }}
        />

        {isLoading && (
          <div className="absolute inset-0 z-20 animate-pulse bg-gradient-to-br from-white/10 via-white/5 to-transparent" />
        )}

        {onPreview && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onPreview();
            }}
            className="absolute right-3 top-3 z-30 rounded-full bg-black/55 px-3 py-1.5 text-xs font-semibold text-white shadow-lg transition hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Vista previa"
          >
            <Eye className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  },
);

KioskImage.displayName = "KioskImage";
