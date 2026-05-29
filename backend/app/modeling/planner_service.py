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
    ModelingDiscoveryAssessment,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingPlannerSource,
    ModelingSubGoal,
    ModelingTraceLevel,
    ModelingTraceSource,
    ModelState,
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
from app.modeling.discovery import assess_request_async as assess_discovery_async
from app.modeling.discovery import heuristic_assessment
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.planner import (
    build_edit_context_block,
    correct_step,
    create_heuristic_plan,
    create_llm_plan,
    create_llm_plan_async,
    decompose_request,
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

    def create_plan(
        self, payload: ModelingPlanCreate, *, live_state_block: str | None = None
    ) -> ModelingPlan:
        """Synchronous plan creation. Mirrors ``ModelingService.create_plan``.

        T3.3: ``live_state_block`` carries the on-demand reconciliation block
        (live Fusion timeline read by the orchestrator before an edit). It is
        merged into the edit context so the planner parts from the real model
        state, not stale history.
        """

        plan, source, fallback_reason = self._build_plan(payload, live_state_block=live_state_block)
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
    # F2: decomposição hierárquica + planejamento por bloco
    # ------------------------------------------------------------------

    def decompose(self, payload: ModelingPlanCreate) -> list[ModelingSubGoal]:
        """F2 (T2.2): decompõe o pedido em sub-objetivos via LLM. Fallback
        gracioso: se o modelo não está disponível ou a chamada falha, retorna
        um único sub-objetivo = o pedido inteiro (degrada para o fluxo de
        bloco único, equivalente ao plano one-shot)."""

        model = self._resolve_planner_model()
        if model is None:
            return [ModelingSubGoal(seq=1, title="Modelo completo", description=payload.prompt)]
        try:
            with self._tracer.record_span(
                "planner.decompose",
                source=ModelingTraceSource.backend,
                payload={"model_id": model.id, "prompt_length": len(payload.prompt or "")},
            ) as span:
                sub_goals = decompose_request(payload, gateway=self.gateway, model=model)
                span.attach({"sub_goal_count": len(sub_goals)})
            self._tracer.record(
                "planner.decomposed",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.info,
                message=f"Decomposto em {len(sub_goals)} sub-objetivo(s).",
                payload={"titles": [sg.title for sg in sub_goals]},
            )
            return sub_goals
        except Exception as exc:  # noqa: BLE001 - fallback intencional
            self._classify_and_record_llm_error(exc, model)
            return [ModelingSubGoal(seq=1, title="Modelo completo", description=payload.prompt)]

    def plan_block_for_subgoal(
        self,
        sub_goal: ModelingSubGoal,
        *,
        base_payload: ModelingPlanCreate,
        parent_plan_id: str,
        model_state: ModelState | None,
        done_titles: list[str] | None = None,
    ) -> ModelingPlan:
        """F2 (T2.4): planeja o bloco de UM sub-objetivo como um plano kind=edit
        com ``parent_plan_id`` = primary, injetando o ``ModelState`` real
        (read-back do bloco anterior) + a descrição/critério do sub-objetivo no
        contexto. Reusa ``create_plan`` (build+persist+fallback heurístico)."""

        from app.modeling.model_state import render_model_state_block

        parts = [f"{sub_goal.title}: {sub_goal.description}".strip()]
        if sub_goal.acceptance:
            parts.append(f"Critério de aceitação: {sub_goal.acceptance}")
        block_prompt = "\n".join(parts)

        context_parts: list[str] = []
        state_block = render_model_state_block(model_state)
        if state_block:
            context_parts.append(state_block)
        if done_titles:
            context_parts.append("Sub-objetivos já concluídos: " + ", ".join(done_titles))
        live_block = "\n\n".join(context_parts) or None

        block_payload = base_payload.model_copy(
            update={
                "prompt": block_prompt,
                "kind": ModelingPlanKind.edit,
                "parent_plan_id": parent_plan_id,
            }
        )
        return self.create_plan(block_payload, live_state_block=live_block)

    async def assess_request_async(
        self,
        prompt: str,
        *,
        history: list[dict[str, str]] | None = None,
        software_override: Any = None,
        threshold: float | None = None,
        has_existing_model: bool = False,
    ) -> ModelingDiscoveryAssessment:
        """P2/P3: avalia se o pedido está pronto para planejar (e, quando já
        existe modelo, classifica intent edit/new_model/ambiguous). Reusa a
        resolução de modelo + gateway do planner. Em qualquer falha cai no
        fallback heurístico, que NÃO bloqueia o usuário.
        """

        effective_threshold = (
            threshold if threshold is not None else settings.modeling_discovery_confidence_threshold
        )
        model = self._resolve_planner_model()
        if model is None:
            return heuristic_assessment(prompt, history, has_existing_model=has_existing_model)
        try:
            with self._tracer.record_span(
                "discovery.assess",
                source=ModelingTraceSource.backend,
                payload={
                    "model_id": model.id,
                    "provider": model.provider.value,
                    "provider_model_id": model.provider_model_id,
                    "threshold": effective_threshold,
                    "history_len": len(history or []),
                    "prompt_length": len(prompt or ""),
                    "has_existing_model": has_existing_model,
                },
            ) as span:
                assessment = await assess_discovery_async(
                    prompt,
                    gateway=self.gateway,
                    model=model,
                    history=history,
                    software_override=software_override,
                    threshold=effective_threshold,
                    has_existing_model=has_existing_model,
                )
                span.attach(
                    {
                        "ready_to_plan": assessment.ready_to_plan,
                        "confidence": assessment.confidence,
                        "question_count": len(assessment.questions),
                        "intent": assessment.intent,
                    }
                )
            self._tracer.record(
                "discovery.assessed",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.info,
                message=(
                    "Pedido pronto para planejar"
                    if assessment.ready_to_plan
                    else f"Descoberta pediu {len(assessment.questions)} esclarecimento(s)"
                ),
                payload={
                    "ready_to_plan": assessment.ready_to_plan,
                    "confidence": assessment.confidence,
                    "question_count": len(assessment.questions),
                    "intent": assessment.intent,
                    "threshold": effective_threshold,
                },
            )
            return assessment
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            self._classify_and_record_llm_error(exc, model)
            return heuristic_assessment(prompt, history, has_existing_model=has_existing_model)

    def build_corrector(self, *, max_attempts: int = 5):
        """Fase 2: corretor de passo para o ``ModelingAgentLoop``.

        Resolve o modelo do planner e devolve um callable
        ``(step, output, attempt) -> ModelingPlanStep | None`` que usa o LLM
        (``planner.correct_step``) para corrigir o passo. Retorna ``None``
        quando não há modelo disponível **ou** quando a correção falha — o loop
        então esgota as iterações e reverte (RF-011).
        """

        model = self._resolve_planner_model()
        if model is None:
            return None

        def corrector(step: Any, output: dict[str, Any], attempt: int) -> Any:
            try:
                return correct_step(
                    step,
                    output,
                    attempt,
                    gateway=self.gateway,
                    model=model,
                    max_attempts=max_attempts,
                    verification=output.get("verification_divergence"),
                )
            except Exception as exc:  # noqa: BLE001 - falha de correção não estoura
                self._classify_and_record_llm_error(exc, model)
                return None

        return corrector

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

    def _resolve_edit_context(
        self, payload: ModelingPlanCreate, *, live_state_block: str | None = None
    ) -> str | None:
        """P5/T3.3: para planos de edição, monta o contexto do modelo atual.

        Combina o histórico registrado (``build_edit_context_block`` do
        plano-pai) com o ``live_state_block`` (leitura ao vivo do Fusion,
        reconciliação T3.2/T3.3). O bloco ao vivo vai por ÚLTIMO para que a
        instrução "parta do estado atual" seja a última lida pelo planner.
        Retorna None quando não é edição e não há leitura ao vivo."""

        if payload.kind != ModelingPlanKind.edit or not payload.parent_plan_id:
            return live_state_block
        recorded: str | None = None
        if hasattr(self.store, "get_modeling_plan"):
            try:
                parent = self.store.get_modeling_plan(payload.parent_plan_id)
            except Exception:
                parent = None
            recorded = build_edit_context_block(parent)
        if live_state_block and recorded:
            return f"{recorded}\n\n{live_state_block}"
        return live_state_block or recorded

    def _build_plan(
        self, payload: ModelingPlanCreate, *, live_state_block: str | None = None
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
            edit_context = self._resolve_edit_context(payload, live_state_block=live_state_block)
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
                    edit_context=edit_context,
                )
                span.attach(
                    {
                        "step_count": len(plan.steps),
                        "kind": plan.kind.value,
                        "edit_context": bool(edit_context),
                    }
                )
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
            edit_context = self._resolve_edit_context(payload)
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
                    edit_context=edit_context,
                )
                span.attach(
                    {
                        "step_count": len(plan.steps),
                        "kind": plan.kind.value,
                        "edit_context": bool(edit_context),
                    }
                )
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
            # Dump completo do payload do request. ``model_dump`` evita o
            # erro anterior onde eu tentei acessar ``payload.assumptions``
            # que existe em ``ModelingPlan`` (saída) mas não em
            # ``ModelingPlanCreate`` (entrada). Pegado em produção pela
            # própria observabilidade — fix-by-trace.
            try:
                out["payload_dump"] = payload.model_dump(mode="json")
            except Exception as exc:  # noqa: BLE001 - never crash on debug dump
                out["payload_dump_error"] = str(exc)
            out["prompt"] = payload.prompt
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
