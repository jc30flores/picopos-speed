import { PageLayout } from "@/components/layout/PageLayout";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";
import DTEPage from "./DTE";

const RegistrosDTE = () => {
  return (
    <PageLayout title="Reportes" subtitle="Documentos tributarios electrónicos.">
      <RegistrosTabs />
      <DTEPage embedded />
    </PageLayout>
  );
};

export default RegistrosDTE;
