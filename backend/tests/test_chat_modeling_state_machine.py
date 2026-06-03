"""Tests for the 3D chat state machine (Onda 2.3, ADR-013)."""

from __future__ import annotations

import pytest

from app.core.contracts import ChatModelingStage
from app.modeling.chat_state import (
    ChatModelingEvent,
    InvalidModelingStageTransition,
    allowed_events,
    initial_stage,
    is_terminal,
    is_valid_transition,
    transition,
)


def test_initial_stage_for_modeling_chat_is_discovery() -> None:
    assert initial_stage(is_modeling_3d=True) is ChatModelingStage.discovery


def test_initial_stage_for_non_modeling_chat_is_none() -> None:
    assert initial_stage(is_modeling_3d=False) is None


def test_chat_created_event_enters_discovery() -> None:
    next_stage = transition(None, ChatModelingEvent.CHAT_CREATED_AS_MODELING_3D)
    assert next_stage is ChatModelingStage.discovery


def test_clarification_keeps_chat_in_discovery() -> None:
    assert (
        transition(ChatModelingStage.discovery, ChatModelingEvent.CLARIFICATION_ASKED)
        is ChatModelingStage.discovery
    )


def test_plan_proposed_moves_discovery_to_planning() -> None:
    assert (
        transition(ChatModelingStage.discovery, ChatModelingEvent.PLAN_PROPOSED)
        is ChatModelingStage.planning
    )


def test_plan_approval_chain_moves_through_approved_executing_editing() -> None:
    after_approval = transition(ChatModelingStage.planning, ChatModelingEvent.PLAN_APPROVED)
    assert after_approval is ChatModelingStage.approved

    after_start = transition(after_approval, ChatModelingEvent.EXECUTION_STARTED)
    assert after_start is ChatModelingStage.executing

    after_complete = transition(after_start, ChatModelingEvent.EXECUTION_COMPLETED)
    assert after_complete is ChatModelingStage.editing


def test_plan_rejected_returns_to_discovery() -> None:
    assert (
        transition(ChatModelingStage.planning, ChatModelingEvent.PLAN_REJECTED)
        is ChatModelingStage.discovery
    )


def test_execution_failed_lands_in_failed() -> None:
    """DT-008: failed execution moves to the distinct ``failed`` stage."""

    assert (
        transition(ChatModelingStage.executing, ChatModelingEvent.EXECUTION_FAILED)
        is ChatModelingStage.failed
    )


def test_failed_recovers_to_editing_on_successful_edit() -> None:
    """DT-008: a successful edit/retry from ``failed`` recovers to ``editing``."""

    assert (
        transition(ChatModelingStage.failed, ChatModelingEvent.EDIT_AUTO_EXECUTED)
        is ChatModelingStage.editing
    )
    assert (
        transition(ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_APPROVED)
        is ChatModelingStage.editing
    )


def test_failed_stays_failed_on_pending_high_risk_and_resets_on_reject() -> None:
    assert (
        transition(ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED)
        is ChatModelingStage.failed
    )
    assert (
        transition(ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_REJECTED)
        is ChatModelingStage.discovery
    )


def test_new_primary_plan_from_editing_or_failed_moves_to_planning() -> None:
    """DT-006: começar um modelo do zero a partir de editing/failed propõe um
    plano primário e leva a planning (caso "modelo novo" da rota viva)."""

    assert (
        transition(ChatModelingStage.editing, ChatModelingEvent.PLAN_PROPOSED)
        is ChatModelingStage.planning
    )
    assert (
        transition(ChatModelingStage.failed, ChatModelingEvent.PLAN_PROPOSED)
        is ChatModelingStage.planning
    )


def test_editing_self_loops_for_auto_executed_mini_plans() -> None:
    assert (
        transition(ChatModelingStage.editing, ChatModelingEvent.EDIT_AUTO_EXECUTED)
        is ChatModelingStage.editing
    )


def test_editing_self_loops_for_high_risk_request_and_approval() -> None:
    assert (
        transition(ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED)
        is ChatModelingStage.editing
    )
    assert (
        transition(ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_APPROVED)
        is ChatModelingStage.editing
    )


def test_high_risk_rejection_in_editing_reopens_discovery() -> None:
    assert (
        transition(ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_REJECTED)
        is ChatModelingStage.discovery
    )


def test_archive_event_is_legal_from_any_stage() -> None:
    for stage in [None, *ChatModelingStage]:
        assert transition(stage, ChatModelingEvent.CHAT_ARCHIVED) is (ChatModelingStage.completed)


def test_illegal_event_raises_with_helpful_message() -> None:
    # Approving a plan while still in discovery is not a legal transition.
    with pytest.raises(InvalidModelingStageTransition) as exc_info:
        transition(ChatModelingStage.discovery, ChatModelingEvent.PLAN_APPROVED)
    assert "discovery" in str(exc_info.value)
    assert "plan_approved" in str(exc_info.value)


def test_is_valid_transition_predicate_never_raises() -> None:
    assert is_valid_transition(ChatModelingStage.planning, ChatModelingEvent.PLAN_APPROVED)
    assert not is_valid_transition(ChatModelingStage.discovery, ChatModelingEvent.PLAN_APPROVED)
    # Archive event must always be valid.
    assert is_valid_transition(None, ChatModelingEvent.CHAT_ARCHIVED)


def test_allowed_events_for_discovery_includes_clarify_and_propose() -> None:
    events = set(allowed_events(ChatModelingStage.discovery))
    assert ChatModelingEvent.CLARIFICATION_ASKED in events
    assert ChatModelingEvent.PLAN_PROPOSED in events
    assert ChatModelingEvent.CHAT_ARCHIVED in events


def test_allowed_events_for_planning_includes_approve_and_reject() -> None:
    events = set(allowed_events(ChatModelingStage.planning))
    assert ChatModelingEvent.PLAN_APPROVED in events
    assert ChatModelingEvent.PLAN_REJECTED in events


def test_is_terminal_only_true_for_completed() -> None:
    assert is_terminal(ChatModelingStage.completed)
    assert not is_terminal(ChatModelingStage.discovery)
    assert not is_terminal(ChatModelingStage.editing)
    assert not is_terminal(None)


def test_full_happy_path_is_chainable() -> None:
    stage: ChatModelingStage | None = None
    events_in_order = [
        ChatModelingEvent.CHAT_CREATED_AS_MODELING_3D,
        ChatModelingEvent.CLARIFICATION_ASKED,
        ChatModelingEvent.CLARIFICATION_ASKED,
        ChatModelingEvent.PLAN_PROPOSED,
        ChatModelingEvent.PLAN_APPROVED,
        ChatModelingEvent.EXECUTION_STARTED,
        ChatModelingEvent.EXECUTION_COMPLETED,
        ChatModelingEvent.EDIT_AUTO_EXECUTED,
        ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED,
        ChatModelingEvent.EDIT_HIGH_RISK_APPROVED,
        ChatModelingEvent.CHAT_ARCHIVED,
    ]
    for event in events_in_order:
        stage = transition(stage, event)
    assert stage is ChatModelingStage.completed
