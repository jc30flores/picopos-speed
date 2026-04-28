import { PageLayout } from "@/components/layout/PageLayout";
import { EmployeeHoursTab } from "@/components/reports/EmployeeHoursTab";
import { RegistrosTabs } from "@/components/reports/RegistrosTabs";

const RegistrosEmpleados = () => {
  return (
    <PageLayout title="Reportes" subtitle="Horas trabajadas y descansos del personal.">
      <RegistrosTabs />
      <EmployeeHoursTab />
    </PageLayout>
  );
};

export default RegistrosEmpleados;
