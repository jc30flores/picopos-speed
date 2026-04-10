import { PageLayout } from "@/components/layout/PageLayout";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";
import { RegistrosReportesTab } from "@/components/reports/RegistrosReportesTab";

const RegistrosReportes = () => {
  return (
    <PageLayout title="Reportes" subtitle="Vista consolidada de ventas y desempeño.">
      <RegistrosTabs />
      <RegistrosReportesTab />
    </PageLayout>
  );
};

export default RegistrosReportes;
