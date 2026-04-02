import { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { LayoutGrid } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";

type PageLayoutProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  maxWidthClassName?: string;
  className?: string;
};

export const PageLayout = ({
  title,
  subtitle,
  actions,
  children,
  maxWidthClassName = "",
  className,
}: PageLayoutProps) => {
  const navigate = useNavigate();

  return (
    <div className="min-h-[100svh] w-full bg-background">
      <div className={cn("w-full space-y-6 px-4 pb-8 pt-4 md:px-6 md:pt-6 xl:px-8", maxWidthClassName, className)}>
        <header className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border bg-card/80 px-4 py-4 shadow-sm md:px-6">
          <div className="flex min-w-0 items-start gap-4">
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="h-12 w-12 shrink-0 rounded-full md:h-14 md:w-14"
              onClick={() => navigate("/")}
              aria-label="Menú principal"
              title="Menú principal"
            >
              <LayoutGrid className="h-5 w-5 md:h-6 md:w-6" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl md:text-4xl">{title}</h1>
              {subtitle ? <p className="mt-1 text-sm text-muted-foreground md:text-base">{subtitle}</p> : null}
            </div>
          </div>
          {actions ? <div className="flex min-h-12 items-center gap-2 md:min-h-14">{actions}</div> : null}
        </header>
        {children}
      </div>
    </div>
  );
};
