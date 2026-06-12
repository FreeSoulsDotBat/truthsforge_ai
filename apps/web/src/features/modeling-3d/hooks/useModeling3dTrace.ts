import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";

import { modeling3dApi } from "../api";
import type { ModelingTraceEvent, ModelingTraceEventCreate } from "../../../types/api";

/**
 * Hook que consulta o trace de modelagem 3D associado a um plano.
 *
 * Tem dois modos de uso:
 * - Quando o card SSE entrega ``trace_id`` no metadata do plano: passe
 *   ``traceId`` para usar o endpoint ``/api/3d/traces/{trace_id}`` (mais
 *   barato — não filtra no banco por plan_id).
 * - Quando só o ``planId`` está disponível (ex: histórico): passe
 *   ``planId`` e o hook usa ``/api/3d/plans/{plan_id}/trace``.
 *
 * Para refresh em tempo real, o frontend pode invalidar a query ao
 * receber eventos SSE ``modeling_trace_event``; nesta iteração ficamos
 * só com polling on-demand quando o modal está aberto (staleTime curto).
 */
export function useModeling3dTrace(
  planId?: string | null,
  traceId?: string | null,
  options: { enabled?: boolean } = {}
) {
  const enabled = options.enabled !== false && Boolean(planId || traceId);
  return useQuery({
    queryKey: ["modeling-3d-trace", traceId ?? "", planId ?? ""],
    queryFn: async (): Promise<ModelingTraceEvent[]> => {
      if (traceId) {
        return modeling3dApi.trace(traceId);
      }
      if (planId) {
        return modeling3dApi.planTrace(planId);
      }
      return [];
    },
    enabled,
    staleTime: 5_000
  });
}

/**
 * Devolve um callback ``recordEvent`` que posta eventos UI no backend.
 * Aplica debounce simples — eventos UI tendem a vir em rajada (modal
 * aberto, foco mudou, etc.) e não queremos saturar o rate limit do
 * endpoint (60/min por IP).
 *
 * Falhas são silenciadas: observabilidade não pode quebrar o fluxo do
 * usuário. Use o console do navegador para verificar quando suspeitar.
 */
export function useRecordClientTrace(traceId?: string | null, planId?: string | null) {
  return useCallback(
    (
      eventType: string,
      payload: Record<string, unknown> = {},
      options: { level?: "info" | "warn" | "error" | "debug"; message?: string } = {}
    ) => {
      if (!traceId) return;
      modeling3dApi
        .recordClientTraceEvent({
          trace_id: traceId,
          plan_id: planId ?? null,
          event_type: eventType,
          level: options.level ?? "info",
          message: options.message ?? null,
          payload
        })
        .catch((error) => {
          // Silenciado — apenas console pra debug. Não exibe pra UI.

          console.debug("[trace] failed to record client event:", eventType, error);
        });
    },
    [traceId, planId]
  );
}

export type { ModelingTraceEvent, ModelingTraceEventCreate };
