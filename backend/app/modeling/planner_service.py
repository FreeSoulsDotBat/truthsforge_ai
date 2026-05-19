"""High-level planning service extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
plan creation end-to-end: pick a planner model from the registry, call the
LLM (or the heuristic fallback), apply the safety policy, persist the
resulting plan and emit the ``modeling.plan_created`` audit event.

The :class:`ModelingService` facade keeps the same public methods
(``create_plan`` / ``create_plan_async``) and delegates here.

Observabilidade
---------------
Esta camada é o ponto onde o bug original aconteceu (modelo default era
``test/audit-cost-*`` sem ``provider_model_id`` válido, fazendo o LLM
falhar silenciosamente). Cada decisão crítica agora emite um evento no
``ModelingTracer``:

- ``planner.model_resolved`` (info) com o modelo escolhido + lista de
  candidatos rejeitados quando vários estavam disponíveis;
- ``planner.model_unavailable`` (error) quando nenhum modelo qualifica,
  com a razão de rejeição de cada candidato — pega o bug original na hora;
- ``planner.llm_request`` / ``planner.llm_response`` span (debug por
  padrão; ``planner.llm_request`` em level=info quando a flag
  ``modeling_debug_llm_trace`` é ativada);
- ``planner.llm_auth_error`` / ``.llm_timeout`` / ``.llm_invalid_response``
  / ``.llm_provider_error`` (error) em vez do antigo ``except Exception``
  cego — classificadas via ``classify_provider_exception``;
- ``planner.fallback_used`` (error) quando o resultado é heurístico,
  com o motivo persistido em ``ModelingPlan.fallback_reason``.

Além disso, ``logger.warning`` em falhas críticas foi promovido para
``logger.error(..., exc_info=True)`` para garantir stack trace.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    KnowledgeBase,
    ModelCapability,
    ModelConfig,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlannerSource,
    ModelingTraceLevel,
    ModelingTraceSource,
    ProviderName,
)
from app.llm_gateway.exceptions import (
    LLMAuthError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    classify_provider_exception,
)
from app.llm_gateway.gateway import LLMGateway
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.planner import (
    create_heuristic_plan,
    create_llm_plan,
    create_llm_plan_async,
)
from app.modeling.policy import apply_modeling_policy

logger = logging.getLogger(__name__)


# Mapa de subclasses de ``LLMProviderError`` para event_type específico.
# Quando o except cai aqui, escolhemos o event_type pelo tipo da exceção,
# garantindo trilhas distintas no trace para cada classe de falha.
_LLM_ERROR_EVENT_TYPES: dict[type[LLMProviderError], str] = {
    LLMAuthError: "planner.llm_auth_error",
    LLMTimeoutError: "planner.llm_timeout",
    LLMRateLimitError: "planner.llm_rate_limit",
    LLMInvalidResponseError: "planner.llm_invalid_response",
}


def _llm_error_event_type(exc: LLMProviderError) -> str:
    """Retorna o event_type específico ou ``planner.llm_provider_error`` genérico."""

    for cls, event_type in _LLM_ERROR_EVENT_TYPES.items():
        if isinstance(exc, cls):
            return event_type
    return "planner.llm_provider_error"


class ModelingPlannerService:
    """Builds, validates and persists modeling plans.

    Why a dedicated service rather than free functions: the v1 implementation
    embedded planner-model resolution, knowledge-base lookup, fallback policy
    and audit emission inside ``ModelingService``. Pulling them apart lets
    the chat-first orchestrator added in Onda 2 wire the planner into the
    new ``3d.propose_plan`` and ``3d.propose_edit_plan`` tools without
    pulling in the entire service surface.
    """

    def __init__(self, store: Any, gateway: LLMGateway | None = None) -> None:
        self.store = store
        self.gateway = gateway or LLMGateway()
        # Tracer compartilhado — store injetada lazy na primeira chamada.
        self._tracer = get_tracer(store if hasattr(store, "record_trace_events_bulk") else None)

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def create_plan(self, payload: ModelingPlanCreate) -> ModelingPlan:
        """Synchronous plan creation. Mirrors ``ModelingService.create_plan``."""

        plan, source, fallback_reason = self._build_plan(payload)
        plan = plan.model_copy(
            update={"planner_source": source, "fallback_reason": fallback_reason}
        )
        return self._persist_plan(plan, source, fallback_reason)

    async def create_plan_async(self, payload: ModelingPlanCreate) -> ModelingPlan:
        """Async plan creation. Mirrors ``ModelingService.create_plan_async``."""

        plan, source, fallback_reason = await self._build_plan_async(payload)
        plan = plan.model_copy(
            update={"planner_source": source, "fallback_reason": fallback_reason}
        )
        return self._persist_plan(plan, source, fallback_reason)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _persist_plan(
        self,
        plan: ModelingPlan,
        source: ModelingPlannerSource,
        fallback_reason: str | None,
    ) -> ModelingPlan:
        plan = apply_modeling_policy(plan)
        self.store.upsert_modeling_plan(plan)

        # Bind plan_id no contexto para que eventos subsequentes herdem.
        self._tracer.bind_plan(plan.id)

        # Emite trace event de fallback se aplicável (mais loud que só o
        # campo em ModelingPlan, que ninguém lia antes desta refatoração).
        if source == ModelingPlannerSource.heuristic and fallback_reason:
            self._tracer.record(
                "planner.fallback_used",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.error,
                message="Plano heurístico foi usado em vez de LLM",
                payload={
                    "plan_id": plan.id,
                    "fallback_reason": fallback_reason,
                    "step_count": len(plan.steps),
                },
            )

        metadata: dict[str, Any] = {
            "plan_id": plan.id,
            "software": plan.software_choice.value,
            "step_count": len(plan.steps),
            "mode": plan.mode.value,
            "kind": plan.kind.value,
            "planner_source": source.value,
        }
        if fallback_reason:
            metadata["fallback_reason"] = fallback_reason

        # Anexa trace_id ao audit event âncora — permite navegar do audit
        # de compliance/custo para o trace de debug completo.
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_created",
                metadata=metadata,
                trace_id=current_trace_id(),
            ),
        )
        return plan

    def _build_plan(
        self, payload: ModelingPlanCreate
    ) -> tuple[ModelingPlan, ModelingPlannerSource, str | None]:
        model = self._resolve_planner_model()
        if model is None:
            return (
                create_heuristic_plan(payload),
                ModelingPlannerSource.heuristic,
                "planner_model_unavailable",
            )
        try:
            knowledge_bases = self._resolve_knowledge_bases(payload.knowledge_base_ids)
            with self._tracer.record_span(
                "planner.llm_request",
                source=ModelingTraceSource.backend,
                payload=self._build_llm_request_payload(model, payload),
            ) as span:
                plan = create_llm_plan(
                    payload,
                    gateway=self.gateway,
                    model=model,
                    knowledge_bases=knowledge_bases,
                )
                span.attach({"step_count": len(plan.steps), "kind": plan.kind.value})
            return plan, ModelingPlannerSource.llm, None
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            classified = self._classify_and_record_llm_error(exc, model)
            return (
                create_heuristic_plan(payload),
                ModelingPlannerSource.heuristic,
                str(classified),
            )

    async def _build_plan_async(
        self, payload: ModelingPlanCreate
    ) -> tuple[ModelingPlan, ModelingPlannerSource, str | None]:
        model = self._resolve_planner_model()
        if model is None:
            return (
                create_heuristic_plan(payload),
                ModelingPlannerSource.heuristic,
                "planner_model_unavailable",
            )
        try:
            knowledge_bases = self._resolve_knowledge_bases(payload.knowledge_base_ids)
            with self._tracer.record_span(
                "planner.llm_request",
                source=ModelingTraceSource.backend,
                payload=self._build_llm_request_payload(model, payload),
            ) as span:
                plan = await create_llm_plan_async(
                    payload,
                    gateway=self.gateway,
                    model=model,
                    knowledge_bases=knowledge_bases,
                )
                span.attach({"step_count": len(plan.steps), "kind": plan.kind.value})
            return plan, ModelingPlannerSource.llm, None
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            classified = self._classify_and_record_llm_error(exc, model)
            return (
                create_heuristic_plan(payload),
                ModelingPlannerSource.heuristic,
                str(classified),
            )

    def _classify_and_record_llm_error(
        self, exc: BaseException, model: ModelConfig
    ) -> LLMProviderError:
        """Traduz exceção genérica para tipada e emite event apropriado.

        Também promove o antigo ``logger.warning`` para ``logger.error``
        com ``exc_info=True`` — sem stack trace o debug era cego.
        """

        if isinstance(exc, LLMProviderError):
            classified = exc
        else:
            classified = classify_provider_exception(exc)

        event_type = _llm_error_event_type(classified)
        logger.error(
            "Planner LLM falhou (%s); usando fallback heurístico.",
            classified,
            exc_info=exc,
        )
        self._tracer.record(
            event_type,
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.error,
            message=str(classified) or classified.__class__.__name__,
            payload={
                "model_id": model.id,
                "provider": model.provider.value,
                "provider_model_id": model.provider_model_id,
                "exception_type": exc.__class__.__name__,
                "retryable": classified.retryable,
                "provider_error_code": classified.provider_error_code,
            },
        )
        return classified

    def _build_llm_request_payload(
        self, model: ModelConfig, payload: ModelingPlanCreate
    ) -> dict[str, Any]:
        """Monta o payload do trace event ``planner.llm_request``.

        Quando a flag ``modeling_debug_llm_trace`` é ``true``, inclui o
        prompt completo do usuário. Senão, só metadata (id do modelo,
        número de KBs, hash do prompt). Mantém o trace utilizável mesmo
        com privacidade — saber QUE houve um request é suficiente sem o
        conteúdo.
        """

        out: dict[str, Any] = {
            "model_id": model.id,
            "provider": model.provider.value,
            "provider_model_id": model.provider_model_id,
            "knowledge_base_count": len(payload.knowledge_base_ids or []),
            "mode": payload.mode.value if payload.mode else None,
        }
        if settings.modeling_debug_llm_trace:
            out["prompt"] = payload.prompt
            out["assumptions"] = list(payload.assumptions or [])
        else:
            out["prompt_length"] = len(payload.prompt or "")
        return out

    def _resolve_planner_model(self) -> ModelConfig | None:
        """Resolve modelo para o planner LLM, emitindo trace events com diagnóstico.

        Antes desta refatoração, retornava ``None`` silenciosamente quando
        não havia candidato — exatamente o caso do bug original (modelo
        default era ``test/audit-cost-*`` que falhava na chamada). Agora
        cada decisão é registrada com a lista de candidatos e razão de
        rejeição.
        """

        if not hasattr(self.store, "list_models"):
            return None
        all_models = list(self.store.list_models())
        enabled = [m for m in all_models if m.enabled]
        chat_models = [
            m
            for m in enabled
            if ModelCapability.chat in m.capabilities and m.provider == ProviderName.openai
        ]
        if not chat_models:
            self._tracer.record(
                "planner.model_unavailable",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.error,
                message="Nenhum modelo OpenAI com capability chat habilitado",
                payload={
                    "total_models": len(all_models),
                    "enabled_models": len(enabled),
                    "openai_chat_candidates": 0,
                },
            )
            return None

        default = next((m for m in chat_models if m.default), None)
        chosen = default or chat_models[0]

        # Bloqueio do bug original: modelo "default" sem provider_model_id
        # válido (placeholder ou modelo de teste fake). Em produção
        # (allow_dev_llm=False) isso é tratado como indisponibilidade
        # explícita; em dev (true) o gateway tentará mesmo assim e
        # falhará no boundary do provider, onde será capturado.
        if not chosen.provider_model_id and not settings.allow_dev_llm:
            self._tracer.record(
                "planner.model_unavailable",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.error,
                message=(
                    "Modelo default sem provider_model_id e allow_dev_llm=False "
                    "— rejeitando para forçar correção de configuração."
                ),
                payload={
                    "chosen_model_id": chosen.id,
                    "chosen_default": chosen.default,
                    "candidates": [
                        {
                            "id": m.id,
                            "provider_model_id": m.provider_model_id,
                            "default": m.default,
                            "rejection_reason": (
                                "missing_provider_model_id" if not m.provider_model_id else None
                            ),
                        }
                        for m in chat_models
                    ],
                },
            )
            return None

        self._tracer.record(
            "planner.model_resolved",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info,
            message=f"Planner usará modelo {chosen.id}",
            payload={
                "model_id": chosen.id,
                "provider": chosen.provider.value,
                "provider_model_id": chosen.provider_model_id,
                "default": chosen.default,
                "candidate_count": len(chat_models),
            },
        )
        return chosen

    def _resolve_knowledge_bases(self, knowledge_base_ids: list[str]) -> list[KnowledgeBase]:
        if not knowledge_base_ids or not hasattr(self.store, "list_knowledge_bases"):
            return []
        known = {kb.id: kb for kb in self.store.list_knowledge_bases()}
        return [known[item] for item in knowledge_base_ids if item in known]


__all__ = ["ModelingPlannerService"]
