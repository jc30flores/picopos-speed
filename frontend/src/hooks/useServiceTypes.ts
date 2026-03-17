import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { ServiceType, getServiceTypes } from "@/lib/api";

export const SERVICE_TYPES_QUERY_KEY = ["service-types"];

export const useServiceTypes = () => {
  const query = useQuery({
    queryKey: SERVICE_TYPES_QUERY_KEY,
    queryFn: getServiceTypes,
    staleTime: 1000 * 60 * 5,
  });

  const serviceTypes = useMemo(
    () => [...(query.data ?? [])].sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.label.localeCompare(b.label)),
    [query.data],
  );

  const activeServiceTypes = useMemo(() => serviceTypes.filter((item) => item.isActive !== false), [serviceTypes]);

  return {
    ...query,
    serviceTypes,
    activeServiceTypes,
  } as typeof query & { serviceTypes: ServiceType[]; activeServiceTypes: ServiceType[] };
};
