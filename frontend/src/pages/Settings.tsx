import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";
import { FeatureFlagsTab } from "@/components/settings/FeatureFlagsTab";
import { OrderTypesTab } from "@/components/settings/OrderTypesTab";
import { PageLayout } from "@/components/layout/PageLayout";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");

  return (
    <PageLayout
      title="Configuración"
      subtitle="Gestiona usuarios, horarios del personal y funciones avanzadas del sistema."
    >

          <PageTabs
            tabs={[
              { label: "Empleados", value: "employees" },
              { label: "Horarios", value: "schedules" },
              { label: "Funciones", value: "features" },
              { label: "Tipos de Pedido", value: "order-types" },
            ]}
            activeValue={activeTab}
            onChange={setActiveTab}
          />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsContent value="employees">
              <EmployeesTab />
            </TabsContent>

            <TabsContent value="schedules">
              <SchedulesTab />
            </TabsContent>

            <TabsContent value="features">
              <FeatureFlagsTab />
            </TabsContent>

            <TabsContent value="order-types">
              <OrderTypesTab />
            </TabsContent>
          </Tabs>
    </PageLayout>
  );
};

export default Settings;
