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
  /** T3.6: desfaz a última edição (rollback da timeline ao ponto pré-edição). */
  rollback: (planId: string) => Promise<ModelingExecutionResult | null>;
  revise: (planId: string, reason?: string) => Promise<ModelingPlan | null>;
  /** P4: edita o plano antes da aprovação (etapas/rationale). */
  edit: (planId: string, payload: ModelingPlanEdit) => Promise<ModelingPlan | null>;
  reset: () => void;
}

const DEFAULT_REVISE_REASON = "Usuário pediu para revisar o plano; voltando para descoberta.";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * `fetch` rejeita com `TypeError` ("Failed to fetch") em falha de REDE — conexão
 * caiu/resetou (ex.: backend lento ou `uvicorn --reload` reiniciando no meio da
 * request). É diferente de um erro HTTP (4xx/5xx), que chega como `Error` com a
 * mensagem do `detail`. Só no caso de rede vale reconciliar o status do plano.
 */
function isNetworkError(exc: unknown): boolean {
  if (exc instanceof TypeError) return true;
  const msg = exc instanceof Error ? exc.message.toLowerCase() : "";
  return msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("load failed");
}

/**
 * Executa o plano e, se a CONEXÃO cair (mas o backend puder ter concluído),
 * reconcilia: faz poll do status do plano por alguns segundos. Se o backend
 * terminou (`completed`), devolve um resultado sintético de sucesso em vez de
 * propagar "Failed to fetch" — corrige o "a UI diz que falhou mas a peça saiu
 * certa". Se o plano de fato falhou, propaga o erro real; se não dá pra
 * confirmar, propaga o erro de rede original.
 */
async function executePlanWithRecovery(planId: string): Promise<ModelingExecutionResult> {
  try {
    return await modeling3dApi.executePlan(planId);
  } catch (exc) {
    if (!isNetworkError(exc)) throw exc;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        const plan = await modeling3dApi.getPlan(planId);
        if (plan.status === "completed") {
          return {
            plan,
            executed_step_ids: plan.steps.filter((s) => s.status === "completed").map((s) => s.id),
            blocked_step_ids: plan.steps.filter((s) => s.status !== "completed").map((s) => s.id),
            events: ["A conexão caiu durante a execução, mas o backend concluiu — recuperado."],
            tool_call_ids: []
          };
        }
        if (plan.status === "failed" || plan.status === "rejected") {
          throw new Error("A execução do plano falhou no backend.", { cause: exc });
        }
      } catch (probe) {
        if (!isNetworkError(probe)) throw probe; // erro real ao reconsultar
      }
      await sleep(1500); // ainda em execução: espera o backend terminar
    }
    throw exc; // não deu pra confirmar conclusão — mantém o erro de rede
  }
}

export function useModelingPlanActions(): UseModelingPlanActionsResult {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPlan, setLastPlan] = useState<ModelingPlan | null>(null);
  const [lastExecution, setLastExecution] = useState<ModelingExecutionResult | null>(null);

  const wrap = useCallback(async <T>(op: () => Promise<T>): Promise<T | null> => {
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
  }, []);

  const approve = useCallback(
    async (planId: string) =>
      wrap(async () => {
        // fe-modeling-3: não persistir estado parcial (approved/running) antes
        // da execução concluir. Se executePlan falhar, `wrap` retorna null e o
        // card permanece em waiting_approval em vez de divergir para um estado
        // pós-aprovação que sugeriria sucesso e induziria re-execução.
        await modeling3dApi.approvePlan(planId);
        const execution = await executePlanWithRecovery(planId);
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
        const execution = await executePlanWithRecovery(planId);
        setLastPlan(execution.plan);
        setLastExecution(execution);
        return execution;
      }),
    [wrap]
  );

  const rollback = useCallback(
    async (planId: string) =>
      wrap(async () => {
        const execution = await modeling3dApi.rollbackPlan(planId);
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

  return {
    busy,
    error,
    lastPlan,
    lastExecution,
    approve,
    reject,
    retry,
    rollback,
    revise,
    edit,
    reset
  };
}
