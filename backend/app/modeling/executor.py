"""Plan execution service extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
plan execution end-to-end: routing steps to the MCP client (or the
in-process ``project_store`` handler), wrapping outputs in tool-call records
and updating the plan status when a step fails / completes / stays blocked.

The :class:`ModelingService` facade keeps the same public ``execute_plan``
method and delegates here.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.contracts import (
    AuditEvent,
    ModelingErrorEnvelope,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingSnapshotCreate,
    ModelingStepStatus,
    ModelingToolCall,
    ModelingToolCallStatus,
    ModelingTraceLevel,
    ModelingTraceSource,
    now_utc,
)
from app.modeling.artifacts import ModelingArtifactService
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.observability import current_trace_id, get_tracer
from app.modeling.snapshot_service import ModelingSnapshotService


def envelope_into_output(
    envelope: ModelingErrorEnvelope, *, base: dict[str, Any]
) -> dict[str, Any]:
    """Spread a typed error envelope into a tool output dict.

    Keeps a single source of truth for error fields (``error_code``,
    ``retryable``, ``safe_to_retry_after_snapshot_restore``,
    ``host_details``) while still returning a serializable dict to fit the
    existing dict-based tool-call contract.
    """

    return {**base, **envelope.model_dump(), "message": envelope.message}


def envelope_from_output(output: dict[str, Any]) -> ModelingErrorEnvelope | None:
    """Reconstruct an envelope from a tool output dict, if one is present."""

    error_code = output.get("error_code")
    if not error_code:
        return None
    try:
        return ModelingErrorEnvelope(
            error_code=str(error_code),
            message=str(output.get("message") or output.get("error") or ""),
            retryable=bool(output.get("retryable", False)),
            safe_to_retry_after_snapshot_restore=bool(
                output.get("safe_to_retry_after_snapshot_restore", False)
            ),
            host_details=(
                output["host_details"] if isinstance(output.get("host_details"), dict) else {}
            ),
        )
    except Exception:  # pragma: no cover - defensive against malformed output
        return None


class ModelingExecutorService:
    """Executes plans by dispatching steps and recording tool calls."""

    def __init__(
        self,
        store: Any,
        mcp_client: LocalMCPClient,
        snapshots: ModelingSnapshotService,
        artifacts: ModelingArtifactService,
    ) -> None:
        self.store = store
        self.mcp_client = mcp_client
        self.snapshots = snapshots
        self.artifacts = artifacts
        # Tracer compartilhado (no-op se a store não tem record_trace_events_bulk).
        self._tracer = get_tracer(store if hasattr(store, "record_trace_events_bulk") else None)

    def execute_plan(self, plan: ModelingPlan) -> ModelingExecutionResult:
        """Execute every runnable step of ``plan`` and persist the result."""

        if plan.status == ModelingPlanStatus.draft:
            blocked_step_ids = [step.id for step in plan.steps]
            return ModelingExecutionResult(
                plan=plan,
                executed_step_ids=[],
                blocked_step_ids=blocked_step_ids,
                events=["Plano em modo planejamento; aprove antes de executar."],
                tool_call_ids=[],
            )

        executed_step_ids: list[str] = []
        blocked_step_ids: list[str] = []
        events: list[str] = []
        tool_call_ids: list[str] = []
        next_steps: list[ModelingPlanStep] = []

        for step in plan.steps:
            if step.error:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                self._tracer.record(
                    "executor.step_skipped",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.warn,
                    message=f"Step {step.seq} bloqueado por erro prévio",
                    payload={"step_id": step.id, "tool_name": step.tool_name, "error": step.error},
                    plan_id=plan.id,
                )
                continue
            if step.approval_required and step.status != ModelingStepStatus.approved:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                self._tracer.record(
                    "executor.step_blocked",
                    source=ModelingTraceSource.backend,
                    level=ModelingTraceLevel.info,
                    message=f"Step {step.seq} aguardando aprovação humana",
                    payload={
                        "step_id": step.id,
                        "tool_name": step.tool_name,
                        "risk_level": step.risk_level.value,
                    },
                    plan_id=plan.id,
                )
                continue

            self._tracer.record(
                "executor.step_started",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.info,
                message=f"Step {step.seq}: {step.tool_name}",
                payload={
                    "step_id": step.id,
                    "seq": step.seq,
                    "tool_name": step.tool_name,
                    "input": step.input_json,
                },
                plan_id=plan.id,
            )

            started_at = time.perf_counter()
            output = self._dispatch_step(step, plan=plan)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            output = self.artifacts.register_outputs(output, plan=plan, step=step)

            tool_call = self._record_tool_call(
                plan=plan, step=step, output=output, duration_ms=duration_ms
            )
            if tool_call is not None:
                tool_call_ids.append(tool_call.id)

            executed_step_ids.append(step.id)
            event_verb = "executado" if output.get("transport") != "mock" else "preparado"
            events.append(f"{step.seq}. {step.tool_name} {event_verb} via {output['mcp_server']}")

            step_ok = output.get("ok") is not False
            self._tracer.record(
                "executor.step_ok" if step_ok else "executor.step_error",
                source=ModelingTraceSource.backend,
                level=ModelingTraceLevel.info if step_ok else ModelingTraceLevel.error,
                message=(
                    f"Step {step.seq} OK"
                    if step_ok
                    else f"Step {step.seq} falhou: {output.get('message') or output.get('error')}"
                ),
                payload={
                    "step_id": step.id,
                    "tool_name": step.tool_name,
                    "transport": output.get("transport"),
                    "mcp_server": output.get("mcp_server"),
                    "error_code": output.get("error_code"),
                    "error_message": output.get("message") or output.get("error"),
                    "retryable": output.get("retryable"),
                },
                duration_ms=duration_ms,
                plan_id=plan.id,
            )

            if output.get("ok") is False:
                blocked_step_ids.append(step.id)
                next_steps.append(
                    step.model_copy(
                        update={
                            "status": ModelingStepStatus.failed,
                            "output_json": output,
                            "error": str(output.get("message") or output.get("error") or ""),
                            "completed_at": now_utc(),
                        }
                    )
                )
                continue
            next_steps.append(
                step.model_copy(
                    update={
                        "status": ModelingStepStatus.completed,
                        "output_json": output,
                        "completed_at": now_utc(),
                    }
                )
            )

        has_failed_step = any(step.status == ModelingStepStatus.failed for step in next_steps)
        if has_failed_step:
            status = ModelingPlanStatus.failed
        elif blocked_step_ids:
            status = ModelingPlanStatus.running
        else:
            status = ModelingPlanStatus.completed
        updated = plan.model_copy(
            update={"steps": next_steps, "status": status, "updated_at": now_utc()}
        )
        self.store.upsert_modeling_plan(updated)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_executed",
                metadata={
                    "plan_id": updated.id,
                    "executed_step_ids": executed_step_ids,
                    "blocked_step_ids": blocked_step_ids,
                    "tool_call_ids": tool_call_ids,
                },
                trace_id=current_trace_id(),
            ),
        )
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed_step_ids,
            blocked_step_ids=blocked_step_ids,
            events=events,
            tool_call_ids=tool_call_ids,
        )

    # ------------------------------------------------------------------
    # step dispatch
    # ------------------------------------------------------------------

    def _dispatch_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> dict[str, Any]:
        """Route a step to the right local handler.

        ``project_store.*`` tools are handled inline because the project
        store lives in the same process. Everything else goes through the
        MCP client boundary, which delegates to the adapter or falls back
        to mock.
        """

        if step.tool_name == "project_store.create_snapshot":
            return self._run_project_store_snapshot(step, plan=plan)
        return self.mcp_client.execute_step(
            step,
            plan_id=plan.id,
            project_id=plan.project_id,
        )

    def _run_project_store_snapshot(
        self, step: ModelingPlanStep, *, plan: ModelingPlan
    ) -> dict[str, Any]:
        try:
            snapshot = self.snapshots.create(
                ModelingSnapshotCreate(
                    project_id=plan.project_id,
                    plan_id=plan.id,
                    step_id=step.id,
                    label=str(step.input_json.get("label") or f"Plan {plan.id} step {step.seq}"),
                    reason=str(step.input_json.get("reason") or "before_modeling"),
                )
            )
        except Exception as exc:  # pragma: no cover - safety net
            envelope = ModelingErrorEnvelope(
                error_code="project_store.snapshot_failed",
                message=f"Falha ao criar snapshot: {exc}",
                retryable=False,
                safe_to_retry_after_snapshot_restore=False,
                host_details={"plan_id": plan.id, "step_id": step.id},
            )
            return envelope_into_output(
                envelope,
                base={
                    "ok": False,
                    "mcp_server": "project_store_mcp",
                    "transport": "local",
                    "tool_name": step.tool_name,
                    "software": step.software.value,
                    "input": step.input_json,
                },
            )
        return {
            "ok": True,
            "mcp_server": "project_store_mcp",
            "transport": "local",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": f"Snapshot {snapshot.id} criado ({len(snapshot.files)} arquivo(s)).",
            "input": step.input_json,
            "snapshot_id": snapshot.id,
            "artifact_paths": [],
        }

    # ------------------------------------------------------------------
    # tool-call persistence
    # ------------------------------------------------------------------

    def _record_tool_call(
        self,
        *,
        plan: ModelingPlan,
        step: ModelingPlanStep,
        output: dict[str, Any],
        duration_ms: int,
    ) -> ModelingToolCall | None:
        if not hasattr(self.store, "add_modeling_tool_call"):
            return None
        ok = output.get("ok") is not False
        status = ModelingToolCallStatus.ok if ok else ModelingToolCallStatus.error
        artifact_paths = [
            value for value in output.get("artifact_paths", []) if isinstance(value, str) and value
        ]
        artifact_file_ids = [
            value
            for value in output.get("platform_file_ids", [])
            if isinstance(value, str) and value
        ]
        model_version_ids = [
            value
            for value in output.get("model_version_ids", [])
            if isinstance(value, str) and value
        ]
        envelope = envelope_from_output(output) if not ok else None
        record = ModelingToolCall(
            plan_id=plan.id,
            step_id=step.id,
            seq=step.seq,
            mcp_server=str(output.get("mcp_server") or "unknown_mcp"),
            tool_name=step.tool_name,
            software=step.software,
            transport=output.get("transport") or "mock",
            status=status,
            request_json=step.input_json,
            response_json=output,
            error_code=envelope.error_code if envelope else None,
            error_message=envelope.message if envelope else None,
            retryable=envelope.retryable if envelope else False,
            safe_to_retry_after_snapshot_restore=(
                envelope.safe_to_retry_after_snapshot_restore if envelope else False
            ),
            duration_ms=duration_ms,
            artifact_paths=artifact_paths,
            artifact_file_ids=artifact_file_ids,
            model_version_ids=model_version_ids,
        )
        return self.store.add_modeling_tool_call(record)


__all__ = [
    "ModelingExecutorService",
    "envelope_from_output",
    "envelope_into_output",
]
