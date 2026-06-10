import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { modeling3dApi } from "../api";
import type { ModelingExecutionResult, ModelingPlan, ModelingPlanStatus } from "../types";
import { useModelingPlanActions } from "./useModelingPlanActions";

vi.mock("../api", () => ({
  modeling3dApi: {
    approvePlan: vi.fn(),
    executePlan: vi.fn(),
    getPlan: vi.fn()
  }
}));

const api = modeling3dApi as unknown as {
  approvePlan: ReturnType<typeof vi.fn>;
  executePlan: ReturnType<typeof vi.fn>;
  getPlan: ReturnType<typeof vi.fn>;
};

function plan(status: ModelingPlanStatus): ModelingPlan {
  return {
    id: "p1",
    status,
    steps: [{ id: "s1", status: "completed" }]
  } as unknown as ModelingPlan;
}

const netError = () => new TypeError("Failed to fetch");

describe("useModelingPlanActions — recuperação de queda de rede no execute", () => {
  beforeEach(() => vi.clearAllMocks());

  it("recupera quando a conexão cai mas o backend concluiu", async () => {
    api.approvePlan.mockResolvedValue(plan("approved"));
    api.executePlan.mockRejectedValue(netError());
    api.getPlan.mockResolvedValue(plan("completed")); // backend terminou apesar da queda

    const { result } = renderHook(() => useModelingPlanActions());
    let exec: Awaited<ReturnType<typeof result.current.approve>> = null;
    await act(async () => {
      exec = await result.current.approve("p1");
    });

    // O `exec` é reatribuído dentro do closure do `act`; o CFA externo não
    // enxerga a escrita e estreita p/ `null`. O cast restaura a união real.
    expect((exec as ModelingExecutionResult | null)?.plan.status).toBe("completed");
    expect(result.current.error).toBeNull(); // NÃO mostra "falhou"
  });

  it("reporta falha quando o backend de fato falhou", async () => {
    api.approvePlan.mockResolvedValue(plan("approved"));
    api.executePlan.mockRejectedValue(netError());
    api.getPlan.mockResolvedValue(plan("failed"));

    const { result } = renderHook(() => useModelingPlanActions());
    await act(async () => {
      await result.current.approve("p1");
    });

    expect(result.current.error).toBeTruthy();
  });

  it("propaga erro HTTP real do execute sem reconsultar (não é queda de rede)", async () => {
    api.approvePlan.mockResolvedValue(plan("approved"));
    api.executePlan.mockRejectedValue(new Error("API /execute returned 500"));

    const { result } = renderHook(() => useModelingPlanActions());
    await act(async () => {
      await result.current.approve("p1");
    });

    expect(result.current.error).toContain("500");
    expect(api.getPlan).not.toHaveBeenCalled(); // erro HTTP ≠ rede → não reconcilia
  });
});
