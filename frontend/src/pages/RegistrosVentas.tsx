import { Navigation } from "@/components/Navigation";
import { SalesHistoryTab } from "@/components/reports/SalesHistoryTab";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";

const RegistrosVentas = () => {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="px-4 pb-8 pt-4">
        <div className="mx-auto max-w-7xl">
          <div className="mb-4 space-y-1">
            <h1 className="text-2xl font-bold sm:text-3xl">Registros</h1>
            <p className="text-sm text-muted-foreground">Consulta ventas y movimientos de caja.</p>
          </div>
          <RegistrosTabs />
          <SalesHistoryTab />
        </div>
      </div>
    </div>
  );
};

export default RegistrosVentas;
