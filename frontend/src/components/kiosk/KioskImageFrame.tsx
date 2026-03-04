import { cn } from "@/lib/utils";

interface KioskImageFrameProps {
  className?: string;
  ratio?: string;
  children: React.ReactNode;
}

export const KioskImageFrame = ({ className, ratio = "4 / 3", children }: KioskImageFrameProps) => (
  <div
    className={cn("relative overflow-hidden rounded-2xl border border-white/10 bg-white", className)}
    style={{ aspectRatio: ratio }}
  >
    {children}
  </div>
);
