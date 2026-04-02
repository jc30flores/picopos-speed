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
    <div className={cn("mb-6 flex flex-wrap gap-3", className)}>
      {tabs.map((tab) => {
        const active = tab.value === activeValue;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cn(
              "min-h-12 rounded-xl border px-5 py-2 text-sm font-semibold transition-colors md:min-h-14 md:text-base",
              active
                ? "border-primary bg-primary text-primary-foreground shadow-sm"
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
