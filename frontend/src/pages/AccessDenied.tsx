import { Navigation } from "@/components/Navigation";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

const AccessDenied = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-4">
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <h1 className="text-2xl sm:text-3xl font-bold">Acceso denegado</h1>
          <p className="text-muted-foreground">
            No tienes permisos para ver esta sección. Contacta a un administrador si necesitas acceso.
          </p>
          <Button onClick={() => navigate("/")}>Volver al inicio</Button>
        </div>
      </div>
    </div>
  );
};

export default AccessDenied;
