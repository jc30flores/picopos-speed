import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { FeatureFlag, getFeatureFlags, updateFeatureFlag } from "@/lib/api";

export const FeatureFlagsTab = () => {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());

  const orderedFlags = useMemo(() => {
    return [...flags].sort((a, b) => a.label.localeCompare(b.label));
  }, [flags]);

  const loadFlags = async () => {
    try {
      setIsLoading(true);
      const data = await getFeatureFlags();
      setFlags(data);
    } catch (error) {
      console.error("Failed to load feature flags", error);
      toast.error(error instanceof Error ? error.message : "No se pudieron cargar las funciones");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFlags();
  }, []);

  const handleToggle = async (flag: FeatureFlag, enabled: boolean) => {
    const previous = flag.isEnabled;
    setFlags((current) =>
      current.map((item) => (item.id === flag.id ? { ...item, isEnabled: enabled } : item))
    );
    setSavingIds((current) => new Set(current).add(flag.id));
    try {
      const updated = await updateFeatureFlag(flag.id, { isEnabled: enabled });
      setFlags((current) =>
        current.map((item) => (item.id === flag.id ? updated : item))
      );
      toast.success("Función actualizada");
    } catch (error) {
      console.error("Failed to update feature flag", error);
      setFlags((current) =>
        current.map((item) => (item.id === flag.id ? { ...item, isEnabled: previous } : item))
      );
      toast.error(error instanceof Error ? error.message : "No se pudo actualizar la función");
    } finally {
      setSavingIds((current) => {
        const next = new Set(current);
        next.delete(flag.id);
        return next;
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Funciones avanzadas</CardTitle>
        <CardDescription>
          Activa o desactiva módulos completos sin afectar el flujo actual de POS, cocina o reportes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <p className="text-sm text-muted-foreground">Cargando funciones...</p>}
        {!isLoading && orderedFlags.length === 0 && (
          <p className="text-sm text-muted-foreground">No hay funciones configuradas.</p>
        )}
        {!isLoading &&
          orderedFlags.map((flag) => {
            const isSaving = savingIds.has(flag.id);
            return (
              <div
                key={flag.id}
                className="flex flex-col gap-3 rounded-lg border border-border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-semibold text-foreground">{flag.label}</p>
                  {flag.description && (
                    <p className="text-xs text-muted-foreground">{flag.description}</p>
                  )}
                  <p className="text-xs text-muted-foreground">Clave: {flag.key}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {flag.isEnabled ? "Activo" : "Inactivo"}
                  </span>
                  <Switch
                    checked={flag.isEnabled}
                    onCheckedChange={(checked) => handleToggle(flag, checked)}
                    disabled={isSaving}
                    aria-label={`Activar ${flag.label}`}
                  />
                </div>
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
};
