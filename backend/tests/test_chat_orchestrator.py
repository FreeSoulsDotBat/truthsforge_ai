"""Tests for the chat-first orchestrator (Onda 2.4, ADR-013)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.contracts import (
    AuditEvent,
    ChatModelingStage,
    ChatSession,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.chat_orchestrator import (
    InvalidEditStage,
    ModelingChatOrchestrator,
    NotAModelingChat,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeStore:
    """Minimal in-memory store covering the surface the orchestrator hits."""

    chats: dict[str, ChatSession] = field(default_factory=dict)
    plans: dict[str, ModelingPlan] = field(default_factory=dict)
    audit_events: list[AuditEvent] = field(default_factory=list)

    def upsert_chat_session(self, chat: ChatSession) -> ChatSession:
        self.chats[chat.id] = chat
        return chat

    def get_modeling_plan(self, plan_id: str) -> ModelingPlan | None:
        return self.plans.get(plan_id)

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        self.plans[plan.id] = plan
        return plan

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        self.audit_events.append(event)
        return event


@dataclass
class _FakePlanner:
    """Stub planner that returns a plan built from the payload directly."""

    store: _FakeStore
    next_steps: list[ModelingPlanStep] = field(default_factory=list)
    # T3.3: captura o bloco de reconciliação que o orchestrator injeta.
    last_live_state_block: str | None = None

    def create_plan(
        self, payload: ModelingPlanCreate, *, live_state_block: str | None = None
    ) -> ModelingPlan:
        self.last_live_state_block = live_state_block
        steps = list(self.next_steps)
        plan = ModelingPlan(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            prompt=payload.prompt,
            mode=payload.mode,
            kind=payload.kind,
            parent_plan_id=payload.parent_plan_id,
            software_choice=payload.software_override or ModelingSoftware.blender,
            steps=steps,
            status=(
                ModelingPlanStatus.waiting_approval
                if any(step.approval_required for step in steps)
                else ModelingPlanStatus.approved
            ),
            approval_required=any(step.approval_required for step in steps),
        )
        self.store.upsert_modeling_plan(plan)
        return plan


@dataclass
class _FakeExecutor:
    """Stub executor that completes every step instantly with ``ok``."""

    store: _FakeStore
    fail: bool = False
    # T3.2/T3.6: controls the best-effort ``query_timeline`` probe in
    # ``_read_live_timeline`` (only invoked for fusion edits).
    probe_count: int | None = 7
    probe_features: list[dict[str, Any]] | None = None
    probe_ok: bool = True
    probe_raises: bool = False
    single_step_calls: list[ModelingPlanStep] = field(default_factory=list)

    def execute_plan(self, plan: ModelingPlan) -> ModelingExecutionResult:
        status = ModelingPlanStatus.failed if self.fail else ModelingPlanStatus.completed
        executed = [step.id for step in plan.steps]
        updated = plan.model_copy(update={"status": status})
        self.store.upsert_modeling_plan(updated)
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed,
            blocked_step_ids=[],
            events=[f"executed:{name}" for name in (s.tool_name for s in plan.steps)],
            tool_call_ids=[],
        )

    def _execute_single_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> Any:
        self.single_step_calls.append(step)
        if self.probe_raises:
            raise RuntimeError("fusion offline durante a captura")
        output: dict[str, Any] = (
            {} if self.probe_count is None else {"timeline_count": self.probe_count}
        )
        if self.probe_features is not None:
            output["timeline"] = self.probe_features
        return SimpleNamespace(
            step=step, output=output, tool_call_id=None, event="probe", ok=self.probe_ok
        )


def _make_chat(*, is_modeling_3d: bool = True, stage: Any = None) -> ChatSession:
    chat = ChatSession(
        title="Suporte para fone",
        is_modeling_3d=is_modeling_3d,
        modeling_stage=stage,
        modeling_software_preference=ModelingSoftware.blender if is_modeling_3d else None,
    )
    return chat


def _orchestrator(
    **kwargs: Any,
) -> tuple[ModelingChatOrchestrator, _FakeStore, _FakePlanner, _FakeExecutor]:
    store = _FakeStore()
    planner = _FakePlanner(store=store, next_steps=kwargs.get("planner_steps", []))
    executor = _FakeExecutor(
        store=store,
        fail=kwargs.get("execution_fails", False),
        probe_count=kwargs.get("probe_count", 7),
        probe_features=kwargs.get("probe_features"),
        probe_ok=kwargs.get("probe_ok", True),
        probe_raises=kwargs.get("probe_raises", False),
    )
    orch = ModelingChatOrchestrator(store=store, planner=planner, executor=executor)
    return orch, store, planner, executor


def _safe_step(seq: int, tool_name: str) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=seq,
        title=f"Etapa {seq}",
        software=ModelingSoftware.blender,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.pending,
    )


def _high_risk_step() -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=1,
        title="Aplicar boolean",
        software=ModelingSoftware.blender,
        tool_name="blender.apply_boolean",
        risk_level=ModelingRiskLevel.medium,
        approval_required=True,
        status=ModelingStepStatus.waiting_approval,
    )


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


def test_on_chat_created_marks_modeling_chat_as_discovery() -> None:
    orch, store, _, _ = _orchestrator()
    chat = _make_chat(is_modeling_3d=True, stage=None)
    store.chats[chat.id] = chat

    updated = orch.on_chat_created(chat)

    assert updated.modeling_stage is ChatModelingStage.discovery
    assert store.chats[updated.id].modeling_stage is ChatModelingStage.discovery
    event_types = [event.event_type for event in store.audit_events]
    assert "modeling.chat.discovery_started" in event_types


def test_on_chat_created_is_noop_for_non_modeling_chats() -> None:
    orch, _, _, _ = _orchestrator()
    chat = _make_chat(is_modeling_3d=False, stage=None)

    updated = orch.on_chat_created(chat)

    assert updated is chat
    assert updated.modeling_stage is None


def test_on_chat_created_is_idempotent_when_already_in_a_stage() -> None:
    orch, _, _, _ = _orchestrator()
    chat = _make_chat(is_modeling_3d=True, stage=ChatModelingStage.editing)

    updated = orch.on_chat_created(chat)

    # Already in a stage — orchestrator must not regress to discovery.
    assert updated.modeling_stage is ChatModelingStage.editing


# ---------------------------------------------------------------------------
# discovery & planning
# ---------------------------------------------------------------------------


def test_ask_clarification_keeps_chat_in_discovery() -> None:
    orch, store, _, _ = _orchestrator()
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat

    updated = orch.ask_clarification(chat, question="Qual a altura desejada?")

    assert updated.modeling_stage is ChatModelingStage.discovery
    assert any(
        event.event_type == "modeling.chat.clarification_asked" for event in store.audit_events
    )


def test_propose_plan_creates_primary_plan_and_moves_to_planning() -> None:
    orch, store, planner, _ = _orchestrator(
        planner_steps=[_safe_step(1, "blender.create_mesh_primitive")]
    )
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    payload = ModelingPlanCreate(prompt="cubo de 40mm")

    updated, plan = orch.propose_plan(chat, payload=payload)

    assert updated.modeling_stage is ChatModelingStage.planning
    assert updated.modeling_plan_id == plan.id
    assert plan.kind is ModelingPlanKind.primary
    assert plan.parent_plan_id is None
    assert plan.conversation_id == chat.id


def test_propose_plan_carries_software_preference_when_payload_omits_it() -> None:
    orch, store, planner, _ = _orchestrator(
        planner_steps=[_safe_step(1, "blender.create_mesh_primitive")]
    )
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat

    _, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="qualquer"))

    assert plan.software_choice is ModelingSoftware.blender  # from chat preference


# ---------------------------------------------------------------------------
# approval / rejection
# ---------------------------------------------------------------------------


def test_approve_plan_drives_through_executing_to_editing() -> None:
    orch, store, planner, _ = _orchestrator(
        planner_steps=[_safe_step(1, "blender.create_mesh_primitive")]
    )
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, approved_plan, execution = orch.approve_plan(chat, plan.id)

    assert chat.modeling_stage is ChatModelingStage.editing
    assert approved_plan.status is ModelingPlanStatus.completed
    assert execution.executed_step_ids == [step.id for step in plan.steps]


def test_approve_plan_falls_into_failed_when_execution_fails() -> None:
    orch, store, _, _ = _orchestrator(
        planner_steps=[_safe_step(1, "blender.create_mesh_primitive")],
        execution_fails=True,
    )
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, approved_plan, _ = orch.approve_plan(chat, plan.id)

    # DT-008: execução que falha cai no estágio distinto ``failed``.
    assert chat.modeling_stage is ChatModelingStage.failed
    assert approved_plan.status is ModelingPlanStatus.failed


def test_reject_plan_returns_to_discovery_and_clears_plan_id() -> None:
    orch, store, _, _ = _orchestrator(
        planner_steps=[_safe_step(1, "blender.create_mesh_primitive")]
    )
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, rejected = orch.reject_plan(chat, plan.id, reason="forma errada")

    assert chat.modeling_stage is ChatModelingStage.discovery
    assert chat.modeling_plan_id is None
    assert rejected.status is ModelingPlanStatus.rejected


# ---------------------------------------------------------------------------
# edit plans
# ---------------------------------------------------------------------------


def test_propose_edit_plan_auto_executes_when_no_high_risk() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    outcome = orch.propose_edit_plan(
        chat, payload=ModelingPlanCreate(prompt="suavizar com bevel 2mm")
    )

    assert outcome.requires_approval is False
    assert outcome.chat.modeling_stage is ChatModelingStage.editing
    assert outcome.plan.kind is ModelingPlanKind.edit
    assert outcome.plan.parent_plan_id == "m3d_plan_parent"
    assert outcome.execution is not None
    assert outcome.plan.status is ModelingPlanStatus.completed


def test_propose_edit_plan_captures_rollback_marker_for_fusion() -> None:
    orch, store, _, executor = _orchestrator(
        planner_steps=[_safe_step(1, "fusion.extrude_profile")],
        probe_count=5,
    )
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    outcome = orch.propose_edit_plan(
        chat,
        payload=ModelingPlanCreate(
            prompt="extrudar base 4mm", software_override=ModelingSoftware.fusion
        ),
    )

    # T3.6: a captura roda fusion.query_timeline ANTES da edição (fora de
    # plan.steps, para o loop nunca a ver) e grava a contagem no plano.
    assert [s.tool_name for s in executor.single_step_calls] == ["fusion.query_timeline"]
    assert outcome.plan.rollback_marker == 5
    assert store.plans[outcome.plan.id].rollback_marker == 5
    assert outcome.requires_approval is False


def test_propose_edit_plan_skips_rollback_capture_for_non_fusion() -> None:
    orch, store, _, executor = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    outcome = orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="bevel 2mm"))

    # Blender não tem timeline: nenhuma sondagem; marcador permanece None.
    assert executor.single_step_calls == []
    assert outcome.plan.rollback_marker is None


def test_propose_edit_plan_proceeds_when_rollback_capture_fails() -> None:
    orch, store, _, executor = _orchestrator(
        planner_steps=[_safe_step(1, "fusion.extrude_profile")],
        probe_raises=True,
    )
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    outcome = orch.propose_edit_plan(
        chat,
        payload=ModelingPlanCreate(
            prompt="extrudar base 4mm", software_override=ModelingSoftware.fusion
        ),
    )

    # A leitura falhou, mas a edição NÃO pode ser bloqueada por isso (best-effort).
    assert executor.single_step_calls  # tentou sondar
    assert outcome.requires_approval is False
    assert outcome.plan.status is ModelingPlanStatus.completed
    assert outcome.plan.rollback_marker is None


def test_propose_edit_plan_injects_live_state_into_planner_for_fusion() -> None:
    # T3.2/T3.3: o estado ao vivo do Fusion vira contexto do planner.
    orch, store, planner, _ = _orchestrator(
        planner_steps=[_safe_step(1, "fusion.chamfer_edges")],
        probe_count=2,
        probe_features=[
            {"index": 0, "name": "Extrude1", "type": "ExtrudeFeature", "suppressed": False},
            {"index": 1, "name": "Fillet1", "type": "FilletFeature", "suppressed": False},
        ],
    )
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    orch.propose_edit_plan(
        chat,
        payload=ModelingPlanCreate(
            prompt="chanfrar arestas", software_override=ModelingSoftware.fusion
        ),
    )

    block = planner.last_live_state_block
    assert block is not None
    assert "estado-atual-fusion" in block
    assert "FONTE DE VERDADE" in block
    assert "Extrude1" in block
    assert "Fillet1" in block


def test_propose_edit_plan_passes_no_live_state_for_non_fusion() -> None:
    orch, store, planner, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="bevel 2mm"))

    assert planner.last_live_state_block is None


def test_reconciliation_flags_possible_manual_edit_on_count_mismatch() -> None:
    # T3.2: timeline ao vivo (5) ≠ histórico registrado (2 passos) → dica de
    # possível edição manual no contexto (não autoritativa).
    orch, store, planner, _ = _orchestrator(
        planner_steps=[_safe_step(1, "fusion.extrude_profile")],
        probe_count=5,
    )
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat
    parent = ModelingPlan(
        id="m3d_plan_parent",
        prompt="primário",
        software_choice=ModelingSoftware.fusion,
        steps=[
            _safe_step(1, "fusion.add_box").model_copy(
                update={"status": ModelingStepStatus.completed}
            ),
            _safe_step(2, "fusion.extrude_profile").model_copy(
                update={"status": ModelingStepStatus.completed}
            ),
        ],
    )
    store.plans["m3d_plan_parent"] = parent

    orch.propose_edit_plan(
        chat,
        payload=ModelingPlanCreate(prompt="editar", software_override=ModelingSoftware.fusion),
    )

    block = planner.last_live_state_block
    assert block is not None
    assert "edição manual" in block.lower()


def test_propose_edit_plan_blocks_on_high_risk() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_high_risk_step()])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat

    outcome = orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="aplicar boolean"))

    assert outcome.requires_approval is True
    assert outcome.execution is None
    assert outcome.chat.modeling_stage is ChatModelingStage.editing
    assert any(
        event.event_type == "modeling.chat.edit_high_risk_requested" for event in store.audit_events
    )


def test_propose_edit_plan_raises_outside_editing_stage() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat

    with pytest.raises(InvalidEditStage):
        orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="x"))


def test_approve_edit_plan_executes_and_keeps_editing_stage() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_high_risk_step()])
    chat = _make_chat(stage=ChatModelingStage.editing)
    store.chats[chat.id] = chat
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat
    outcome = orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="aplicar boolean"))

    chat, approved, execution = orch.approve_edit_plan(outcome.chat, outcome.plan.id)

    assert chat.modeling_stage is ChatModelingStage.editing
    assert approved.status is ModelingPlanStatus.completed
    assert execution.executed_step_ids


def test_reject_edit_plan_returns_to_discovery() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_high_risk_step()])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat
    outcome = orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="aplicar boolean"))

    chat, rejected = orch.reject_edit_plan(
        outcome.chat, outcome.plan.id, reason="prefiro outra abordagem"
    )

    assert chat.modeling_stage is ChatModelingStage.discovery
    assert rejected.status is ModelingPlanStatus.rejected


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_orchestrator_rejects_non_modeling_chats() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(is_modeling_3d=False)
    store.chats[chat.id] = chat

    with pytest.raises(NotAModelingChat):
        orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="x"))


def test_archive_chat_marks_completed_even_from_non_terminal_stage() -> None:
    orch, store, _, _ = _orchestrator()
    chat = _make_chat(stage=ChatModelingStage.editing)
    store.chats[chat.id] = chat

    updated = orch.archive_chat(chat)

    assert updated.modeling_stage is ChatModelingStage.completed
    assert any(event.event_type == "modeling.chat.archived" for event in store.audit_events)


def test_archive_chat_is_noop_for_non_modeling_chat() -> None:
    orch, _, _, _ = _orchestrator()
    chat = _make_chat(is_modeling_3d=False, stage=None)

    updated = orch.archive_chat(chat)

    assert updated is chat
    assert updated.modeling_stage is None


# ---------------------------------------------------------------------------
# split approve / execute (chat-card two-call flow)
# ---------------------------------------------------------------------------


def test_approve_plan_only_advances_to_approved_without_executing() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, approved = orch.approve_plan_only(chat, plan.id)

    # Approval moves the chat to ``approved`` but must NOT execute yet — the
    # executor only runs on the separate ``/execute`` call.
    assert chat.modeling_stage is ChatModelingStage.approved
    assert approved.status is ModelingPlanStatus.approved
    assert store.plans[plan.id].status is ModelingPlanStatus.approved


def test_execute_plan_runs_after_approve_and_lands_in_editing() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))
    chat, _ = orch.approve_plan_only(chat, plan.id)

    chat, executed_plan, execution = orch.execute_plan(chat, plan.id)

    assert chat.modeling_stage is ChatModelingStage.editing
    assert executed_plan.status is ModelingPlanStatus.completed
    assert execution.executed_step_ids


def test_split_flow_matches_monolithic_approve_plan() -> None:
    """approve_plan_only + execute_plan must land in the same end state as the
    monolithic approve_plan (the agent-tool path)."""

    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, _ = orch.approve_plan_only(chat, plan.id)
    chat, executed_plan, _ = orch.execute_plan(chat, plan.id)

    assert chat.modeling_stage is ChatModelingStage.editing
    assert executed_plan.status is ModelingPlanStatus.completed


def test_execute_plan_retry_in_editing_stays_editing() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))
    chat, _ = orch.approve_plan_only(chat, plan.id)
    chat, _, _ = orch.execute_plan(chat, plan.id)
    assert chat.modeling_stage is ChatModelingStage.editing

    # Retry from editing must execute again without an illegal transition.
    chat, _, execution = orch.execute_plan(chat, plan.id)

    assert chat.modeling_stage is ChatModelingStage.editing
    assert execution.executed_step_ids


def test_reject_dispatches_to_reject_plan_in_planning() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_safe_step(1, "blender.apply_bevel")])
    chat = _make_chat(stage=ChatModelingStage.discovery)
    store.chats[chat.id] = chat
    chat, plan = orch.propose_plan(chat, payload=ModelingPlanCreate(prompt="cubo"))

    chat, rejected = orch.reject(chat, plan.id, reason="forma errada")

    assert chat.modeling_stage is ChatModelingStage.discovery
    assert rejected.status is ModelingPlanStatus.rejected


def test_reject_dispatches_to_reject_edit_plan_in_editing() -> None:
    orch, store, _, _ = _orchestrator(planner_steps=[_high_risk_step()])
    chat = _make_chat(stage=ChatModelingStage.editing)
    chat = chat.model_copy(update={"modeling_plan_id": "m3d_plan_parent"})
    store.chats[chat.id] = chat
    outcome = orch.propose_edit_plan(chat, payload=ModelingPlanCreate(prompt="aplicar boolean"))

    chat, rejected = orch.reject(outcome.chat, outcome.plan.id, reason="não")

    assert rejected.status is ModelingPlanStatus.rejected
    assert chat.modeling_stage is ChatModelingStage.discovery
