"""F5 — edição robusta: reconciliação por geometria ao vivo (sobre F1).

Cobre o incremento da Frente F5 no ``ModelingChatOrchestrator`` sem Fusion:
* ``_build_live_state_block`` anexa o ModelState AO VIVO (tokens/raios reais)
  à reconciliação da timeline, e passa intacto quando não há geometria;
* ``_read_live_geometry`` roda o probe ``query_geometry`` best-effort (None em
  falha / software não-fusion), espelhando ``_read_live_timeline``.

O instanciamento via ``__new__`` evita montar todas as dependências do
orchestrator — os métodos sob teste só usam ``self.executor`` (injetado).
"""

from __future__ import annotations

import json
from typing import Any

from app.core.contracts import (
    ModelingPlan,
    ModelingSoftware,
)
from app.modeling.chat_orchestrator import ModelingChatOrchestrator


def _query_inner() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "1 corpo(s).",
        "bodies": [
            {
                "name": "Pino",
                "stable_id": "abc123def456",
                "dimensions_mm": [10, 10, 20],
                "is_solid": True,
                "faces": [
                    {
                        "face_index": 0,
                        "face_token": "TOK_FACE_CYL",
                        "type": "cylindrical",
                        "area_mm2": 628.3,
                        "radius_mm": 5.0,
                    }
                ],
                "edges": [
                    {
                        "edge_index": 0,
                        "edge_token": "TOK_EDGE_CIRC",
                        "length_mm": 31.4,
                        "is_circular": True,
                        "radius_mm": 5.0,
                    }
                ],
            }
        ],
    }


def _http_envelope(inner: dict[str, Any]) -> dict[str, Any]:
    blob = json.dumps(inner)
    return {
        "ok": True,
        "result": {"message": blob, "success": True},
        "message": blob,
        "software": "fusion",
    }


class _Outcome:
    def __init__(self, ok: bool, output: Any) -> None:
        self.ok = ok
        self.output = output


class _FakeExecutor:
    def __init__(self, outcome: _Outcome | None = None, raise_exc: bool = False) -> None:
        self._outcome = outcome
        self._raise = raise_exc
        self.calls: list[str] = []

    def _execute_single_step(self, step: Any, *, plan: Any) -> _Outcome:
        self.calls.append(step.tool_name)
        if self._raise:
            raise RuntimeError("fusion offline")
        return self._outcome  # type: ignore[return-value]


def _orchestrator(executor: _FakeExecutor) -> ModelingChatOrchestrator:
    orch = ModelingChatOrchestrator.__new__(ModelingChatOrchestrator)
    orch.executor = executor  # type: ignore[attr-defined]
    return orch


def _context_plan() -> ModelingPlan:
    return ModelingPlan(
        prompt="<leitura de estado>",
        software_choice=ModelingSoftware.fusion,
    )


# ---------------------------------------------------------------------------
# _build_live_state_block
# ---------------------------------------------------------------------------


def test_live_state_block_appends_model_state() -> None:
    orch = _orchestrator(_FakeExecutor())
    recon = "<estado-atual-fusion>\nTimeline: 3 feature(s).\n</estado-atual-fusion>"
    combined = orch._build_live_state_block(recon, _http_envelope(_query_inner()))

    assert combined is not None
    assert "<estado-atual-fusion>" in combined  # reconciliação preservada
    assert "<model-state" in combined  # ModelState ao vivo anexado
    assert "TOK_FACE_CYL" in combined and "raio=5mm" in combined  # tokens/raios reais


def test_live_state_block_passthrough_without_geometry() -> None:
    orch = _orchestrator(_FakeExecutor())
    recon = "<estado-atual-fusion>\n</estado-atual-fusion>"
    assert orch._build_live_state_block(recon, None) == recon


def test_live_state_block_passthrough_when_unparseable() -> None:
    orch = _orchestrator(_FakeExecutor())
    recon = "RECON"
    # geometria sem bodies => ModelState None => reconciliação intacta.
    assert orch._build_live_state_block(recon, {"ok": True, "bodies": []}) == recon


def test_live_state_block_uses_geometry_when_no_reconciliation() -> None:
    orch = _orchestrator(_FakeExecutor())
    combined = orch._build_live_state_block(None, _http_envelope(_query_inner()))
    assert combined is not None and "<model-state" in combined


# ---------------------------------------------------------------------------
# _read_live_geometry
# ---------------------------------------------------------------------------


def test_read_live_geometry_runs_query_geometry_probe() -> None:
    output = _http_envelope(_query_inner())
    executor = _FakeExecutor(_Outcome(ok=True, output=output))
    orch = _orchestrator(executor)

    result = orch._read_live_geometry(
        software=ModelingSoftware.fusion, context_plan=_context_plan()
    )

    assert result == output
    assert executor.calls == ["fusion.query_geometry"]


def test_read_live_geometry_returns_none_on_failure() -> None:
    executor = _FakeExecutor(_Outcome(ok=False, output=None))
    orch = _orchestrator(executor)
    assert (
        orch._read_live_geometry(software=ModelingSoftware.fusion, context_plan=_context_plan())
        is None
    )


def test_read_live_geometry_swallows_executor_exception() -> None:
    executor = _FakeExecutor(raise_exc=True)
    orch = _orchestrator(executor)
    assert (
        orch._read_live_geometry(software=ModelingSoftware.fusion, context_plan=_context_plan())
        is None
    )


def test_read_live_geometry_skips_non_fusion() -> None:
    executor = _FakeExecutor(_Outcome(ok=True, output={}))
    orch = _orchestrator(executor)
    assert (
        orch._read_live_geometry(software=ModelingSoftware.blender, context_plan=_context_plan())
        is None
    )
    assert executor.calls == []  # nem chega a rodar o probe
