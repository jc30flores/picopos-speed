import { memo, useEffect, useMemo, useState } from "react";
import { Eye, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { KioskImageFrame } from "@/components/kiosk/KioskImageFrame";

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

const getVariantSrcSet = (src: string) => {
  if (src.startsWith("data:")) return undefined;
  return `${src}?w=256 256w, ${src}?w=512 512w, ${src}?w=1024 1024w`;
};

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

    const srcSet = useMemo(() => (src ? getVariantSrcSet(src) : undefined), [src]);

    if (!src || hasError) {
      return (
        <KioskImageFrame ratio={ratio} className={className}>
          <div className="flex h-full w-full items-center justify-center text-slate-500">
            <ImageIcon className="h-8 w-8" />
          </div>
        </KioskImageFrame>
      );
    }

    return (
      <KioskImageFrame ratio={ratio} className={cn(onPreview && "cursor-zoom-in", className)}>
        <img
          src={src}
          srcSet={srcSet}
          sizes={sizes}
          alt={alt}
          loading={loading}
          decoding="async"
          className={cn("relative z-10 h-full w-full object-contain p-2 md:p-3", imageClassName)}
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setHasError(true);
            setIsLoading(false);
            onImageError?.();
          }}
        />

        {isLoading && <div className="absolute inset-0 z-20 animate-pulse bg-slate-200/70" />}

        {onPreview && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onPreview();
            }}
            className="absolute right-3 top-3 z-30 rounded-full bg-black/55 p-2 text-white shadow-lg transition hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Vista previa"
          >
            <Eye className="h-5 w-5" />
          </button>
        )}
      </KioskImageFrame>
    );
  },
);

KioskImage.displayName = "KioskImage";
