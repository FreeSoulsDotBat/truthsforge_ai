from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    KnowledgeBase,
    ModelCapability,
    ModelConfig,
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingCapabilities,
    ModelingCapability,
    ModelingErrorEnvelope,
    ModelingExecutionResult,
    ModelingModelVersion,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlannerSource,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingPrintabilityIssue,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingRiskLevel,
    ModelingSession,
    ModelingSessionStart,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotFile,
    ModelingSnapshotRestore,
    ModelingSnapshotRestoreResult,
    ModelingSoftware,
    ModelingStepStatus,
    ModelingToolCall,
    ModelingToolCallStatus,
    PlatformFile,
    PlatformFileCreate,
    ProviderName,
    now_utc,
)
from app.files.library import content_type_for_name, safe_filename
from app.llm_gateway.gateway import LLMGateway
from app.modeling.mcp_client import LocalMCPClient
from app.modeling.planner import create_heuristic_plan, create_llm_plan, create_llm_plan_async
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

logger = logging.getLogger(__name__)

ARTIFACT_CONTENT_TYPES = {
    ".3mf": "model/3mf",
    ".blend": "application/x-blender",
    ".obj": "model/obj",
    ".stl": "model/stl",
}


def _envelope_into_output(
    envelope: ModelingErrorEnvelope, *, base: dict[str, Any]
) -> dict[str, Any]:
    """Spread a typed error envelope into a tool output dict.

    Keeps a single source of truth for error fields (``error_code``,
    ``retryable``, ``safe_to_retry_after_snapshot_restore``, ``host_details``)
    while still returning a serializable dict to fit the existing dict-based
    tool call contract.
    """
    return {**base, **envelope.model_dump(), "message": envelope.message}


def _envelope_from_output(output: dict[str, Any]) -> ModelingErrorEnvelope | None:
    """Reconstruct an envelope from a tool output dict, if one is present.

    Returns ``None`` when the output does not carry the typed envelope fields.
    """
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


class ModelingService:
    def __init__(
        self,
        store: Any,
        mcp_client: LocalMCPClient | None = None,
        gateway: LLMGateway | None = None,
    ) -> None:
        self.store = store
        self.mcp_client = mcp_client or LocalMCPClient()
        self.gateway = gateway or LLMGateway()

    def capabilities(self) -> ModelingCapabilities:
        capabilities = self.mcp_client.capabilities()
        return ModelingCapabilities(
            safety_notes=[
                "MCP roda localmente; nenhum MCP remoto fica exposto no MVP.",
                (
                    "Adições e alterações normais autoexecutam; deleções, "
                    "ações destrutivas e high-risk exigem aprovação."
                ),
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
        plan, source, fallback_reason = self._build_plan(payload)
        plan = plan.model_copy(
            update={"planner_source": source, "fallback_reason": fallback_reason}
        )
        return self._persist_plan(plan, source, fallback_reason)

    async def create_plan_async(self, payload: ModelingPlanCreate) -> ModelingPlan:
        plan, source, fallback_reason = await self._build_plan_async(payload)
        plan = plan.model_copy(
            update={"planner_source": source, "fallback_reason": fallback_reason}
        )
        return self._persist_plan(plan, source, fallback_reason)

    def _persist_plan(
        self, plan: ModelingPlan, source: ModelingPlannerSource, fallback_reason: str | None
    ) -> ModelingPlan:
        plan = apply_modeling_policy(plan)
        self.store.upsert_modeling_plan(plan)
        metadata: dict[str, Any] = {
            "plan_id": plan.id,
            "software": plan.software_choice.value,
            "step_count": len(plan.steps),
            "mode": plan.mode.value,
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
            if ModelCapability.chat in model.capabilities and model.provider == ProviderName.openai
        ]
        if not chat_models:
            return None
        default = next((model for model in chat_models if model.default), None)
        chosen = default or chat_models[0]
        # When the model id is unresolved (no provider_model_id) and we're not in
        # allow_dev_llm mode, surface that as "unavailable" so we fall back.
        if not chosen.provider_model_id and not settings.allow_dev_llm:
            return None
        return chosen

    def _resolve_knowledge_bases(self, knowledge_base_ids: list[str]) -> list[KnowledgeBase]:
        if not knowledge_base_ids or not hasattr(self.store, "list_knowledge_bases"):
            return []
        known = {kb.id: kb for kb in self.store.list_knowledge_bases()}
        return [known[item] for item in knowledge_base_ids if item in known]

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
            output = self._dispatch_step(step, plan=plan)
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
        self,
        snapshot_id: str,
        payload: ModelingSnapshotRestore | None = None,
    ) -> ModelingSnapshotRestoreResult:
        if not hasattr(self.store, "get_modeling_snapshot"):
            raise RuntimeError("Backend store não implementa get_modeling_snapshot.")
        request = payload or ModelingSnapshotRestore()
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

        auto_snapshot: ModelingSnapshot | None = None
        if not request.force and workspace.is_dir() and any(workspace.iterdir()):
            auto_snapshot = self.create_snapshot(
                ModelingSnapshotCreate(
                    project_id=snapshot.project_id,
                    plan_id=snapshot.plan_id,
                    parent_snapshot_id=snapshot.id,
                    label=f"auto: pré-restore de {snapshot.id}",
                    reason=(
                        request.reason or f"Backup automático antes de restaurar {snapshot.id}."
                    ),
                )
            )

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
                    "reason": request.reason,
                    "force": request.force,
                    "auto_snapshot_id": auto_snapshot.id if auto_snapshot else None,
                },
            ),
        )
        return ModelingSnapshotRestoreResult(
            snapshot=updated,
            auto_snapshot=auto_snapshot,
            restored_file_count=len(restored_paths),
        )

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

    def run_printability(self, payload: ModelingPrintabilityRequest) -> ModelingPrintabilityReport:
        step = ModelingPlanStep(
            seq=1,
            title="Validar printability",
            software=ModelingSoftware.blender,
            tool_name="blender.validate_printability",
            risk_level=ModelingRiskLevel.low,
            approval_required=False,
            input_json={
                "checks": payload.checks,
                "printer_profile": payload.printer_profile,
                "file_id": payload.file_id,
            },
        )
        output = self.mcp_client.execute_step(
            step,
            plan_id=payload.plan_id,
            project_id=payload.project_id,
        )

        report = self._printability_report_from_output(payload, output)
        if hasattr(self.store, "add_modeling_printability_report"):
            self.store.add_modeling_printability_report(report)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.printability_validated",
                metadata={
                    "report_id": report.id,
                    "plan_id": payload.plan_id,
                    "file_id": payload.file_id,
                    "transport": str(output.get("transport") or "mock"),
                    "issue_count": len(report.issues),
                    "risk_score": report.risk_score,
                },
            ),
        )
        return report

    def list_printability_reports(
        self, *, plan_id: str | None = None, file_id: str | None = None
    ) -> list[ModelingPrintabilityReport]:
        if not hasattr(self.store, "list_modeling_printability_reports"):
            return []
        return self.store.list_modeling_printability_reports(plan_id=plan_id, file_id=file_id)

    @staticmethod
    def _printability_report_from_output(
        payload: ModelingPrintabilityRequest, output: dict[str, Any]
    ) -> ModelingPrintabilityReport:
        result = output.get("result") if isinstance(output.get("result"), dict) else {}
        is_real_run = output.get("transport") == "stdio" and output.get("ok")
        if is_real_run and result:
            raw_issues = result.get("issues") or []
            issues = [
                ModelingPrintabilityIssue(**ModelingService._normalize_printability_issue(item))
                for item in raw_issues
                if isinstance(item, dict)
            ]
            recommendations = ModelingService._printability_recommendations(issues, result)
            return ModelingPrintabilityReport(
                project_id=payload.project_id,
                plan_id=payload.plan_id,
                step_id=payload.step_id,
                file_id=payload.file_id,
                checks_executed=list(result.get("checks_executed") or payload.checks),
                issues=issues,
                metrics=dict(result.get("metrics") or {}),
                recommendations=recommendations,
                risk_score=float(result.get("risk_score") or 0.0),
                summary=str(result.get("message") or "Printability validada."),
                report_json={**result, "recommendations": recommendations},
            )
        return ModelingPrintabilityReport(
            project_id=payload.project_id,
            plan_id=payload.plan_id,
            step_id=payload.step_id,
            file_id=payload.file_id,
            checks_executed=list(payload.checks),
            issues=[],
            metrics={},
            recommendations=[
                (
                    "Configure TRUTHS_FORGE_BLENDER_EXECUTABLE para trocar o placeholder "
                    "por validação real."
                )
            ],
            risk_score=0.0,
            summary=(
                "Blender não está conectado; relatório de printability é placeholder. "
                "Configure TRUTHS_FORGE_BLENDER_EXECUTABLE para validar de verdade."
            ),
            report_json=output,
        )

    @staticmethod
    def _normalize_printability_issue(item: dict[str, Any]) -> dict[str, Any]:
        recommendation = item.get("recommendation")
        if not isinstance(recommendation, str) or not recommendation.strip():
            recommendation = ModelingService._recommendation_for_issue(item)
        return {**item, "recommendation": recommendation}

    @staticmethod
    def _recommendation_for_issue(issue: dict[str, Any]) -> str:
        check = str(issue.get("check") or "")
        if check in {"non_manifold", "volume", "is_solid"}:
            return "Reparar malha/corpo fechado antes de exportar para impressão."
        if check in {"thickness_approx", "wall_thickness_approx", "thin_features"}:
            return "Aumentar espessura mínima ou aplicar solidify antes da impressão."
        if check == "overhang_approx":
            return "Reorientar peça ou planejar suportes no slicer."
        if check in {"loose_parts", "normals"}:
            return "Limpar geometria e recalcular normais antes do export final."
        if check == "bounding_box":
            return "Revisar escala e dimensões mínimas do perfil de impressora."
        return "Revisar o aviso antes de aprovar execução/export final."

    @staticmethod
    def _printability_recommendations(
        issues: list[ModelingPrintabilityIssue], result: dict[str, Any]
    ) -> list[str]:
        raw = result.get("recommendations")
        if isinstance(raw, list):
            recommendations = [str(item).strip() for item in raw if str(item).strip()]
        else:
            recommendations = []
        for issue in issues:
            if issue.recommendation:
                recommendations.append(issue.recommendation)
        return list(dict.fromkeys(recommendations))

    def _dispatch_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> dict[str, Any]:
        """Route a step to the right local handler.

        ``project_store.*`` tools are handled inline by the service because the
        project store lives in the same process. Everything else goes through
        the MCP client boundary, which delegates to the adapter or falls back
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
            snapshot = self.create_snapshot(
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
            return _envelope_into_output(
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
        envelope = _envelope_from_output(output) if not ok else None
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
        model_version_ids = self._register_model_versions(
            created_or_existing,
            output=output,
            plan=plan,
            step=step,
        )
        return {
            **output,
            "platform_file_ids": [platform_file.id for platform_file in created_or_existing],
            "model_version_ids": model_version_ids,
        }

    def _register_model_versions(
        self,
        files: list[PlatformFile],
        *,
        output: dict[str, Any],
        plan: ModelingPlan,
        step: ModelingPlanStep,
    ) -> list[str]:
        if not hasattr(self.store, "add_modeling_model_version"):
            return []
        existing_versions = (
            self.store.list_modeling_model_versions(project_id=plan.project_id)
            if hasattr(self.store, "list_modeling_model_versions")
            else []
        )
        existing_by_source = {
            version.source_file_id: version
            for version in existing_versions
            if version.source_file_id
        }
        version_ids: list[str] = []
        for platform_file in files:
            existing = existing_by_source.get(platform_file.id)
            if existing:
                version_ids.append(existing.id)
                continue
            version = ModelingModelVersion(
                project_id=plan.project_id,
                plan_id=plan.id,
                step_id=step.id,
                software=step.software,
                source_file_id=platform_file.id,
                file_ids=[platform_file.id],
                export_format=Path(platform_file.filename).suffix.lower().lstrip(".") or None,
                label=f"{step.software.value} export {platform_file.filename}",
                notes=str(output.get("message") or ""),
                metadata={
                    "conversation_id": plan.conversation_id,
                    "tool_name": step.tool_name,
                    "artifact_path": platform_file.storage_path,
                    "checksum_sha256": platform_file.checksum_sha256,
                },
            )
            self.store.add_modeling_model_version(version)
            version_ids.append(version.id)
        return version_ids

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
