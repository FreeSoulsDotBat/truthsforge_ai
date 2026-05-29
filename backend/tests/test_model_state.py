"""Testes F1 — estado rico do modelo (parser + render + contrato).

Cobre `app.modeling.model_state` (camada pura, sem Fusion) e o campo novo
`ModelingPlan.model_state`. A captura real (`capture_model_state`) e os tokens
no script gerado são cobertos em `test_agent_loop.py`/`test_modeling_observability.py`.
"""

from __future__ import annotations

import json

from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingSoftware,
    ModelState,
)
from app.modeling.model_state import (
    model_state_from_query_output,
    render_model_state_block,
)


def _query_inner(**overrides):
    """Payload típico de fusion.query_geometry (com tokens F1)."""
    body = {
        "name": "Pino",
        "stable_id": "abc123def456",
        "dimensions_mm": [10, 10, 20],
        "is_solid": True,
        "is_closed": True,
        "surface_area_mm2": 706.8,
        "face_count": 3,
        "edge_count": 3,
        "faces": [
            {
                "face_index": 0,
                "face_token": "TOK_FACE_CYL",
                "type": "cylindrical",
                "area_mm2": 628.3,
                "radius_mm": 5.0,
                "normal_axis": None,
                "center_mm": [0, 0, 10],
            },
            {
                "face_index": 1,
                "face_token": "TOK_FACE_TOP",
                "type": "planar",
                "area_mm2": 78.5,
                "radius_mm": None,
                "normal_axis": "+z",
                "center_mm": [0, 0, 20],
            },
        ],
        "edges": [
            {
                "edge_index": 0,
                "edge_token": "TOK_EDGE_CIRC",
                "length_mm": 31.4,
                "is_circular": True,
                "radius_mm": 5.0,
                "adjacent_face_tokens": ["TOK_FACE_CYL", "TOK_FACE_TOP"],
            }
        ],
    }
    body.update(overrides)
    return {"bodies": [body], "message": "1 corpo(s) inspecionado(s).", "ok": True}


def _http_envelope(inner: dict) -> dict:
    """Replica o envelope HTTP real do adapter fusion (message = JSON string)."""
    blob = json.dumps(inner)
    return {
        "ok": True,
        "input": {},
        "result": {"message": blob, "success": True},
        "message": blob,
        "software": "fusion",
    }


def test_parser_unwraps_http_envelope_with_tokens() -> None:
    state = model_state_from_query_output(_http_envelope(_query_inner()))
    assert state is not None and len(state.bodies) == 1
    body = state.bodies[0]
    assert body.name == "Pino" and body.stable_id == "abc123def456"
    assert body.is_solid is True and body.dimensions_mm == [10, 10, 20]
    # Tokens estáveis preservados.
    assert body.faces[0].token == "TOK_FACE_CYL" and body.faces[0].radius_mm == 5.0
    assert body.edges[0].token == "TOK_EDGE_CIRC" and body.edges[0].is_circular is True
    assert body.edges[0].adjacent_face_tokens == ["TOK_FACE_CYL", "TOK_FACE_TOP"]


def test_parser_accepts_direct_payload_without_envelope() -> None:
    # Mock/in-process devolve o dict direto (sem envelope HTTP).
    state = model_state_from_query_output(_query_inner())
    assert state is not None and state.bodies[0].faces[0].token == "TOK_FACE_CYL"


def test_parser_tolerates_missing_fields() -> None:
    minimal = {"bodies": [{"name": "X"}]}
    state = model_state_from_query_output(minimal)
    assert state is not None and state.bodies[0].name == "X"
    assert state.bodies[0].faces == [] and state.bodies[0].edges == []


def test_parser_returns_none_without_bodies() -> None:
    assert model_state_from_query_output({"message": "vazio"}) is None
    assert model_state_from_query_output(None) is None
    assert model_state_from_query_output({"bodies": []}) is None


def test_render_block_highlights_tokens_radius_and_circular_edges() -> None:
    state = model_state_from_query_output(_query_inner())
    block = render_model_state_block(state)
    assert "<model-state" in block and "</model-state>" in block
    assert "corpo 'Pino'" in block and "abc123def456" in block
    # Face cilíndrica com raio e token; aresta circular com raio e token.
    assert "TOK_FACE_CYL" in block and "raio=5mm" in block
    assert "TOK_EDGE_CIRC" in block and "circular" in block


def test_render_block_empty_for_none_or_no_bodies() -> None:
    assert render_model_state_block(None) == ""
    assert render_model_state_block(ModelState()) == ""


def test_model_state_round_trips_on_modeling_plan() -> None:
    # model_state é JSONB no plano (migration-free): round-trip preserva.
    state = model_state_from_query_output(_query_inner())
    plan = ModelingPlan(
        prompt="peça",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.approved,
        model_state=state,
    )
    dumped = plan.model_dump(mode="json")
    restored = ModelingPlan.model_validate(dumped)
    assert restored.model_state is not None
    assert restored.model_state.bodies[0].faces[0].token == "TOK_FACE_CYL"
