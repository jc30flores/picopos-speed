import { CashHistoryTab } from "@/components/reports/CashHistoryTab";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";
import { PageLayout } from "@/components/layout/PageLayout";

const RegistrosCaja = () => {
  return (
    <PageLayout title="Reportes" subtitle="Cierres y diferencias de caja.">
          <RegistrosTabs />
          <CashHistoryTab />
    </PageLayout>
  );
};

export default RegistrosCaja;
