"""F6 — sanitizer determinístico pós-LLM (ex-Fase 9.2).

Cobre a malha determinística entre planner e executor: remoção de
campos-fantasma e valores de referência geométrica (Bug J' do gate da Fase 4),
remap de aliases, e a garantia de que planos VÁLIDOS passam intactos. Também
verifica o wiring no `create_llm_plan` (flag default ON) e a regressão com a
flag desligada.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.contracts import (
    ModelCapability,
    ModelConfig,
    ModelingExecutionMode,
    ModelingPlanCreate,
    ProviderName,
)
from app.modeling.plan_sanitizer import (
    GHOST_KEYS,
    SanitizeAction,
    sanitize_tool_arguments,
)
from app.modeling.planner import create_llm_plan

# ---------------------------------------------------------------------------
# sanitizer puro
# ---------------------------------------------------------------------------


def test_drops_ghost_keys() -> None:
    args = {
        "body": "Placa",
        "diameter_mm": 6,
        "face": "Placa.top_face",
        "target_face": "X",
        "surface": "Y",
    }
    cleaned, actions = sanitize_tool_arguments("fusion.hole", args)
    assert cleaned == {"body": "Placa", "diameter_mm": 6}
    dropped = {a.field for a in actions if a.kind == "drop_ghost_key"}
    assert {"face", "target_face", "surface"} <= dropped


def test_drops_geometry_reference_values() -> None:
    args = {
        "diameter_mm": 6,
        "position_mm": ["Placa.bounding_box.max_x - 20", 10],
    }
    cleaned, actions = sanitize_tool_arguments("fusion.hole", args)
    assert "position_mm" not in cleaned  # valor inválido removido
    assert cleaned["diameter_mm"] == 6
    assert any(a.kind == "drop_geom_ref_value" for a in actions)


def test_detects_geom_ref_in_scalar_and_center() -> None:
    _, a1 = sanitize_tool_arguments("fusion.move_body", {"distance_mm": "Body.center"})
    _, a2 = sanitize_tool_arguments("fusion.move_body", {"to_mm": "Cubo.bounding_box.min_z"})
    assert any(a.kind == "drop_geom_ref_value" for a in a1)
    assert any(a.kind == "drop_geom_ref_value" for a in a2)


def test_at_refs_spared_only_when_resolver_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    # F7: @-ref VÁLIDA só é poupada quando o resolver está ATIVO p/ resolvê-la.
    # Com a flag OFF, ninguém resolve @-refs → o guardrail derruba (senão chegaria
    # crua ao adapter e cairia em (0,0)). A forma CRUA (sem @) cai nas duas configs.
    from app.core.config import settings

    spared = {
        "diameter_mm": 6,
        "origin_mm": ["@body('Placa').bbox.max_z - 20", 0, 0],
    }
    # Flag ON: o resolver resolverá os @-refs depois → sanitizer POUPA.
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", True, raising=False)
    cleaned_on, actions_on = sanitize_tool_arguments("fusion.add_cylinder", spared)
    assert cleaned_on == spared and actions_on == []

    # Flag OFF (default): @-ref em origin_mm é DERRUBADA (regressão do guardrail
    # evitada).
    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", False, raising=False)
    cleaned_off, actions_off = sanitize_tool_arguments("fusion.add_cylinder", spared)
    assert "origin_mm" not in cleaned_off and cleaned_off["diameter_mm"] == 6
    assert any(a.kind == "drop_geom_ref_value" for a in actions_off)

    # Com a flag OFF, as formas @-ref COMUNS (.center/.normal/.direction) — que o
    # regex _GEOM_REF_RE NÃO casa (')' antes do '.center') — também caem, pela
    # PRESENÇA do @-ref, não chegam cruas ao adapter.
    for field, ref in (
        ("origin_mm", "@token('F_TOP').center"),
        ("axis", "@edge('E1').direction"),
        ("center_mm", "@body('Placa').center"),
    ):
        c_off, _ = sanitize_tool_arguments("fusion.add_cylinder", {field: ref, "diameter_mm": 6})
        assert field not in c_off, f"{field}={ref} deveria cair com flag OFF"

    # Forma CRUA (sem @) cai independente da flag.
    raw = {"position_mm": ["Placa.bbox.max_z - 20", 0]}
    cleaned_raw, _ = sanitize_tool_arguments("fusion.add_cylinder", raw)
    assert "position_mm" not in cleaned_raw


def test_remaps_alias_axis_line_to_axis() -> None:
    cleaned, actions = sanitize_tool_arguments(
        "fusion.revolve_profile", {"sketch": "s", "axis_line": "y"}
    )
    assert cleaned["axis"] == "y"
    assert "axis_line" not in cleaned
    assert any(a.kind == "remap_alias" for a in actions)


def test_alias_does_not_clobber_existing_canonical() -> None:
    cleaned, actions = sanitize_tool_arguments(
        "fusion.revolve_profile", {"axis": "z", "axis_line": "y"}
    )
    assert cleaned["axis"] == "z"  # canônico preservado
    assert "axis_line" not in cleaned
    assert any(a.kind == "drop_ghost_key" and a.field == "axis_line" for a in actions)


def test_valid_arguments_pass_intact() -> None:
    args = {
        "diameter_mm": 6,
        "position_mm": [10, 20],
        "depth_mm": "Comprimento/2 - 15",  # expressão paramétrica legítima
        "body": "Placa",
    }
    cleaned, actions = sanitize_tool_arguments("fusion.hole", args)
    assert cleaned == args
    assert actions == []


def test_non_dict_passthrough() -> None:
    cleaned, actions = sanitize_tool_arguments("fusion.hole", None)
    assert cleaned is None
    assert actions == []


def test_ghost_keys_set_is_frozen() -> None:
    assert isinstance(GHOST_KEYS, frozenset)
    assert "face" in GHOST_KEYS and "target_face" in GHOST_KEYS


def test_sanitize_action_is_hashable_record() -> None:
    action = SanitizeAction("drop_ghost_key", "face", "x")
    assert action.kind == "drop_ghost_key"
    assert action.field == "face"


# ---------------------------------------------------------------------------
# wiring no create_llm_plan
# ---------------------------------------------------------------------------


class _FakeGateway:
    def __init__(self, response: Any) -> None:
        self.response = response

    async def generate_structured(
        self,
        *,
        model: ModelConfig,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return self.response


def _model() -> ModelConfig:
    return ModelConfig(
        id="openai/test-plan",
        provider=ProviderName.openai,
        display_name="Test Planner",
        provider_model_id="gpt-test",
        capabilities=[ModelCapability.chat],
        default=True,
    )


def _response_with_ghost() -> dict[str, Any]:
    return {
        "software_choice": "fusion",
        "confidence": 0.8,
        "rationale": "ok",
        "assumptions": [],
        "risks": [],
        "steps": [
            {
                "seq": 1,
                "title": "Furo",
                "tool_name": "fusion.hole",
                "risk_level": "low",
                "approval_required": False,
                "input_json": json.dumps(
                    {
                        "body": "Placa",
                        "diameter_mm": 6,
                        "face": "Placa.top_face",
                        "position_mm": ["Placa.bounding_box.max_x - 20", 10],
                    }
                ),
            }
        ],
    }


def test_create_llm_plan_sanitizes_steps_by_default() -> None:
    payload = ModelingPlanCreate(
        prompt="furo na placa", mode=ModelingExecutionMode.approval_required
    )
    gateway = _FakeGateway(_response_with_ghost())
    plan = create_llm_plan(payload, gateway=gateway, model=_model())

    args = plan.steps[0].input_json
    assert "face" not in args  # ghost removido
    assert "position_mm" not in args  # valor com ref geométrica removido
    assert args["body"] == "Placa"  # válido preservado
    assert args["diameter_mm"] == 6


def test_create_llm_plan_keeps_ghost_when_sanitizer_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modeling import planner as planner_mod

    monkeypatch.setattr(
        planner_mod.settings, "modeling_plan_sanitizer_enabled", False, raising=False
    )
    payload = ModelingPlanCreate(
        prompt="furo na placa", mode=ModelingExecutionMode.approval_required
    )
    gateway = _FakeGateway(_response_with_ghost())
    plan = create_llm_plan(payload, gateway=gateway, model=_model())

    # Sem sanitizer, o campo-fantasma chega cru ao step (comportamento legado).
    assert "face" in plan.steps[0].input_json
