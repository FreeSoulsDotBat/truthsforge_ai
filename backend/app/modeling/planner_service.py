"""High-level planning service extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
plan creation end-to-end: pick a planner model from the registry, call the
LLM (or the heuristic fallback), apply the safety policy, persist the
resulting plan and emit the ``modeling.plan_created`` audit event.

The :class:`ModelingService` facade keeps the same public methods
(``create_plan`` / ``create_plan_async``) and delegates here.
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
    ProviderName,
)
from app.llm_gateway.gateway import LLMGateway
from app.modeling.planner import (
    create_heuristic_plan,
    create_llm_plan,
    create_llm_plan_async,
)
from app.modeling.policy import apply_modeling_policy

logger = logging.getLogger(__name__)


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
        self.store.add_audit_event(
            AuditEvent(event_type="modeling.plan_created", metadata=metadata),
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
            plan = create_llm_plan(
                payload,
                gateway=self.gateway,
                model=model,
                knowledge_bases=knowledge_bases,
            )
            return plan, ModelingPlannerSource.llm, None
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            logger.warning("Planner LLM falhou (%s); usando fallback heurístico.", exc)
            return create_heuristic_plan(payload), ModelingPlannerSource.heuristic, str(exc)

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
            plan = await create_llm_plan_async(
                payload,
                gateway=self.gateway,
                model=model,
                knowledge_bases=knowledge_bases,
            )
            return plan, ModelingPlannerSource.llm, None
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            logger.warning("Planner LLM falhou (%s); usando fallback heurístico.", exc)
            return create_heuristic_plan(payload), ModelingPlannerSource.heuristic, str(exc)

    def _resolve_planner_model(self) -> ModelConfig | None:
        if not hasattr(self.store, "list_models"):
            return None
        models = [model for model in self.store.list_models() if model.enabled]
        if not models:
            return None
        chat_models = [
            model
            for model in models
            if ModelCapability.chat in model.capabilities
            and model.provider == ProviderName.openai
        ]
        if not chat_models:
            return None
        default = next((model for model in chat_models if model.default), None)
        chosen = default or chat_models[0]
        # When the model id is unresolved (no provider_model_id) and we're not
        # in allow_dev_llm mode, surface that as "unavailable" so we fall back.
        if not chosen.provider_model_id and not settings.allow_dev_llm:
            return None
        return chosen

    def _resolve_knowledge_bases(self, knowledge_base_ids: list[str]) -> list[KnowledgeBase]:
        if not knowledge_base_ids or not hasattr(self.store, "list_knowledge_bases"):
            return []
        known = {kb.id: kb for kb in self.store.list_knowledge_bases()}
        return [known[item] for item in knowledge_base_ids if item in known]


__all__ = ["ModelingPlannerService"]
