import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { getFeatureSettings } from "@/lib/api";

type Props = {
  feature: "kiosk" | "kitchen" | "customer_display";
  children: React.ReactElement;
};

export const FeatureRouteGuard = ({ feature, children }: Props) => {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getFeatureSettings()
      .then((settings) => {
        if (feature === "kiosk") setEnabled(settings.kioskEnabled);
        else if (feature === "kitchen") setEnabled(settings.kitchenDisplayEnabled);
        else setEnabled(settings.customerDisplayEnabled);
      })
      .catch((error) => {
        const status = error instanceof Error && "status" in error ? (error as { status?: number }).status : undefined;
        console.warn("FEATURE_FLAGS_LOAD_FAILED", {
          status: status ?? null,
          non_blocking: true,
          keep_authenticated: true,
        });
        setEnabled(true);
      });
  }, [feature]);

  if (enabled === null) {
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Cargando...</div>;
  }

  if (!enabled) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-4">
        <p className="text-lg font-semibold">Esta función está deshabilitada desde Configuración.</p>
        <Button onClick={() => navigate("/")}>Volver al inicio</Button>
      </div>
    );
  }

  return children;
};
