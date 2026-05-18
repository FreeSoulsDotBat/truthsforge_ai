import { useQuery } from "@tanstack/react-query";

import { modeling3dApi } from "../api";
import type { Modeling3DDiagnostics } from "../types";

export function useModeling3dDiagnostics(planId?: string | null, projectId?: string | null) {
  return useQuery({
    queryKey: ["modeling-3d-diagnostics", planId ?? "__none__", projectId ?? "__all__"],
    queryFn: async (): Promise<Modeling3DDiagnostics> => {
      const [capabilities, plans, toolCalls, printabilityReports, modelVersions] = await Promise.all([
        modeling3dApi.capabilities(),
        modeling3dApi.plans(),
        planId ? modeling3dApi.toolCalls({ plan_id: planId, limit: 50 }) : Promise.resolve([]),
        planId ? modeling3dApi.printabilityReports({ plan_id: planId }) : Promise.resolve([]),
        modeling3dApi.modelVersions(projectId ? { project_id: projectId } : {})
      ]);
      return { capabilities, plans, toolCalls, printabilityReports, modelVersions };
    },
    staleTime: 10_000
  });
}
