"""Testes F8 (Sub 2) — proveniência de operações (``provenance``), puro/mock.

Diff before→after do ModelState: created/modified/consumed/deleted/uncertain por
handle estável, com delta geométrico; classificação cruzada com a categoria do
tool; histórico agregado + render. Sem Fusion.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.executor import ModelingExecutorService
from app.modeling.provenance import (
    aggregate_history,
    build_change_record,
    diff_model_state,
    render_history_block,
)


def _body(
    name,
    stable_id=None,
    *,
    bbox_min=None,
    bbox_max=None,
    sa=None,
    vol=None,
    fc=None,
    ec=None,
    faces=(),
    edges=(),
):
    return ModelStateBody(
        name=name,
        stable_id=stable_id,
        bbox_min_mm=bbox_min,
        bbox_max_mm=bbox_max,
        surface_area_mm2=sa,
        volume_mm3=vol,
        face_count=fc,
        edge_count=ec,
        faces=[ModelStateFace(token=t) for t in faces],
        edges=[ModelStateEdge(token=t) for t in edges],
    )


def _state(*bodies):
    return ModelState(bodies=list(bodies))


def test_created_body() -> None:
    before = _state(_body("Caixa", "ID1"))
    after = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"))
    rec = build_change_record("fusion.add_box", before, after, category="additive", seq=2)
    assert [c.ref.name for c in rec.created] == ["Tampa"]
    assert rec.modified == [] and rec.deleted == [] and rec.uncertain == []
    assert rec.bodies_before == 1 and rec.bodies_after == 2
    assert rec.captured_before and rec.captured_after


def test_modified_body_with_deltas() -> None:
    before = _state(_body("Caixa", "ID1", sa=100.0, fc=6, ec=12))
    after = _state(_body("Caixa", "ID1", sa=120.0, fc=7, ec=13))
    rec = build_change_record("fusion.fillet_edges", before, after, category="mutative")
    assert len(rec.modified) == 1 and rec.modified[0].ref.handle == "ID1"
    deltas = {d.metric: d.delta for d in rec.modified[0].deltas}
    assert deltas["surface_area_mm2"] == 20.0 and deltas["face_count"] == 1


def test_disappeared_body_classified_by_category() -> None:
    before = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"))
    after = _state(_body("Caixa", "ID1"))
    # destrutivo → deleted; boolean high_risk → consumed; additive → uncertain.
    assert build_change_record("fusion.delete_body", before, after, category="destructive").deleted
    assert build_change_record(
        "fusion.combine_bodies", before, after, category="high_risk"
    ).consumed
    rec_unc = build_change_record("fusion.add_box", before, after, category="additive")
    assert rec_unc.uncertain and not rec_unc.deleted  # additive não deveria sumir corpo


def test_consumed_and_created_faces_within_surviving_body() -> None:
    # Pocket/fillet: o corpo sobrevive, mas faces somem (consumed) e surgem (created).
    before = _state(_body("Caixa", "ID1", faces=("F1", "F2", "F3")))
    after = _state(_body("Caixa", "ID1", faces=("F1", "F2", "F4")))
    changes = diff_model_state(before, after, category="mutative")
    faces = {(c.op, c.ref.handle) for c in changes if c.ref.kind == "face"}
    assert ("consumed", "F3") in faces and ("created", "F4") in faces
    # corpo não mudou de dimensão → não há 'modified' do corpo aqui.
    assert all(c.ref.kind == "face" for c in changes)


def test_first_step_before_none_degrades_to_created() -> None:
    after = _state(_body("Caixa", "ID1"))
    rec = build_change_record("fusion.add_box", None, after, category="additive")
    assert [c.ref.name for c in rec.created] == ["Caixa"]
    assert rec.captured_before is False and rec.captured_after is True


def test_duplicate_body_is_recorded_as_extra_created() -> None:
    # O bug de hoje: correção visual criou um corpo a mais (Caixa_fixed).
    before = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"))
    after = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"), _body("Caixa_fixed", "ID3"))
    rec = build_change_record("fusion.add_box", before, after, category="additive")
    assert [c.ref.name for c in rec.created] == ["Caixa_fixed"]


def test_aggregate_history_tracks_current_bodies_and_renders() -> None:
    r1 = build_change_record(
        "fusion.add_box", None, _state(_body("Caixa", "ID1")), category="additive", seq=1
    )
    r2 = build_change_record(
        "fusion.add_box",
        _state(_body("Caixa", "ID1")),
        _state(_body("Caixa", "ID1"), _body("Tampa", "ID2")),
        category="additive",
        seq=2,
    )
    r3 = build_change_record(
        "fusion.combine_bodies",
        _state(_body("Caixa", "ID1"), _body("Tampa", "ID2")),
        _state(_body("Caixa", "ID1")),
        category="high_risk",
        seq=3,
    )
    hist = aggregate_history([r1, r2, r3])
    # Tampa foi consumida no combine → some das entidades correntes; Caixa fica.
    current = {e.handle for e in hist.current_entities}
    assert current == {"ID1"}
    block = render_history_block(hist)
    assert "<historico-operacoes>" in block and "fusion.combine_bodies" in block
    assert "criou 1 body" in block and "consumiu 1 body" in block


def test_no_change_yields_empty_record() -> None:
    st = _state(_body("Caixa", "ID1", sa=100.0))
    rec = build_change_record("fusion.query_geometry", st, st, category="read_only")
    assert not (rec.created or rec.modified or rec.deleted or rec.consumed or rec.uncertain)
    assert rec.summary == "sem mudança detectada"


# --------------------------------------------------------------------------- #
# Wiring no executor (Sub 2.2) — flag-gated, captura before/after, carry-forward #
# --------------------------------------------------------------------------- #
def _executor() -> ModelingExecutorService:
    return ModelingExecutorService(
        store=object(), mcp_client=object(), snapshots=object(), artifacts=object()
    )


def _plan() -> ModelingPlan:
    return ModelingPlan(
        prompt="x", software_choice=ModelingSoftware.fusion, status=ModelingPlanStatus.approved
    )


def _step(tool: str) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=2,
        title="t",
        software=ModelingSoftware.fusion,
        tool_name=tool,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json={},
    )


def test_attach_provenance_writes_record_and_carries_forward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "modeling_provenance_enabled", True, raising=False)
    after = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"))
    monkeypatch.setattr("app.modeling.model_state.capture_model_state", lambda _e, _p: after)
    ex, plan = _executor(), _plan()
    output: dict = {"ok": True}
    ex._attach_provenance(_step("fusion.add_box"), plan, output, _state(_body("Caixa", "ID1")))
    prov = output["_provenance"]
    assert [c["ref"]["name"] for c in prov["created"]] == ["Tampa"]
    assert prov["tool_category"] == "additive"
    # after vira o carry-forward (before do próximo passo).
    assert ex._provenance_carry[0] == plan.id and ex._provenance_carry[1] is after


def test_provenance_inactive_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "modeling_provenance_enabled", False, raising=False)
    output: dict = {"ok": True}
    _executor()._attach_provenance(_step("fusion.add_box"), _plan(), output, None)
    assert "_provenance" not in output


def test_provenance_inactive_for_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "modeling_provenance_enabled", True, raising=False)
    output: dict = {"ok": True}
    # query_geometry é read-only → não gera proveniência (e evita recursão).
    _executor()._attach_provenance(_step("fusion.query_geometry"), _plan(), output, None)
    assert "_provenance" not in output


def test_before_state_uses_carry_forward_without_reprobe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "modeling_provenance_enabled", True, raising=False)
    ex, plan = _executor(), _plan()
    carried = _state(_body("Caixa", "ID1"))
    ex._provenance_carry = (plan.id, carried)

    def _boom(_e, _p):
        raise AssertionError("não deveria reprobar — usa o carry-forward")

    monkeypatch.setattr("app.modeling.model_state.capture_model_state", _boom)
    assert ex._provenance_before_state(_step("fusion.fillet_edges"), plan) is carried
