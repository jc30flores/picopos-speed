import { SalesHistoryTab } from "@/components/reports/SalesHistoryTab";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";
import { PageLayout } from "@/components/layout/PageLayout";

const RegistrosVentas = () => {
  return (
    <PageLayout title="Reportes" subtitle="Historial de ventas y movimientos de caja.">
          <RegistrosTabs />
          <SalesHistoryTab />
    </PageLayout>
  );
};

export default RegistrosVentas;
