from fastapi.testclient import TestClient

from app.main import app
from app.modeling.blender_adapter import BlenderAdapter


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
    assert all(
        step["output_json"].get("transport") == "mock"
        for step in execution_payload["plan"]["steps"]
    )


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
    assert payload["manifest"]["sha256"]
