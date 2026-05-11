from __future__ import annotations

import hashlib
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
    ModelingStepStatus,
    PlatformFile,
    PlatformFileCreate,
    now_utc,
)
from app.files.library import content_type_for_name, safe_filename
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.planner import create_structured_plan
from app.modeling.policy import apply_modeling_policy

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
            output = self.mcp_client.execute_step(
                step,
                plan_id=plan.id,
                project_id=plan.project_id,
            )
            output = self._register_generated_artifacts(output, plan=plan, step=step)
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
                },
            ),
        )
        return ModelingExecutionResult(
            plan=updated,
            executed_step_ids=executed_step_ids,
            blocked_step_ids=blocked_step_ids,
            events=events,
        )

    def create_snapshot(self, payload: ModelingSnapshotCreate) -> ModelingSnapshot:
        settings.ensure_local_dirs()
        snapshot_dir = settings.data_dir / "modeling" / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(
            f"{payload.project_id}|{payload.plan_id}|{payload.label}|{now_utc().isoformat()}".encode()
        ).hexdigest()
        manifest = {
            "sha256": fingerprint,
            "path": str(snapshot_dir / f"{fingerprint[:16]}.json"),
            "note": (
                "Manifesto lógico inicial; artefatos reais entram quando "
                "adapters MCP estiverem conectados."
            ),
        }
        snapshot = ModelingSnapshot(
            project_id=payload.project_id,
            plan_id=payload.plan_id,
            label=payload.label,
            reason=payload.reason,
            manifest=manifest,
        )
        self.store.upsert_modeling_snapshot(snapshot)
        return snapshot

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
                    checksum_sha256=self._sha256_file(path),
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

    @staticmethod
    def _sha256_file(path: Path) -> str:
        checksum = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                checksum.update(chunk)
        return checksum.hexdigest()


def get_modeling_service(store: Any) -> ModelingService:
    return ModelingService(store)
