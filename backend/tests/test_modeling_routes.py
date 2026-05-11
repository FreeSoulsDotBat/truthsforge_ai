import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modeling.blender_adapter import BlenderAdapter
from app.modeling.workspace import workspace_dir
from app.storage.store import get_store


def test_modeling_capabilities_are_exposed() -> None:
    client = TestClient(app)
    response = client.get("/api/3d/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local_mcp"
    adapter_tools = {adapter["software"]: adapter["tools"] for adapter in payload["adapters"]}
    assert "blender.create_mesh_primitive" in adapter_tools["blender"]
    assert "fusion.create_sketch" in adapter_tools["fusion"]


def test_modeling_plan_requires_approval_and_can_execute_after_approval() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/3d/plans",
        json={
            "prompt": "Crie uma peça paramétrica de 40 mm com furo central.",
            "mode": "approval_required",
        },
    )

    assert created.status_code == 200
    plan = created.json()
    assert plan["software_choice"] == "fusion"
    assert plan["status"] == "waiting_approval"
    assert any(step["approval_required"] for step in plan["steps"])

    blocked = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert blocked.status_code == 200
    assert blocked.json()["blocked_step_ids"]

    approved = client.post(
        f"/api/3d/plans/{plan['id']}/approve",
        json={"decision": "approve", "reason": "teste automatizado"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    execution_payload = executed.json()
    assert execution_payload["plan"]["status"] == "completed"
    assert len(execution_payload["executed_step_ids"]) == len(plan["steps"])
    for step in execution_payload["plan"]["steps"]:
        if step["tool_name"] == "project_store.create_snapshot":
            assert step["output_json"]["transport"] == "local"
            assert step["output_json"]["snapshot_id"].startswith("m3d_snapshot_")
        else:
            assert step["output_json"]["transport"] == "mock"


def test_blender_plan_uses_mcp_boundary_without_desktop_adapter(monkeypatch) -> None:
    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)

    client = TestClient(app)
    created = client.post(
        "/api/3d/plans",
        json={
            "prompt": "Crie um cubo visual com bevel no Blender.",
            "mode": "approval_required",
            "software_override": "blender",
        },
    )

    assert created.status_code == 200
    plan = created.json()
    assert plan["software_choice"] == "blender"

    approved = client.post(
        f"/api/3d/plans/{plan['id']}/approve",
        json={"decision": "approve", "reason": "teste automatizado"},
    )
    assert approved.status_code == 200

    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    execution_payload = executed.json()
    blender_steps = [
        step
        for step in execution_payload["plan"]["steps"]
        if step["tool_name"].startswith("blender.")
    ]
    assert blender_steps
    assert all(step["output_json"]["mcp_server"] == "blender_mcp" for step in blender_steps)
    assert all(step["output_json"]["transport"] == "mock" for step in blender_steps)


def test_modeling_snapshot_records_manifest() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/3d/snapshots",
        json={"label": "Snapshot teste", "reason": "antes da execução"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "Snapshot teste"
    assert payload["manifest"]["id"] == payload["id"]
    assert payload["manifest"]["label"] == "Snapshot teste"
    assert payload["storage_path"]
    assert Path(payload["storage_path"], "manifest.json").is_file()


def test_modeling_snapshot_copies_and_restores_workspace_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "prj_snap_test"
    plan_id = "m3d_plan_snap_test"
    workspace = workspace_dir(project_id, plan_id)
    workspace.mkdir(parents=True, exist_ok=True)
    blend_path = workspace / "workspace.blend"
    blend_path.write_bytes(b"original-blend-bytes")
    (workspace / "exports").mkdir(exist_ok=True)
    stl_path = workspace / "exports" / "preview.stl"
    stl_path.write_bytes(b"solid mesh original")

    client = TestClient(app)
    created = client.post(
        "/api/3d/snapshots",
        json={
            "project_id": project_id,
            "plan_id": plan_id,
            "label": "antes da edição",
            "reason": "teste",
        },
    )
    assert created.status_code == 200
    snapshot = created.json()
    relative_paths = {item["relative_path"] for item in snapshot["files"]}
    assert "workspace.blend" in relative_paths
    assert "exports/preview.stl" in relative_paths
    assert snapshot["storage_path"]
    manifest_path = Path(snapshot["storage_path"], "manifest.json")
    assert manifest_path.is_file()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["label"] == "antes da edição"
    assert manifest_data["files"]

    # Modify the workspace to simulate destructive operations.
    blend_path.write_bytes(b"mutated-blend-bytes")
    stl_path.write_bytes(b"mutated stl content")

    restored = client.post(
        f"/api/3d/snapshots/{snapshot['id']}/restore",
        json={"reason": "rollback teste"},
    )
    assert restored.status_code == 200
    payload = restored.json()
    assert payload["snapshot"]["restored_at"]
    assert payload["restored_file_count"] >= 2
    auto = payload["auto_snapshot"]
    assert auto is not None, "Auto-snapshot pré-restore deve ser criado por padrão."
    assert auto["label"].startswith("auto: pré-restore")
    assert auto["parent_snapshot_id"] == snapshot["id"]
    # The auto-snapshot captured the mutated workspace state so we can undo
    # the undo if needed.
    auto_blend_capture = next(
        item for item in auto["files"] if item["relative_path"] == "workspace.blend"
    )
    assert auto_blend_capture["size_bytes"] == len(b"mutated-blend-bytes")
    assert blend_path.read_bytes() == b"original-blend-bytes"
    assert stl_path.read_bytes() == b"solid mesh original"


def test_modeling_snapshot_restore_force_skips_auto_snapshot(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "prj_snap_force"
    plan_id = "m3d_plan_snap_force"
    workspace = workspace_dir(project_id, plan_id)
    workspace.mkdir(parents=True, exist_ok=True)
    blend_path = workspace / "workspace.blend"
    blend_path.write_bytes(b"original")

    client = TestClient(app)
    created = client.post(
        "/api/3d/snapshots",
        json={"project_id": project_id, "plan_id": plan_id, "label": "snap"},
    )
    snapshot = created.json()
    blend_path.write_bytes(b"mutated")

    restored = client.post(
        f"/api/3d/snapshots/{snapshot['id']}/restore",
        json={"force": True, "reason": "ignorar auto-snapshot"},
    )
    assert restored.status_code == 200
    body = restored.json()
    assert body["auto_snapshot"] is None
    assert blend_path.read_bytes() == b"original"


def test_modeling_snapshot_excludes_runner_scaffolding(monkeypatch, tmp_path) -> None:
    from app.modeling.workspace import iter_workspace_files

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    workspace = workspace_dir("prj_exclude", "m3d_plan_exclude")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "workspace.blend").write_bytes(b"x")
    (workspace / "01-blender.create_mesh_primitive.result.json").write_text("{}")
    (workspace / "01-m3d_step_abc.job.json").write_text("{}")
    (workspace / "exports").mkdir()
    (workspace / "exports" / "preview.stl").write_bytes(b"y")

    captured = {path.relative_to(workspace).as_posix() for path in iter_workspace_files(workspace)}

    assert "workspace.blend" in captured
    assert "exports/preview.stl" in captured
    assert "01-blender.create_mesh_primitive.result.json" not in captured
    assert "01-m3d_step_abc.job.json" not in captured


def test_modeling_snapshot_restore_rejects_path_outside_modeling_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "prj_snap_escape"
    plan_id = "m3d_plan_snap_escape"
    workspace = workspace_dir(project_id, plan_id)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "workspace.blend").write_bytes(b"x")

    client = TestClient(app)
    created = client.post(
        "/api/3d/snapshots",
        json={"project_id": project_id, "plan_id": plan_id, "label": "snap"},
    )
    snapshot_id = created.json()["id"]

    from app.storage.store import get_store

    store = get_store()
    persisted = store.get_modeling_snapshot(snapshot_id)
    # Tamper the stored workspace_path to point outside the modeling jail.
    tampered = persisted.model_copy(update={"workspace_path": str(tmp_path / "elsewhere")})
    store.upsert_modeling_snapshot(tampered)

    rejected = client.post(f"/api/3d/snapshots/{snapshot_id}/restore", json={})
    assert rejected.status_code == 400


def test_modeling_tool_calls_persisted_during_execution() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/3d/plans",
        json={
            "prompt": "Crie um cubo simples no Blender.",
            "mode": "approval_required",
            "software_override": "blender",
        },
    )
    plan = created.json()
    plan_id = plan["id"]

    approved = client.post(
        f"/api/3d/plans/{plan_id}/approve",
        json={"decision": "approve", "reason": "teste"},
    )
    assert approved.status_code == 200

    executed = client.post(f"/api/3d/plans/{plan_id}/execute")
    assert executed.status_code == 200
    body = executed.json()
    assert body["tool_call_ids"]
    assert len(body["tool_call_ids"]) == len(body["executed_step_ids"])

    listed = client.get(f"/api/3d/tool-calls?plan_id={plan_id}")
    assert listed.status_code == 200
    records = listed.json()
    assert records
    assert {item["plan_id"] for item in records} == {plan_id}
    assert all(item["tool_name"] for item in records)
    assert all(item["status"] == "ok" for item in records)


def test_modeling_failure_is_logged_with_error_envelope_fields(monkeypatch) -> None:
    from app.modeling import service as service_module

    class FailingClient:
        def capabilities(self):  # pragma: no cover - not used in this test
            return {}

        def is_connected(self, software):  # pragma: no cover
            return False

        def transport(self, software):  # pragma: no cover
            return "mock"

        def adapter_status(self, software):  # pragma: no cover
            return "adapter_mock"

        def detail(self, software):  # pragma: no cover
            return ""

        def execute_step(self, step, *, plan_id=None, project_id=None):
            return {
                "ok": False,
                "mcp_server": "blender_mcp",
                "transport": "stdio",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "message": "Falha simulada.",
                "error_code": "blender.simulated_failure",
                "retryable": True,
                "safe_to_retry_after_snapshot_restore": True,
                "input": step.input_json,
            }

    from app.api.routes import modeling as modeling_route

    failing_service = service_module.ModelingService(store=get_store(), mcp_client=FailingClient())
    monkeypatch.setattr(modeling_route, "get_modeling_service", lambda store: failing_service)

    client = TestClient(app)
    created = client.post(
        "/api/3d/plans",
        json={
            "prompt": "Crie um cubo simples no Blender.",
            "mode": "approval_required",
            "software_override": "blender",
        },
    )
    plan = created.json()
    plan_id = plan["id"]
    client.post(
        f"/api/3d/plans/{plan_id}/approve",
        json={"decision": "approve", "reason": "teste"},
    )
    executed = client.post(f"/api/3d/plans/{plan_id}/execute")
    assert executed.status_code == 200
    assert executed.json()["plan"]["status"] == "failed"

    tool_calls = client.get(f"/api/3d/tool-calls?plan_id={plan_id}").json()
    assert tool_calls
    failed = [item for item in tool_calls if item["status"] == "error"]
    assert failed
    assert any(item["error_code"] == "blender.simulated_failure" for item in failed)
    assert any(item["retryable"] is True for item in failed)
    assert any(item["safe_to_retry_after_snapshot_restore"] is True for item in failed)
