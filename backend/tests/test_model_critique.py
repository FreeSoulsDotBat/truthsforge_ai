"""Testes F8 (Sub 3) — auto-crítica estruturada (``model_critique``), puro/mock.

Checagens determinísticas (contagem de corpos, órfão/duplicado, interferência
por bbox, op-sem-efeito) → ModelVerdict (faltou/demais/errado/certo). Só reporta.
"""

from __future__ import annotations

from app.core.contracts import (
    ChangeRecord,
    IntentSpec,
    ModelState,
    ModelStateBody,
    OperationHistory,
)
from app.modeling.model_critique import build_model_verdict, render_verdict_block


def _body(name, sid=None, *, bmin=None, bmax=None):
    return ModelStateBody(name=name, stable_id=sid, bbox_min_mm=bmin, bbox_max_mm=bmax)


def _state(*bodies):
    return ModelState(bodies=list(bodies))


def _kinds(verdict):
    return {(f.check_id, f.kind) for f in verdict.findings}


def test_duplicate_body_is_diverged_excess() -> None:
    # O bug de hoje: esperava 2 (caixa+tampa), saíram 3 (Caixa_fixed órfão).
    intent = IntentSpec(
        expected_body_count=2, expected_bodies=[{"name": "Caixa"}, {"name": "Tampa"}]
    )
    state = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"), _body("Caixa_fixed", "ID3"))
    v = build_model_verdict(intent, None, state)
    assert v.overall == "diverged"
    assert ("body_count", "excess") in _kinds(v)
    assert ("orphan_body", "excess") in _kinds(v)
    assert any("Caixa_fixed" in f.detail for f in v.findings)


def test_missing_body_is_incomplete() -> None:
    intent = IntentSpec(expected_body_count=2)
    v = build_model_verdict(intent, None, _state(_body("Caixa", "ID1")))
    assert v.overall == "incomplete" and ("body_count", "missing") in _kinds(v)


def test_correct_body_count_is_ok() -> None:
    intent = IntentSpec(
        expected_body_count=2, expected_bodies=[{"name": "Caixa"}, {"name": "Tampa"}]
    )
    v = build_model_verdict(intent, None, _state(_body("Caixa"), _body("Tampa")))
    assert v.overall == "ok" and ("body_count", "correct") in _kinds(v)


def test_interference_between_disjoint_bodies_is_wrong() -> None:
    # Dois corpos que deviam ser disjuntos se sobrepõem (tampa atravessa a caixa).
    intent = IntentSpec(disjoint_groups=[["Caixa", "Tampa"]])
    caixa = _body("Caixa", bmin=[0, 0, 0], bmax=[60, 40, 20])
    tampa = _body("Tampa", bmin=[0, 0, 10], bmax=[60, 40, 13])  # cruza a caixa (z 10–13)
    v = build_model_verdict(intent, None, _state(caixa, tampa))
    assert v.overall == "diverged" and ("interference", "wrong") in _kinds(v)


def test_no_interference_when_separated() -> None:
    intent = IntentSpec(disjoint_groups=[["Caixa", "Tampa"]])
    caixa = _body("Caixa", bmin=[0, 0, 0], bmax=[60, 40, 20])
    tampa = _body("Tampa", bmin=[0, 0, 20], bmax=[60, 40, 23])  # encostada (contato, não cruza)
    v = build_model_verdict(intent, None, _state(caixa, tampa))
    assert all(f.check_id != "interference" for f in v.findings)


def test_op_with_no_effect_is_missing() -> None:
    # passo mutativo sem efeito mensurável (ex.: um cut que não cortou nada).
    rec = ChangeRecord(
        tool_name="fusion.hole",
        tool_category="mutative",
        seq=3,
        captured_before=True,
        captured_after=True,
    )
    v = build_model_verdict(IntentSpec(), OperationHistory(records=[rec]), _state(_body("Caixa")))
    assert ("op_no_effect", "missing") in _kinds(v)


def test_deterministic_complete_unless_semantic_acceptance() -> None:
    state = _state(_body("Caixa"), _body("Tampa"))
    assert build_model_verdict(
        IntentSpec(expected_body_count=2), None, state
    ).deterministic_complete
    # com acceptance_text, o julgamento semântico (LLM) ainda é necessário.
    intent = IntentSpec(expected_body_count=2, acceptance_text="tampa abre como dobradiça")
    assert build_model_verdict(intent, None, state).deterministic_complete is False


def test_render_verdict_block_lists_findings() -> None:
    intent = IntentSpec(
        expected_body_count=2, expected_bodies=[{"name": "Caixa"}, {"name": "Tampa"}]
    )
    state = _state(_body("Caixa", "ID1"), _body("Tampa", "ID2"), _body("Caixa_fixed", "ID3"))
    block = render_verdict_block(build_model_verdict(intent, None, state))
    assert "<auto-critica overall=diverged>" in block
    assert "DEMAIS" in block and "Caixa_fixed" in block
    assert "AÇÃO:" in block  # instrução de não-duplicar quando há divergência


def test_render_verdict_block_empty_when_no_findings() -> None:
    assert render_verdict_block(None) == ""
    assert render_verdict_block(build_model_verdict(IntentSpec(), None, _state())) == ""
