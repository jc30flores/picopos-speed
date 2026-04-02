import { Navigation } from "@/components/Navigation";
import { CashHistoryTab } from "@/components/reports/CashHistoryTab";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";

const RegistrosCaja = () => {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="px-4 pb-8 pt-4">
        <div className="mx-auto max-w-7xl">
          <div className="mb-4 space-y-1">
            <h1 className="text-2xl font-bold sm:text-3xl">Registros</h1>
            <p className="text-sm text-muted-foreground">Historial de cierres y diferencias de caja.</p>
          </div>
          <RegistrosTabs />
          <CashHistoryTab />
        </div>
      </div>
    </div>
  );
};

export default RegistrosCaja;
