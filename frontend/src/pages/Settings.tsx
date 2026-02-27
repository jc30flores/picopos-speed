import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";
import { FeatureFlagsTab } from "@/components/settings/FeatureFlagsTab";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="px-4 pb-4 pt-20">
        <div className="mx-auto max-w-7xl">
          <div className="mb-4 space-y-1">
            <h1 className="text-2xl font-bold sm:text-3xl">Configuración</h1>
            <p className="text-sm text-muted-foreground">
              Gestiona usuarios, horarios del personal y funciones avanzadas del sistema.
            </p>
          </div>

          <PageTabs
            tabs={[
              { label: "Empleados", value: "employees" },
              { label: "Horarios", value: "schedules" },
              { label: "Funciones", value: "features" },
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
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default Settings;
