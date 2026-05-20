import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.contracts import ModelingExecutionMode, ModelingPlanCreate, ModelingSoftware
from app.main import app
from app.modeling.blender_adapter import BlenderAdapter
from app.modeling.fusion_adapter import FusionDesktopAdapter
from app.modeling.service import get_modeling_service
from app.modeling.workspace import workspace_dir
from app.storage.store import get_store


def _create_plan_via_service(**kwargs: Any) -> dict[str, Any]:
    """Build a plan through ``ModelingService`` instead of the removed
    ``POST /api/3d/plans`` endpoint (ADR-013, Onda 2.11).

    Returns the plan as a JSON-serialisable dict so existing assertions
    keep working without touching every line.
    """

    payload = ModelingPlanCreate(**kwargs)
    plan = get_modeling_service(get_store()).create_plan(payload)
    return json.loads(plan.model_dump_json())


EXPECTED_BLENDER_TOOLS = {
    "blender.create_mesh_primitive",
    "blender.apply_bevel",
    "blender.apply_boolean",
    "blender.apply_subdivision",
    "blender.apply_solidify",
    "blender.assign_material",
    "blender.measure_object",
    "blender.repair_non_manifold",
    "blender.validate_mesh",
    "blender.validate_printability",
    "blender.export_stl",
    "blender.export_obj",
    "blender.export_3mf",
}


def test_modeling_capabilities_are_exposed() -> None:
    client = TestClient(app)
    response = client.get("/api/3d/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local_mcp"
    adapter_tools = {adapter["software"]: adapter["tools"] for adapter in payload["adapters"]}
    assert EXPECTED_BLENDER_TOOLS.issubset(set(adapter_tools["blender"]))
    assert "fusion.create_sketch" in adapter_tools["fusion"]
    assert "fusion.validate_printability" in adapter_tools["fusion"]


def test_client_trace_event_uses_max_sequence_lookup(monkeypatch) -> None:
    from app.api.routes import modeling as modeling_route

    class TraceStore:
        def __init__(self) -> None:
            self.events: list[Any] = []
            self.sequence_lookups: list[str] = []

        def list_trace_events(self, **kwargs: Any) -> list[Any]:
            raise AssertionError("record_client_trace_event should not list all events")

        def get_max_trace_sequence(self, *, trace_id: str) -> int:
            self.sequence_lookups.append(trace_id)
            return 41

        def record_trace_events_bulk(self, events: list[Any]) -> None:
            self.events.extend(events)

    store = TraceStore()
    monkeypatch.setattr(modeling_route, "get_store", lambda: store)
    with modeling_route._client_trace_lock:
        modeling_route._client_trace_timestamps.clear()

    client = TestClient(app)
    response = client.post(
        "/api/3d/traces/events",
        json={
            "trace_id": "mt_test_trace",
            "plan_id": "plan-1",
            "event_type": "ui.modal_opened",
            "level": "info",
            "payload": {"panel": "diagnostics"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ui"
    assert body["sequence"] == 42
    assert store.sequence_lookups == ["mt_test_trace"]
    assert store.events[0].sequence == 42


def test_modeling_plan_executes_fluid_steps_without_plan_approval(monkeypatch) -> None:
    monkeypatch.setattr(FusionDesktopAdapter, "is_available", lambda self: False)

    client = TestClient(app)
    plan = _create_plan_via_service(
        prompt="Crie uma peça paramétrica de 40 mm com furo central.",
        mode=ModelingExecutionMode.safe_auto,
    )

    assert plan["software_choice"] == "fusion"
    assert plan["status"] == "approved"
    assert all(step["approval_required"] is False for step in plan["steps"])
    assert all(step["tool_name"] != "project_store.create_snapshot" for step in plan["steps"])

    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    execution_payload = executed.json()
    assert execution_payload["plan"]["status"] == "completed"
    assert len(execution_payload["executed_step_ids"]) == len(plan["steps"])
    for step in execution_payload["plan"]["steps"]:
        assert step["output_json"]["transport"] == "mock"


def test_blender_plan_uses_mcp_boundary_without_desktop_adapter(monkeypatch) -> None:
    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)

    client = TestClient(app)
    plan = _create_plan_via_service(
        prompt="Crie um cubo visual com bevel no Blender.",
        mode=ModelingExecutionMode.safe_auto,
        software_override=ModelingSoftware.blender,
    )

    assert plan["software_choice"] == "blender"
    assert all(step["tool_name"] != "project_store.create_snapshot" for step in plan["steps"])

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


def test_modeling_plan_only_draft_does_not_execute_directly(monkeypatch) -> None:
    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)

    client = TestClient(app)
    plan = _create_plan_via_service(
        prompt="Planeje um cubo visual no Blender.",
        mode=ModelingExecutionMode.plan_only,
        software_override=ModelingSoftware.blender,
    )
    assert plan["status"] == "draft"

    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    execution_payload = executed.json()
    assert execution_payload["plan"]["status"] == "draft"
    assert execution_payload["executed_step_ids"] == []
    assert set(execution_payload["blocked_step_ids"]) == {step["id"] for step in plan["steps"]}
    assert "modo planejamento" in execution_payload["events"][0]


def _sse_event(text: str, event_name: str) -> dict[str, Any] | None:
    """Extrai o ``data`` JSON do primeiro bloco SSE com ``event: <name>``."""

    current_event: str | None = None
    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:") and current_event == event_name:
            return json.loads(line[len("data:") :].strip())
    return None


def test_chat_stream_proposes_plan_without_executing(monkeypatch) -> None:
    """P1 (gate de aprovação): a rota /api/chat/stream com modeling_3d
    ligado deve PROPOR o plano (status waiting_approval) e NÃO executar,
    mesmo em mode=safe_auto. A execução só acontece via /approve+/execute
    (acionados pelo card). Regressão da dor "o plano executa sem autorização".
    Ver specs/modeling-3d-fusion/chat-flow-redesign.md (P1).
    """

    monkeypatch.setattr(FusionDesktopAdapter, "is_available", lambda self: False)
    monkeypatch.setattr(settings, "require_chat_title", False)
    # Foca o teste no gate de aprovação (P1); a descoberta (P2) é coberta à
    # parte. Sem isso o teste tentaria uma chamada LLM de descoberta antes.
    monkeypatch.setattr(settings, "modeling_discovery_enabled", False)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "Crie uma placa 80x60x5mm com furo central de 10mm.",
            "title": "Placa parametrizada",
            "modeling_3d": {
                "enabled": True,
                "mode": "safe_auto",
                "software_override": "fusion",
            },
        },
    )
    assert response.status_code == 200

    plan_event = _sse_event(response.text, "modeling_plan")
    assert plan_event is not None, "stream não emitiu evento modeling_plan"
    plan = plan_event["plan"]

    # Núcleo da P1: parou para aprovação, não executou.
    assert plan["status"] == "waiting_approval"
    assert all(step["status"] == "pending" for step in plan["steps"])
    assert all(step["output_json"] in ({}, None) for step in plan["steps"])
    # Nenhum runtime status de execução concluída deve aparecer.
    assert "Execução MCP 3D concluída" not in response.text

    # A sessão ficou no estágio planning (aguardando aprovação), não editing.
    store = get_store()
    session = store.get_chat_session(plan_event["plan"]["conversation_id"])
    assert session.modeling_stage.value == "planning"
    assert session.modeling_plan_id == plan["id"]

    # O plano persistido também está waiting_approval (card mostra Aprovar).
    persisted = client.get(f"/api/3d/plans/{plan['id']}").json()
    assert persisted["status"] == "waiting_approval"


def test_chat_stream_asks_clarification_when_ambiguous(monkeypatch) -> None:
    """P2 (discovery): quando o agente avalia o pedido como ambíguo, a rota
    /api/chat/stream deve FAZER perguntas e NÃO criar plano; o chat fica em
    ``discovery``. Mockamos a avaliação para não depender do LLM.
    Ver specs/modeling-3d-fusion/chat-flow-redesign.md (P2).
    """

    from app.core.contracts import ModelingDiscoveryAssessment
    from app.modeling.service import ModelingService

    async def _fake_assess(
        self, prompt, *, history=None, software_override=None, threshold=None,
        has_existing_model=False,
    ):
        return ModelingDiscoveryAssessment(
            ready_to_plan=False,
            confidence=0.3,
            questions=["Qual a altura em mm?", "Qual o material?"],
            refined_brief="",
            rationale="pedido vago",
        )

    monkeypatch.setattr(settings, "require_chat_title", False)
    monkeypatch.setattr(settings, "modeling_discovery_enabled", True)
    monkeypatch.setattr(ModelingService, "assess_request_async", _fake_assess)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "quero uma peça",
            "title": "Peça vaga",
            "modeling_3d": {"enabled": True, "mode": "safe_auto"},
        },
    )
    assert response.status_code == 200

    # NÃO deve propor plano nenhum.
    assert _sse_event(response.text, "modeling_plan") is None
    # As perguntas aparecem no texto da resposta.
    assert "Qual a altura em mm?" in response.text
    assert "Qual o material?" in response.text

    # A sessão ficou em discovery, sem plano vinculado.
    meta = _sse_event(response.text, "meta")
    session = get_store().get_chat_session(meta["session_id"])
    assert session.modeling_stage.value == "discovery"
    assert session.modeling_plan_id is None


def _editing_session(store, **overrides):
    from app.core.contracts import ChatModelingStage, ChatSession

    session = ChatSession(
        title=overrides.pop("title", "Chat 3D em edição"),
        is_modeling_3d=True,
        modeling_stage=ChatModelingStage.editing,
        modeling_plan_id=overrides.pop("modeling_plan_id", "m3d_plan_prev"),
        **overrides,
    )
    store.upsert_chat_session(session)
    return session


def _mock_assess(monkeypatch, *, intent: str, ready: bool = True):
    from app.core.contracts import ModelingDiscoveryAssessment
    from app.modeling.service import ModelingService

    async def _fake(self, prompt, *, history=None, software_override=None,
                    threshold=None, has_existing_model=False):
        return ModelingDiscoveryAssessment(
            ready_to_plan=ready,
            confidence=0.95,
            questions=[] if ready else ["?"],
            refined_brief=prompt if ready else "",
            intent=intent,
            rationale="mock",
        )

    monkeypatch.setattr(ModelingService, "assess_request_async", _fake)


def test_chat_stream_edit_proposes_edit_plan_without_executing(monkeypatch) -> None:
    """P3: follow-up classificado como edição vira plano kind=edit e PARA no
    card (modo fluido desligado). Não executa."""

    from app.modeling.blender_adapter import BlenderAdapter

    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)
    monkeypatch.setattr(settings, "require_chat_title", False)
    _mock_assess(monkeypatch, intent="edit")

    store = get_store()
    session = _editing_session(store, modeling_fluid_mode=False)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "arredonde as bordas em 2mm",
            "title": "Editar peça",
            "session_id": session.id,
            "modeling_3d": {"enabled": True, "mode": "safe_auto", "software_override": "blender"},
        },
    )
    assert response.status_code == 200
    plan_event = _sse_event(response.text, "modeling_plan")
    assert plan_event is not None
    plan = plan_event["plan"]
    assert plan["status"] == "waiting_approval"
    assert all(step["status"] == "pending" for step in plan["steps"])

    persisted = client.get(f"/api/3d/plans/{plan['id']}").json()
    assert persisted["kind"] == "edit"
    assert persisted["parent_plan_id"] == "m3d_plan_prev"


def test_chat_stream_ambiguous_intent_asks(monkeypatch) -> None:
    """P3: quando a intenção edição-vs-novo é ambígua, a rota pergunta e não
    cria plano."""

    monkeypatch.setattr(settings, "require_chat_title", False)
    _mock_assess(monkeypatch, intent="ambiguous")

    store = get_store()
    session = _editing_session(store)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "faz um suporte",
            "title": "Ambíguo",
            "session_id": session.id,
            "modeling_3d": {"enabled": True, "mode": "safe_auto"},
        },
    )
    assert response.status_code == 200
    assert _sse_event(response.text, "modeling_plan") is None
    assert "edição do modelo atual" in response.text or "começar" in response.text
    refreshed = store.get_chat_session(session.id)
    assert refreshed.modeling_stage.value == "editing"


def test_chat_stream_fluid_edit_auto_executes(monkeypatch) -> None:
    """P3: com modo fluido ligado, edição aditiva sem high-risk auto-executa
    (pula o card)."""

    from app.modeling.blender_adapter import BlenderAdapter

    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)
    monkeypatch.setattr(settings, "require_chat_title", False)
    _mock_assess(monkeypatch, intent="edit")

    store = get_store()
    session = _editing_session(store, modeling_fluid_mode=True)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "adicione um chanfro de 1mm",
            "title": "Fluido",
            "session_id": session.id,
            "modeling_3d": {"enabled": True, "mode": "safe_auto", "software_override": "blender"},
        },
    )
    assert response.status_code == 200
    plan_event = _sse_event(response.text, "modeling_plan")
    assert plan_event is not None
    assert plan_event["plan"]["status"] == "completed"


def test_execute_advances_chat_to_editing(monkeypatch) -> None:
    """P3: ao executar um plano vinculado a um chat 3D via card, o chat avança
    para ``editing`` (para que follow-ups sejam tratados como edição).
    Ver specs/modeling-3d-fusion/chat-flow-redesign.md (P3).
    """

    from app.core.contracts import ChatModelingStage, ChatSession
    from app.modeling.blender_adapter import BlenderAdapter

    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)

    store = get_store()
    session = ChatSession(
        title="Chat 3D edição",
        is_modeling_3d=True,
        modeling_stage=ChatModelingStage.planning,
    )
    store.upsert_chat_session(session)

    plan = _create_plan_via_service(
        prompt="Crie um cubo visual no Blender.",
        mode=ModelingExecutionMode.safe_auto,
        software_override=ModelingSoftware.blender,
        conversation_id=session.id,
    )

    client = TestClient(app)
    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    assert executed.json()["plan"]["status"] == "completed"

    refreshed = store.get_chat_session(session.id)
    assert refreshed.modeling_stage == ChatModelingStage.editing
    assert refreshed.modeling_plan_id == plan["id"]


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


def test_list_snapshots_supports_plan_id_filter(monkeypatch, tmp_path) -> None:
    """GET /api/3d/snapshots?plan_id=... must filter server-side."""
    import uuid

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)

    # Use unique plan/project IDs per run so the assertions hold even when
    # the dev store accumulates snapshots from previous test runs.
    suffix = uuid.uuid4().hex[:8]
    plan_a = f"plan_filter_a_{suffix}"
    plan_b = f"plan_filter_b_{suffix}"
    project_a = f"prj_a_{suffix}"
    project_b = f"prj_b_{suffix}"
    bogus_plan = f"does_not_exist_{suffix}"

    first = client.post(
        "/api/3d/snapshots",
        json={"plan_id": plan_a, "project_id": project_a, "label": "A"},
    ).json()
    second = client.post(
        "/api/3d/snapshots",
        json={"plan_id": plan_b, "project_id": project_b, "label": "B"},
    ).json()

    all_snapshots = client.get("/api/3d/snapshots").json()
    ids = {item["id"] for item in all_snapshots}
    assert {first["id"], second["id"]}.issubset(ids)

    only_a = client.get(f"/api/3d/snapshots?plan_id={plan_a}").json()
    assert {item["id"] for item in only_a} == {first["id"]}

    only_b = client.get(f"/api/3d/snapshots?plan_id={plan_b}").json()
    assert {item["id"] for item in only_b} == {second["id"]}

    only_prj_a = client.get(f"/api/3d/snapshots?project_id={project_a}").json()
    assert {item["id"] for item in only_prj_a} == {first["id"]}

    combined = client.get(f"/api/3d/snapshots?plan_id={plan_a}&project_id={project_a}").json()
    assert {item["id"] for item in combined} == {first["id"]}

    no_match = client.get(f"/api/3d/snapshots?plan_id={bogus_plan}").json()
    assert no_match == []


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
    plan = _create_plan_via_service(
        prompt="Crie um cubo simples no Blender.",
        mode=ModelingExecutionMode.approval_required,
        software_override=ModelingSoftware.blender,
    )
    plan_id = plan["id"]

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


def test_modeling_export_artifacts_create_platform_files_and_versions(
    monkeypatch, tmp_path
) -> None:
    from app.modeling import service as service_module

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = "prj_artifacts"
    plan_id = "m3d_plan_artifacts"
    artifact = (
        tmp_path / "modeling" / "projects" / project_id / "plans" / plan_id / "exports" / "part.stl"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"solid test")

    class ExportClient:
        def capabilities(self):  # pragma: no cover - not used in this test
            return {}

        def is_connected(self, software):  # pragma: no cover
            return True

        def transport(self, software):  # pragma: no cover
            return "stdio"

        def adapter_status(self, software):  # pragma: no cover
            return "available"

        def detail(self, software):  # pragma: no cover
            return "ok"

        def execute_step(self, step, *, plan_id=None, project_id=None):
            return {
                "ok": True,
                "mcp_server": "blender_mcp",
                "transport": "stdio",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "message": "STL exportado.",
                "artifact_paths": [str(artifact)],
            }

    from app.api.routes import modeling as modeling_route

    fake_service = service_module.ModelingService(store=get_store(), mcp_client=ExportClient())
    monkeypatch.setattr(modeling_route, "get_modeling_service", lambda store: fake_service)

    client = TestClient(app)
    plan = json.loads(
        fake_service.create_plan(
            ModelingPlanCreate(
                prompt="Exporte um STL no Blender.",
                project_id=project_id,
                mode=ModelingExecutionMode.safe_auto,
                software_override=ModelingSoftware.blender,
            )
        ).model_dump_json()
    )
    executed = client.post(f"/api/3d/plans/{plan['id']}/execute")
    assert executed.status_code == 200
    export_steps = [
        step
        for step in executed.json()["plan"]["steps"]
        if step["tool_name"] == "blender.export_stl"
    ]
    assert export_steps
    output = export_steps[0]["output_json"]
    assert output["platform_file_ids"]
    assert output["model_version_ids"]

    store = get_store()
    versions = store.list_modeling_model_versions(project_id=project_id)
    assert any(version.id in output["model_version_ids"] for version in versions)
    assert versions[0].file_ids
    assert versions[0].export_format == "stl"

    tool_calls = client.get(f"/api/3d/tool-calls?plan_id={plan['id']}").json()
    export_call = next(item for item in tool_calls if item["tool_name"] == "blender.export_stl")
    assert export_call["artifact_file_ids"] == output["platform_file_ids"]
    assert export_call["model_version_ids"] == output["model_version_ids"]

    listed_versions = client.get(f"/api/3d/model-versions?project_id={project_id}")
    assert listed_versions.status_code == 200
    assert any(item["id"] == versions[0].id for item in listed_versions.json())


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
    plan = json.loads(
        failing_service.create_plan(
            ModelingPlanCreate(
                prompt="Crie um cubo simples no Blender.",
                mode=ModelingExecutionMode.safe_auto,
                software_override=ModelingSoftware.blender,
            )
        ).model_dump_json()
    )
    plan_id = plan["id"]
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


def test_modeling_validate_printability_falls_back_to_mock_report(monkeypatch) -> None:
    monkeypatch.setattr(BlenderAdapter, "is_available", lambda self: False)
    client = TestClient(app)

    response = client.post(
        "/api/3d/validate/printability",
        json={
            "plan_id": "m3d_plan_does_not_exist",
            "checks": ["non_manifold", "volume", "non_manifold"],
            "printer_profile": "bambu_x1c_pla",
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["id"].startswith("m3d_print_report_")
    assert report["risk_score"] == 0.0
    assert report["issues"] == []
    assert report["checks_executed"] == ["non_manifold", "volume"]
    assert "Blender não está conectado" in report["summary"]

    listed = client.get(f"/api/3d/printability-reports?plan_id={report['plan_id']}").json()
    assert any(item["id"] == report["id"] for item in listed)


def test_modeling_validate_printability_parses_real_runner_output(monkeypatch) -> None:
    from app.api.routes import modeling as modeling_route
    from app.modeling import service as service_module

    class FakeStdioClient:
        def capabilities(self):  # pragma: no cover
            return {}

        def is_connected(self, software):  # pragma: no cover
            return True

        def transport(self, software):  # pragma: no cover
            return "stdio"

        def adapter_status(self, software):  # pragma: no cover
            return "available"

        def detail(self, software):  # pragma: no cover
            return ""

        def execute_step(self, step, *, plan_id=None, project_id=None):
            return {
                "ok": True,
                "mcp_server": "blender_mcp",
                "transport": "stdio",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "result": {
                    "message": "Printability validada em 1 objeto.",
                    "objects_inspected": 1,
                    "checks_executed": ["non_manifold", "volume"],
                    "issues": [
                        {
                            "check": "non_manifold",
                            "severity": "error",
                            "message": "3 aresta(s) não-manifold em Cube.",
                            "detail": {"object": "Cube", "edge_count": 3},
                        }
                    ],
                    "metrics": {"Cube": {"volume_mm3": 8000.0}},
                    "risk_score": 0.5,
                },
            }

    fake_service = service_module.ModelingService(store=get_store(), mcp_client=FakeStdioClient())
    monkeypatch.setattr(modeling_route, "get_modeling_service", lambda store: fake_service)

    client = TestClient(app)
    response = client.post(
        "/api/3d/validate/printability",
        json={"plan_id": "m3d_plan_fake", "checks": ["non_manifold", "volume"]},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["risk_score"] == 0.5
    assert len(report["issues"]) == 1
    assert report["issues"][0]["check"] == "non_manifold"
    assert report["issues"][0]["severity"] == "error"
    assert report["metrics"]["Cube"]["volume_mm3"] == 8000.0
    assert report["checks_executed"] == ["non_manifold", "volume"]


def test_modeling_policy_skips_approval_for_read_only_tools() -> None:
    from app.core.contracts import (
        ModelingExecutionMode,
        ModelingPlan,
        ModelingPlanStep,
        ModelingRiskLevel,
        ModelingSoftware,
    )
    from app.modeling.policy import apply_modeling_policy

    plan = ModelingPlan(
        prompt="auditoria",
        software_choice=ModelingSoftware.blender,
        mode=ModelingExecutionMode.approval_required,
        steps=[
            ModelingPlanStep(
                seq=1,
                title="Validar printability",
                software=ModelingSoftware.blender,
                tool_name="blender.validate_printability",
                risk_level=ModelingRiskLevel.medium,
                approval_required=True,
            ),
            ModelingPlanStep(
                seq=2,
                title="Boolean union",
                software=ModelingSoftware.blender,
                tool_name="blender.apply_boolean",
                risk_level=ModelingRiskLevel.low,
                approval_required=False,
            ),
        ],
    )

    enforced = apply_modeling_policy(plan)
    by_tool = {step.tool_name: step for step in enforced.steps}
    assert by_tool["blender.validate_printability"].approval_required is False
    # apply_boolean é HIGH_RISK e deve forçar approval mesmo com risk_level low.
    assert by_tool["blender.apply_boolean"].approval_required is True


def test_modeling_policy_classifies_tier2_tools_correctly() -> None:
    from app.core.contracts import (
        ModelingExecutionMode,
        ModelingPlan,
        ModelingPlanStep,
        ModelingRiskLevel,
        ModelingSoftware,
    )
    from app.modeling.policy import apply_modeling_policy

    plan = ModelingPlan(
        prompt="tier 2",
        software_choice=ModelingSoftware.blender,
        mode=ModelingExecutionMode.approval_required,
        steps=[
            ModelingPlanStep(
                seq=1,
                title="medir",
                software=ModelingSoftware.blender,
                tool_name="blender.measure_object",
                risk_level=ModelingRiskLevel.medium,
                approval_required=True,
            ),
            ModelingPlanStep(
                seq=2,
                title="reparar",
                software=ModelingSoftware.blender,
                tool_name="blender.repair_non_manifold",
                risk_level=ModelingRiskLevel.low,
                approval_required=False,
            ),
            ModelingPlanStep(
                seq=3,
                title="subdivision",
                software=ModelingSoftware.blender,
                tool_name="blender.apply_subdivision",
                risk_level=ModelingRiskLevel.low,
                approval_required=False,
            ),
        ],
    )
    enforced = apply_modeling_policy(plan)
    by_tool = {step.tool_name: step for step in enforced.steps}
    # measure_object é read-only → auto-execução
    assert by_tool["blender.measure_object"].approval_required is False
    # repair_non_manifold é HIGH_RISK → approval mesmo com risk_level low
    assert by_tool["blender.repair_non_manifold"].approval_required is True
    # apply_subdivision: alteração normal allowlistada → autoexecução no fluxo fluido
    assert by_tool["blender.apply_subdivision"].approval_required is False


def test_modeling_policy_autoexecutes_normal_changes_but_blocks_high_risk() -> None:
    from app.core.contracts import (
        ModelingExecutionMode,
        ModelingPlan,
        ModelingPlanStep,
        ModelingRiskLevel,
        ModelingSoftware,
    )
    from app.modeling.policy import apply_modeling_policy

    plan = ModelingPlan(
        prompt="fluxo fluido",
        software_choice=ModelingSoftware.blender,
        mode=ModelingExecutionMode.safe_auto,
        steps=[
            ModelingPlanStep(
                seq=1,
                title="Adicionar cubo",
                software=ModelingSoftware.blender,
                tool_name="blender.create_mesh_primitive",
                risk_level=ModelingRiskLevel.medium,
                approval_required=True,
            ),
            ModelingPlanStep(
                seq=2,
                title="Boolean destructive",
                software=ModelingSoftware.blender,
                tool_name="blender.apply_boolean",
                risk_level=ModelingRiskLevel.medium,
                approval_required=False,
            ),
        ],
    )

    enforced = apply_modeling_policy(plan)
    by_tool = {step.tool_name: step for step in enforced.steps}
    assert by_tool["blender.create_mesh_primitive"].approval_required is False
    assert by_tool["blender.apply_boolean"].approval_required is True
    assert enforced.approval_required is True
    assert enforced.status == "waiting_approval"
