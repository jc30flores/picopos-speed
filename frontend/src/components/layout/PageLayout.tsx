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
  maxWidthClassName = "max-w-7xl",
  className,
}: PageLayoutProps) => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <div className={cn("mx-auto space-y-4 px-4 pb-6 pt-4", maxWidthClassName, className)}>
        <header className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border bg-card/60 px-4 py-3 shadow-sm">
          <div className="flex min-w-0 items-start gap-3">
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="h-11 w-11 shrink-0 rounded-full"
              onClick={() => navigate("/")}
              aria-label="Menú principal"
              title="Menú principal"
            >
              <LayoutGrid className="h-5 w-5" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
              {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
            </div>
          </div>
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </header>
        {children}
      </div>
    </div>
  );
};
