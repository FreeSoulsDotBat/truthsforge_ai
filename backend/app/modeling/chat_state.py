"""State machine for 3D modeling chats (ADR-013).

The chat-first orchestrator drives every 3D chat through a single linear
state machine. This module captures the transitions as **pure functions**
so the orchestrator (and tests) can apply them without touching the
store, the LLM gateway or the executor.

Lifecycle::

    None  (not a 3D chat)

    created          ─→ discovery
    discovery        ─→ planning      (event: PLAN_PROPOSED)
    discovery        ─→ discovery     (event: CLARIFICATION_ASKED)
    planning         ─→ approved      (event: PLAN_APPROVED)
    planning         ─→ discovery     (event: PLAN_REJECTED)
    approved         ─→ executing     (event: EXECUTION_STARTED)
    executing        ─→ editing       (event: EXECUTION_COMPLETED)
    executing        ─→ failed        (event: EXECUTION_FAILED)      [DT-008]
    editing          ─→ editing       (event: EDIT_AUTO_EXECUTED)
    editing          ─→ editing       (event: EDIT_HIGH_RISK_REQUESTED)
    editing          ─→ editing       (event: EDIT_HIGH_RISK_APPROVED)
    editing          ─→ discovery     (event: EDIT_HIGH_RISK_REJECTED)
    failed           ─→ editing       (event: EDIT_AUTO_EXECUTED)      [DT-008]
    failed           ─→ failed        (event: EDIT_HIGH_RISK_REQUESTED)
    failed           ─→ editing       (event: EDIT_HIGH_RISK_APPROVED)
    failed           ─→ discovery     (event: EDIT_HIGH_RISK_REJECTED)
    any              ─→ completed     (event: CHAT_ARCHIVED)

DT-008: a failed execution lands in ``failed`` (not ``editing``) so the
agentic loop and the UI can distinguish a failed run from a healthy one.
The chat recovers from ``failed`` via the same edit/retry events as
``editing`` (a successful edit moves it to ``editing``).

The transitions matrix lives in :data:`_TRANSITIONS`. The orchestrator
must call :func:`transition` and let it raise
:class:`InvalidModelingStageTransition` when a caller tries to apply an
event that is not legal for the current stage.

Non-3D chats keep ``modeling_stage = None``; calling any function in this
module with ``stage=None`` works as long as the event makes sense for the
``None`` state (currently only ``CHAT_CREATED_AS_MODELING_3D``).
"""

from __future__ import annotations

from enum import StrEnum

from app.core.contracts import ChatModelingStage


class ChatModelingEvent(StrEnum):
    """Events that drive the 3D chat state machine."""

    CHAT_CREATED_AS_MODELING_3D = "chat_created_as_modeling_3d"
    CLARIFICATION_ASKED = "clarification_asked"
    PLAN_PROPOSED = "plan_proposed"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EDIT_AUTO_EXECUTED = "edit_auto_executed"
    EDIT_HIGH_RISK_REQUESTED = "edit_high_risk_requested"
    EDIT_HIGH_RISK_APPROVED = "edit_high_risk_approved"
    EDIT_HIGH_RISK_REJECTED = "edit_high_risk_rejected"
    CHAT_ARCHIVED = "chat_archived"


class InvalidModelingStageTransition(ValueError):
    """Raised when an event is not legal for the current stage."""

    def __init__(self, stage: ChatModelingStage | None, event: ChatModelingEvent) -> None:
        stage_str = stage.value if stage is not None else "<none>"
        super().__init__(
            f"Modeling chat cannot apply event {event.value!r} from stage {stage_str!r}."
        )
        self.stage = stage
        self.event = event


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

_STAGE_OR_NONE = ChatModelingStage | None

_TRANSITIONS: dict[tuple[_STAGE_OR_NONE, ChatModelingEvent], ChatModelingStage] = {
    # Entering the 3D flow from a freshly created chat.
    (None, ChatModelingEvent.CHAT_CREATED_AS_MODELING_3D): ChatModelingStage.discovery,
    # Discovery loops on itself while the agent gathers context.
    (ChatModelingStage.discovery, ChatModelingEvent.CLARIFICATION_ASKED): (
        ChatModelingStage.discovery
    ),
    (ChatModelingStage.discovery, ChatModelingEvent.PLAN_PROPOSED): (ChatModelingStage.planning),
    # DT-006: "modelo do zero" a partir de um chat que já tinha modelo
    # (estágio editing/failed) também propõe um plano primário → planning.
    (ChatModelingStage.editing, ChatModelingEvent.PLAN_PROPOSED): (ChatModelingStage.planning),
    (ChatModelingStage.failed, ChatModelingEvent.PLAN_PROPOSED): (ChatModelingStage.planning),
    # Planning resolves either to approval or rejection.
    (ChatModelingStage.planning, ChatModelingEvent.PLAN_APPROVED): (ChatModelingStage.approved),
    (ChatModelingStage.planning, ChatModelingEvent.PLAN_REJECTED): (ChatModelingStage.discovery),
    # Execution lifecycle.
    (ChatModelingStage.approved, ChatModelingEvent.EXECUTION_STARTED): (
        ChatModelingStage.executing
    ),
    (ChatModelingStage.executing, ChatModelingEvent.EXECUTION_COMPLETED): (
        ChatModelingStage.editing
    ),
    # DT-008: failure lands in a distinct ``failed`` stage (was ``editing``).
    (ChatModelingStage.executing, ChatModelingEvent.EXECUTION_FAILED): (ChatModelingStage.failed),
    # Recovery from ``failed`` mirrors the editing loop: a successful edit/
    # retry moves to ``editing``; a pending high-risk retry stays in
    # ``failed``; rejecting it returns to ``discovery``.
    (ChatModelingStage.failed, ChatModelingEvent.EDIT_AUTO_EXECUTED): (ChatModelingStage.editing),
    (ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED): (
        ChatModelingStage.failed
    ),
    (ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_APPROVED): (
        ChatModelingStage.editing
    ),
    (ChatModelingStage.failed, ChatModelingEvent.EDIT_HIGH_RISK_REJECTED): (
        ChatModelingStage.discovery
    ),
    # Editing loop — mini-plans either auto-execute or block on high-risk.
    (ChatModelingStage.editing, ChatModelingEvent.EDIT_AUTO_EXECUTED): (ChatModelingStage.editing),
    (ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_REQUESTED): (
        ChatModelingStage.editing
    ),
    (ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_APPROVED): (
        ChatModelingStage.editing
    ),
    (ChatModelingStage.editing, ChatModelingEvent.EDIT_HIGH_RISK_REJECTED): (
        ChatModelingStage.discovery
    ),
}


# CHAT_ARCHIVED is legal from every stage including ``None``; encode that
# uniformly without listing each (stage, event) pair.
def _is_archive(event: ChatModelingEvent) -> bool:
    return event is ChatModelingEvent.CHAT_ARCHIVED


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def initial_stage(*, is_modeling_3d: bool) -> ChatModelingStage | None:
    """Return the initial stage for a freshly created chat.

    Non-3D chats keep ``modeling_stage = None`` for their whole lifetime.
    """

    return ChatModelingStage.discovery if is_modeling_3d else None


def is_valid_transition(stage: ChatModelingStage | None, event: ChatModelingEvent) -> bool:
    """Predicate version of :func:`transition`. Never raises."""

    if _is_archive(event):
        return True
    return (stage, event) in _TRANSITIONS


def transition(stage: ChatModelingStage | None, event: ChatModelingEvent) -> ChatModelingStage:
    """Apply ``event`` to ``stage`` and return the next stage.

    Raises :class:`InvalidModelingStageTransition` when the event is not
    legal for the current stage.
    """

    if _is_archive(event):
        return ChatModelingStage.completed
    try:
        return _TRANSITIONS[(stage, event)]
    except KeyError as exc:
        raise InvalidModelingStageTransition(stage, event) from exc


def allowed_events(stage: ChatModelingStage | None) -> tuple[ChatModelingEvent, ...]:
    """Return every event that is legal from ``stage``.

    Useful for telemetry / debugging and for the orchestrator to decide
    which tools to expose to the LLM at a given stage (see Onda 2.4).
    """

    events: list[ChatModelingEvent] = [event for (s, event) in _TRANSITIONS if s == stage]
    events.append(ChatModelingEvent.CHAT_ARCHIVED)
    return tuple(events)


def is_terminal(stage: ChatModelingStage | None) -> bool:
    """``True`` when no further events are expected (chat is archived)."""

    return stage is ChatModelingStage.completed


__all__ = [
    "ChatModelingEvent",
    "InvalidModelingStageTransition",
    "allowed_events",
    "initial_stage",
    "is_terminal",
    "is_valid_transition",
    "transition",
]
