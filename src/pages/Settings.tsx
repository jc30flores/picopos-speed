import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { AttendanceTab } from "@/components/settings/AttendanceTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl sm:text-3xl font-bold mb-6">Control de Empleados</h1>
          
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-6">
              <TabsTrigger value="employees">Empleados</TabsTrigger>
              <TabsTrigger value="attendance">Asistencia</TabsTrigger>
              <TabsTrigger value="schedules">Horarios</TabsTrigger>
            </TabsList>

            <TabsContent value="employees">
              <EmployeesTab />
            </TabsContent>

            <TabsContent value="attendance">
              <AttendanceTab />
            </TabsContent>

            <TabsContent value="schedules">
              <SchedulesTab />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default Settings;
