"""Tests pinning the v2 service split (ADR-013).

These tests don't re-cover behaviour already exercised by
``test_modeling_routes.py`` / ``test_planner_llm.py``. They lock the
**composition** introduced by Onda 1.3 so a future refactor cannot
silently re-merge the focused services into the facade.
"""

from __future__ import annotations

from app.modeling.artifacts import ModelingArtifactService
from app.modeling.executor import ModelingExecutorService, envelope_from_output
from app.modeling.planner_service import ModelingPlannerService
from app.modeling.printability import ModelingPrintabilityService
from app.modeling.service import ModelingService
from app.modeling.snapshot_service import ModelingSnapshotService
from app.storage.store import get_store


def test_service_composes_five_focused_services() -> None:
    service = ModelingService(store=get_store())
    assert isinstance(service.planner, ModelingPlannerService)
    assert isinstance(service.snapshots, ModelingSnapshotService)
    assert isinstance(service.artifacts, ModelingArtifactService)
    assert isinstance(service.executor, ModelingExecutorService)
    assert isinstance(service.printability, ModelingPrintabilityService)


def test_executor_holds_back_references_to_collaborators() -> None:
    service = ModelingService(store=get_store())
    assert service.executor.snapshots is service.snapshots
    assert service.executor.artifacts is service.artifacts
    assert service.executor.mcp_client is service.mcp_client


def test_planner_service_shares_gateway_with_facade() -> None:
    service = ModelingService(store=get_store())
    assert service.planner.gateway is service.gateway


def test_envelope_from_output_returns_none_when_no_error_code() -> None:
    assert envelope_from_output({"ok": True}) is None


def test_envelope_from_output_reconstructs_envelope() -> None:
    payload = {
        "ok": False,
        "error_code": "blender.timeout",
        "message": "estourou timeout",
        "retryable": True,
        "safe_to_retry_after_snapshot_restore": True,
        "host_details": {"timeout_seconds": 90},
    }
    envelope = envelope_from_output(payload)
    assert envelope is not None
    assert envelope.error_code == "blender.timeout"
    assert envelope.retryable is True
    assert envelope.safe_to_retry_after_snapshot_restore is True
    assert envelope.host_details == {"timeout_seconds": 90}


def test_facade_re_exports_envelope_helpers_for_backwards_compat() -> None:
    # Old callers imported ``_envelope_into_output`` / ``_envelope_from_output``
    # from ``app.modeling.service``. Onda 1.3 moved them to ``executor``;
    # the re-export keeps existing code working.
    from app.modeling import service as legacy_module

    assert hasattr(legacy_module, "_envelope_into_output")
    assert hasattr(legacy_module, "_envelope_from_output")
    assert hasattr(legacy_module, "ARTIFACT_CONTENT_TYPES")


def test_facade_get_modeling_service_returns_modeling_service() -> None:
    from app.modeling.service import get_modeling_service

    instance = get_modeling_service(get_store())
    assert isinstance(instance, ModelingService)
