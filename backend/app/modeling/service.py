from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingCapabilities,
    ModelingCapability,
    ModelingExecutionResult,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingSession,
    ModelingSessionStart,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotFile,
    ModelingSnapshotRestore,
    ModelingStepStatus,
    ModelingToolCall,
    ModelingToolCallStatus,
    PlatformFile,
    PlatformFileCreate,
    now_utc,
)
from app.files.library import content_type_for_name, safe_filename
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.planner import create_structured_plan
from app.modeling.policy import apply_modeling_policy
from app.modeling.workspace import (
    copy_into_snapshot,
    is_inside,
    restore_from_snapshot,
    safe_segment,
    sha256_file,
    snapshots_root,
    workspace_dir,
)

ARTIFACT_CONTENT_TYPES = {
    ".3mf": "model/3mf",
    ".blend": "application/x-blender",
    ".obj": "model/obj",
    ".stl": "model/stl",
}


class ModelingService:
    def __init__(self, store: Any, mcp_client: LocalMCPClient | None = None) -> None:
        self.store = store
        self.mcp_client = mcp_client or LocalMCPClient()

    def capabilities(self) -> ModelingCapabilities:
        capabilities = self.mcp_client.capabilities()
        return ModelingCapabilities(
            safety_notes=[
                "MCP roda localmente; nenhum MCP remoto fica exposto no MVP.",
                "Ações mutáveis em Blender/Fusion exigem aprovação humana por padrão.",
                "Scripts livres e comandos de shell ficam bloqueados até revisão explícita.",
            ],
            adapters=[
                ModelingCapability(
                    software=software,
                    connected=self.mcp_client.is_connected(software),
                    transport=self.mcp_client.transport(software),
                    tools=tools,
                    status=self.mcp_client.adapter_status(software),
                    detail=self.mcp_client.detail(software),
                )
                for software, tools in capabilities.items()
            ],
        )

    def start_session(self, payload: ModelingSessionStart) -> ModelingSession:
        session = ModelingSession(
            software=payload.software,
            project_id=payload.project_id,
            status="mock" if payload.force_mock else "starting",
            mcp_server=f"{payload.software.value}_mcp",
            metadata={
                "force_mock": payload.force_mock,
                "requires_desktop_adapter": True,
            },
        )
        self.store.upsert_modeling_session(session)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.session_started",
                metadata={
                    "session_id": session.id,
                    "software": session.software.value,
                    "status": session.status,
                },
            ),
        )
        return session

    def create_plan(self, payload: ModelingPlanCreate) -> ModelingPlan:
        plan = apply_modeling_policy(create_structured_plan(payload))
        self.store.upsert_modeling_plan(plan)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_created",
                metadata={
                    "plan_id": plan.id,
                    "software": plan.software_choice.value,
                    "step_count": len(plan.steps),
                    "mode": plan.mode.value,
                },
            ),
        )
        return plan

    def approve_plan(self, plan_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
        plan = self._get_plan_or_raise(plan_id)
        if payload.decision == ModelingApprovalDecision.reject:
            rejected = plan.model_copy(
                update={"status": ModelingPlanStatus.rejected, "updated_at": now_utc()}
            )
            self.store.upsert_modeling_plan(rejected)
            return rejected

        steps = [
            step.model_copy(
                update={
                    "status": ModelingStepStatus.approved
                    if step.approval_required
                    else step.status,
                    "approved_at": now_utc() if step.approval_required else step.approved_at,
                }
            )
            for step in plan.steps
        ]
        approved = plan.model_copy(
            update={"status": ModelingPlanStatus.approved, "steps": steps, "updated_at": now_utc()}
        )
        self.store.upsert_modeling_plan(approved)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.plan_approved",
                metadata={"plan_id": approved.id, "reason": payload.reason},
            ),
        )
        return approved

    def decide_step(self, step_id: str, payload: ModelingApprovalRequest) -> ModelingPlan:
        plan = self.store.get_modeling_plan_by_step(step_id)
        if plan is None:
            raise KeyError(step_id)
        next_steps = []
        for step in plan.steps:
            if step.id != step_id:
                next_steps.append(step)
                continue
            if payload.decision == ModelingApprovalDecision.reject:
                next_steps.append(
                    step.model_copy(
                        update={
                            "status": ModelingStepStatus.rejected,
                            "error": payload.reason or "Etapa rejeitada pelo usuário.",
                        }
                    )
                )
            else:
                next_steps.append(
                    step.model_copy(
                        update={"status": ModelingStepStatus.approved, "approved_at": now_utc()}
                    )
                )
        status = (
            ModelingPlanStatus.rejected
            if any(step.status == ModelingStepStatus.rejected for step in next_steps)
            else plan.status
        )
        updated = plan.model_copy(
            update={"steps": next_steps, "status": status, "updated_at": now_utc()}
        )
        self.store.upsert_modeling_plan(updated)
        return updated

    def execute_plan(self, plan_id: str) -> ModelingExecutionResult:
        plan = self._get_plan_or_raise(plan_id)
        executed_step_ids: list[str] = []
        blocked_step_ids: list[str] = []
        events: list[str] = []
        tool_call_ids: list[str] = []
        next_steps = []
        for step in plan.steps:
            if step.error:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                continue
            if step.approval_required and step.status != ModelingStepStatus.approved:
                blocked_step_ids.append(step.id)
                next_steps.append(step)
                continue

            started_at = time.perf_counter()
            output = self.mcp_client.execute_step(
                step,
                plan_id=plan.id,
                project_id=plan.project_id,
            )
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            output = self._register_generated_artifacts(output, plan=plan, step=step)

            tool_call = self._record_tool_call(
                plan=plan, step=step, output=output, duration_ms=duration_ms
            )
            if tool_call is not None:
                tool_call_ids.append(tool_call.id)

            executed_step_ids.append(step.id)
            event_verb = "executado" if output.get("transport") != "mock" else "preparado"
            events.append(f"{step.seq}. {step.tool_name} {event_verb} via {output['mcp_server']}")

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
            ),
        )
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed_step_ids,
            blocked_step_ids=blocked_step_ids,
            events=events,
            tool_call_ids=tool_call_ids,
        )

    def create_snapshot(self, payload: ModelingSnapshotCreate) -> ModelingSnapshot:
        settings.ensure_local_dirs()
        snapshot = ModelingSnapshot(
            project_id=payload.project_id,
            plan_id=payload.plan_id,
            step_id=payload.step_id,
            parent_snapshot_id=payload.parent_snapshot_id,
            label=payload.label,
            reason=payload.reason,
        )
        workspace = workspace_dir(payload.project_id, payload.plan_id)
        snapshot_dir = snapshots_root() / safe_segment(snapshot.id, "snapshot")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        files_dir = snapshot_dir / "files"

        snapshot_files: list[ModelingSnapshotFile] = []
        if workspace.is_dir():
            copied = copy_into_snapshot(workspace, files_dir)
            for path in copied:
                relative = path.relative_to(files_dir).as_posix()
                snapshot_files.append(
                    ModelingSnapshotFile(
                        relative_path=relative,
                        sha256=sha256_file(path),
                        size_bytes=path.stat().st_size,
                    )
                )

        manifest = {
            "id": snapshot.id,
            "project_id": payload.project_id,
            "plan_id": payload.plan_id,
            "step_id": payload.step_id,
            "parent_snapshot_id": payload.parent_snapshot_id,
            "label": payload.label,
            "reason": payload.reason,
            "workspace_path": str(workspace),
            "storage_path": str(snapshot_dir),
            "created_at": snapshot.created_at.isoformat(),
            "files": [item.model_dump() for item in snapshot_files],
        }
        manifest_path = snapshot_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        snapshot = snapshot.model_copy(
            update={
                "workspace_path": str(workspace),
                "storage_path": str(snapshot_dir),
                "files": snapshot_files,
                "manifest": manifest,
            }
        )
        self.store.upsert_modeling_snapshot(snapshot)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.snapshot_created",
                metadata={
                    "snapshot_id": snapshot.id,
                    "plan_id": payload.plan_id,
                    "step_id": payload.step_id,
                    "parent_snapshot_id": payload.parent_snapshot_id,
                    "file_count": len(snapshot_files),
                },
            ),
        )
        return snapshot

    def restore_snapshot(
        self, snapshot_id: str, payload: ModelingSnapshotRestore | None = None
    ) -> ModelingSnapshot:
        if not hasattr(self.store, "get_modeling_snapshot"):
            raise RuntimeError("Backend store não implementa get_modeling_snapshot.")
        snapshot = self.store.get_modeling_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(snapshot_id)
        if not snapshot.storage_path or not snapshot.workspace_path:
            raise ValueError(
                "Snapshot sem storage_path/workspace_path; "
                "não há conteúdo persistido para restaurar."
            )

        storage = Path(snapshot.storage_path)
        workspace = Path(snapshot.workspace_path)
        modeling_root = settings.modeling_dir
        if not is_inside(storage, modeling_root) or not is_inside(workspace, modeling_root):
            raise ValueError("Snapshot fora do diretório de modelagem; restauração bloqueada.")

        files_dir = storage / "files"
        restored_paths = restore_from_snapshot(files_dir, workspace)
        timestamp = now_utc()
        updated = snapshot.model_copy(update={"restored_at": timestamp})
        self.store.upsert_modeling_snapshot(updated)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.snapshot_restored",
                metadata={
                    "snapshot_id": updated.id,
                    "plan_id": updated.plan_id,
                    "step_id": updated.step_id,
                    "file_count": len(restored_paths),
                    "reason": (payload.reason if payload else ""),
                },
            ),
        )
        return updated

    def list_tool_calls(
        self,
        *,
        plan_id: str | None = None,
        step_id: str | None = None,
        limit: int = 200,
    ) -> list[ModelingToolCall]:
        if not hasattr(self.store, "list_modeling_tool_calls"):
            return []
        return self.store.list_modeling_tool_calls(plan_id=plan_id, step_id=step_id, limit=limit)

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
            error_code=output.get("error_code") if not ok else None,
            error_message=(
                str(output.get("message") or output.get("error") or "") if not ok else None
            ),
            retryable=bool(output.get("retryable", False)) if not ok else False,
            safe_to_retry_after_snapshot_restore=bool(
                output.get("safe_to_retry_after_snapshot_restore", False)
            )
            if not ok
            else False,
            duration_ms=duration_ms,
            artifact_paths=artifact_paths,
        )
        return self.store.add_modeling_tool_call(record)

    def _get_plan_or_raise(self, plan_id: str) -> ModelingPlan:
        plan = self.store.get_modeling_plan(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        return plan

    def _register_generated_artifacts(
        self,
        output: dict[str, Any],
        *,
        plan: ModelingPlan,
        step: ModelingPlanStep,
    ) -> dict[str, Any]:
        artifact_paths = [
            Path(raw_path).resolve()
            for raw_path in output.get("artifact_paths", [])
            if isinstance(raw_path, str) and raw_path
        ]
        if not artifact_paths or not hasattr(self.store, "create_platform_file"):
            return output

        created_or_existing: list[PlatformFile] = []
        existing_files = (
            self.store.list_platform_files() if hasattr(self.store, "list_platform_files") else []
        )
        existing_by_storage_path = {item.storage_path: item for item in existing_files}
        for path in artifact_paths:
            if not self._is_path_inside_data_dir(path) or not path.is_file():
                continue
            storage_path = str(path)
            existing = existing_by_storage_path.get(storage_path)
            if existing:
                created_or_existing.append(existing)
                continue
            platform_file = self.store.create_platform_file(
                PlatformFileCreate(
                    filename=safe_filename(path.name),
                    original_filename=safe_filename(path.name),
                    content_type=self._artifact_content_type(path),
                    size_bytes=path.stat().st_size,
                    storage_path=storage_path,
                    checksum_sha256=sha256_file(path),
                    source="generated",
                    tags=["3d", "modeling", step.software.value],
                    metadata={
                        "artifact_kind": "3d_model",
                        "project_id": plan.project_id,
                        "conversation_id": plan.conversation_id,
                        "plan_id": plan.id,
                        "step_id": step.id,
                        "software": step.software.value,
                        "tool_name": step.tool_name,
                    },
                )
            )
            existing_by_storage_path[storage_path] = platform_file
            created_or_existing.append(platform_file)

        if not created_or_existing:
            return output
        return {
            **output,
            "platform_file_ids": [platform_file.id for platform_file in created_or_existing],
        }

    @staticmethod
    def _is_path_inside_data_dir(path: Path) -> bool:
        return path.is_relative_to(settings.data_dir.resolve())

    @staticmethod
    def _artifact_content_type(path: Path) -> str:
        return ARTIFACT_CONTENT_TYPES.get(
            path.suffix.lower(),
            content_type_for_name(path.name) or "application/octet-stream",
        )


def get_modeling_service(store: Any) -> ModelingService:
    return ModelingService(store)
