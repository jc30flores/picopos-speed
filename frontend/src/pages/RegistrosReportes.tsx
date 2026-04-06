import { PageLayout } from "@/components/layout/PageLayout";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";
import { RegistrosReportesTab } from "@/components/reports/RegistrosReportesTab";

const RegistrosReportes = () => {
  return (
    <PageLayout title="Registros" subtitle="Análisis visual de ventas y comportamiento del negocio.">
      <RegistrosTabs />
      <RegistrosReportesTab />
    </PageLayout>
  );
};

export default RegistrosReportes;
