"""Printability validation extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
the ``blender.validate_printability`` workflow: invoking the adapter via
the MCP client, normalising issue payloads, deduping recommendations and
persisting a :class:`ModelingPrintabilityReport`.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import (
    AuditEvent,
    ModelingPlanStep,
    ModelingPrintabilityIssue,
    ModelingPrintabilityReport,
    ModelingPrintabilityRequest,
    ModelingRiskLevel,
    ModelingSoftware,
)
from app.modeling.mcp_client import LocalMCPClient


class ModelingPrintabilityService:
    """Runs printability checks and persists the resulting reports."""

    def __init__(self, store: Any, mcp_client: LocalMCPClient) -> None:
        self.store = store
        self.mcp_client = mcp_client

    def run(self, payload: ModelingPrintabilityRequest) -> ModelingPrintabilityReport:
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

        report = self._report_from_output(payload, output)
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

    def list(
        self, *, plan_id: str | None = None, file_id: str | None = None
    ) -> list[ModelingPrintabilityReport]:
        if not hasattr(self.store, "list_modeling_printability_reports"):
            return []
        return self.store.list_modeling_printability_reports(plan_id=plan_id, file_id=file_id)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _report_from_output(
        payload: ModelingPrintabilityRequest, output: dict[str, Any]
    ) -> ModelingPrintabilityReport:
        result = output.get("result") if isinstance(output.get("result"), dict) else {}
        is_real_run = output.get("transport") == "stdio" and output.get("ok")
        if is_real_run and result:
            raw_issues = result.get("issues") or []
            issues = [
                ModelingPrintabilityIssue(
                    **ModelingPrintabilityService._normalize_issue(item)
                )
                for item in raw_issues
                if isinstance(item, dict)
            ]
            recommendations = ModelingPrintabilityService._recommendations(issues, result)
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
    def _normalize_issue(item: dict[str, Any]) -> dict[str, Any]:
        recommendation = item.get("recommendation")
        if not isinstance(recommendation, str) or not recommendation.strip():
            recommendation = ModelingPrintabilityService._recommendation_for_issue(item)
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
    def _recommendations(
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


__all__ = ["ModelingPrintabilityService"]
