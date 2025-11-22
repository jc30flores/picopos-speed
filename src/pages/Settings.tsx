import { Navigation } from "@/components/Navigation";

const Settings = () => {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-6">Configuración</h1>
          <p className="text-muted-foreground">Configuración del sistema (próximamente)</p>
        </div>
      </div>
    </div>
  );
};

export default Settings;
