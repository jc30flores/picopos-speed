import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";
import { FeatureFlagsTab } from "@/components/settings/FeatureFlagsTab";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-4">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6 space-y-1">
            <h1 className="text-2xl sm:text-3xl font-bold">Configuración</h1>
            <p className="text-sm text-muted-foreground">
              Gestiona usuarios, horarios del personal y funciones avanzadas del sistema.
            </p>
          </div>
          
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-6">
              <TabsTrigger value="employees">Empleados</TabsTrigger>
              <TabsTrigger value="schedules">Horarios</TabsTrigger>
              <TabsTrigger value="features">Funciones</TabsTrigger>
            </TabsList>

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
