import { useCallback, useState } from "react";

import { modeling3dApi } from "../api";
import type { ModelingExecutionResult, ModelingPlan, ModelingPlanEdit } from "../types";

/**
 * Hook that drives the in-chat approval/execution UX for the
 * `ModelingPlanCard` (Onda 4).
 *
 * It encapsulates the two-step pattern that the chat-stream handler
 * will eventually run server-side once the orchestrator is fully wired:
 *
 *   1. POST `/api/3d/plans/:id/approve` (approve | reject)
 *   2. POST `/api/3d/plans/:id/execute` (only on approve)
 *
 * Until the orchestrator drives this from the backend, the frontend
 * triggers both calls inline so users get end-to-end feedback. The hook
 * also keeps a small ``busy`` flag so the card can disable buttons
 * while a network round-trip is in flight, plus the last error message
 * for surface.
 *
 * Reject calls do not trigger execution — the chat returns to
 * discovery and the agent will produce a new plan on the next user
 * message.
 *
 * Retry: re-run `executePlan` on a previously-failed plan. Revise:
 * mark the plan rejected with a placeholder reason so the chat goes
 * back to discovery; the parent component can also catch this event
 * to suggest a follow-up prompt.
 */
export interface UseModelingPlanActionsResult {
  busy: boolean;
  error: string | null;
  /** Latest plan returned by the backend after approval/rejection.
   *  Useful for parents that want to mirror plan.status into UI state. */
  lastPlan: ModelingPlan | null;
  /** Latest execution result (only set after approve + execute). */
  lastExecution: ModelingExecutionResult | null;
  approve: (planId: string) => Promise<ModelingExecutionResult | null>;
  reject: (planId: string, reason: string) => Promise<ModelingPlan | null>;
  retry: (planId: string) => Promise<ModelingExecutionResult | null>;
  revise: (planId: string, reason?: string) => Promise<ModelingPlan | null>;
  /** P4: edita o plano antes da aprovação (etapas/rationale). */
  edit: (planId: string, payload: ModelingPlanEdit) => Promise<ModelingPlan | null>;
  reset: () => void;
}

const DEFAULT_REVISE_REASON =
  "Usuário pediu para revisar o plano; voltando para descoberta.";

export function useModelingPlanActions(): UseModelingPlanActionsResult {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPlan, setLastPlan] = useState<ModelingPlan | null>(null);
  const [lastExecution, setLastExecution] = useState<ModelingExecutionResult | null>(null);

  const wrap = useCallback(
    async <T,>(op: () => Promise<T>): Promise<T | null> => {
      setBusy(true);
      setError(null);
      try {
        return await op();
      } catch (exc) {
        const message = exc instanceof Error ? exc.message : "Falha de rede.";
        setError(message);
        return null;
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const approve = useCallback(
    async (planId: string) =>
      wrap(async () => {
        const approved = await modeling3dApi.approvePlan(planId);
        setLastPlan(approved);
        const execution = await modeling3dApi.executePlan(planId);
        setLastPlan(execution.plan);
        setLastExecution(execution);
        return execution;
      }),
    [wrap]
  );

  const reject = useCallback(
    async (planId: string, reason: string) =>
      wrap(async () => {
        const rejected = await modeling3dApi.rejectPlan(planId, reason);
        setLastPlan(rejected);
        setLastExecution(null);
        return rejected;
      }),
    [wrap]
  );

  const retry = useCallback(
    async (planId: string) =>
      wrap(async () => {
        const execution = await modeling3dApi.executePlan(planId);
        setLastPlan(execution.plan);
        setLastExecution(execution);
        return execution;
      }),
    [wrap]
  );

  const revise = useCallback(
    async (planId: string, reason: string = DEFAULT_REVISE_REASON) =>
      wrap(async () => {
        const rejected = await modeling3dApi.rejectPlan(planId, reason);
        setLastPlan(rejected);
        setLastExecution(null);
        return rejected;
      }),
    [wrap]
  );

  const edit = useCallback(
    async (planId: string, payload: ModelingPlanEdit) =>
      wrap(async () => {
        const edited = await modeling3dApi.editPlan(planId, payload);
        setLastPlan(edited);
        setLastExecution(null);
        return edited;
      }),
    [wrap]
  );

  const reset = useCallback(() => {
    setBusy(false);
    setError(null);
    setLastPlan(null);
    setLastExecution(null);
  }, []);

  return { busy, error, lastPlan, lastExecution, approve, reject, retry, revise, edit, reset };
}
