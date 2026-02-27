import { cn } from "@/lib/utils";

export type PageTabItem = {
  label: string;
  value: string;
};

interface PageTabsProps {
  tabs: PageTabItem[];
  activeValue: string;
  onChange: (value: string) => void;
  className?: string;
}

export const PageTabs = ({ tabs, activeValue, onChange, className }: PageTabsProps) => {
  return (
    <div className={cn("mb-6 flex flex-wrap gap-2", className)}>
      {tabs.map((tab) => {
        const active = tab.value === activeValue;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cn(
              "rounded-xl border px-4 py-2 text-sm font-medium transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground hover:bg-muted"
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
};
