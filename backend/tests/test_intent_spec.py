"""Testes F8 (Sub 3.2) — derivação do ``IntentSpec`` a partir do plano, puro/mock.

Cobre o invariante "NUNCA chuta": asserção geométrica só em build one-shot
totalmente contabilizável; plano de edição / criadores anônimos / tools de net
desconhecido → só a camada semântica (acceptance), sem falso-positivo.
"""

from __future__ import annotations

from app.core.contracts import (
    ModelingPlan,
    ModelingPlanKind,
    ModelingPlanStep,
    ModelingSoftware,
    ModelingSubGoal,
)
from app.modeling.intent_spec import intent_from_plan


def _step(seq: int, tool: str, **args: object) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=seq,
        title=tool,
        software=ModelingSoftware.fusion,
        tool_name=tool,
        input_json=dict(args),
    )


def _plan(*steps: ModelingPlanStep, kind=ModelingPlanKind.primary, parent=None, sub_goals=None):
    return ModelingPlan(
        prompt="x",
        software_choice=ModelingSoftware.fusion,
        kind=kind,
        parent_plan_id=parent,
        steps=list(steps),
        sub_goals=list(sub_goals or []),
    )


def test_two_named_primitives_disjoint() -> None:
    # caixa + tampa: 2 corpos nomeados, esperados disjuntos, sem combine.
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Caixa", width_mm=60, depth_mm=40, height_mm=20),
            _step(2, "fusion.shell_body", body="Caixa", thickness_mm=2),
            _step(3, "fusion.add_box", name="Tampa", width_mm=60, depth_mm=40, height_mm=3),
        )
    )
    assert intent.expected_body_count == 2
    assert {b["name"] for b in intent.expected_bodies} == {"Caixa", "Tampa"}
    assert intent.disjoint_groups == [["Caixa", "Tampa"]]


def test_declarative_placement_makes_count_unknown_but_keeps_names() -> None:
    # place_body é resolvido em runtime (fuse-DENTRO ou joint) → net desconhecido;
    # mas não cria corpo de nome imprevisível → órfão/disjunto seguem valendo.
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Caixa"),
            _step(2, "fusion.add_box", name="Tampa"),
            _step(3, "fusion.place_body", body="Tampa", mate="flush"),
        )
    )
    assert intent.expected_body_count is None
    assert {b["name"] for b in intent.expected_bodies} == {"Caixa", "Tampa"}
    assert intent.disjoint_groups == [["Caixa", "Tampa"]]


def test_combine_join_consumes_tool_bodies() -> None:
    # add 2 + combine(join) com 1 tool → 1 corpo final (Caixa); Pino consumido.
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Caixa"),
            _step(2, "fusion.add_cylinder", name="Pino"),
            _step(3, "fusion.combine_bodies", target="Caixa", tool_refs=["Pino"], operation="join"),
        )
    )
    assert intent.expected_body_count == 1
    assert {b["name"] for b in intent.expected_bodies} == {"Caixa"}
    # 1 corpo só → sem grupo disjunto.
    assert intent.disjoint_groups == []


def test_combine_result_name_rename() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="A"),
            _step(2, "fusion.add_box", name="B"),
            _step(
                3,
                "fusion.combine_bodies",
                target="A",
                tool_refs=["B"],
                operation="join",
                result_name="Montagem",
            ),
        )
    )
    assert intent.expected_body_count == 1
    assert {b["name"] for b in intent.expected_bodies} == {"Montagem"}


def test_delete_body_decrements() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="A"),
            _step(2, "fusion.add_box", name="B"),
            _step(3, "fusion.delete_body", body_name="B"),
        )
    )
    assert intent.expected_body_count == 1
    assert {b["name"] for b in intent.expected_bodies} == {"A"}


def test_anonymous_profile_creator_drops_names_but_may_keep_count() -> None:
    # extrude new_body sem nome: +1 na contagem, mas nome auto → sem órfão/disjunto.
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.create_sketch", plane="xy"),
            _step(2, "fusion.extrude_profile", operation="new_body", distance_mm=10),
        )
    )
    assert intent.expected_body_count == 1
    assert intent.expected_bodies == []
    assert intent.disjoint_groups == []


def test_uncountable_tool_makes_count_none() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Base"),
            _step(2, "fusion.pattern_rectangular", body="Base", count_x=3),
        )
    )
    assert intent.expected_body_count is None
    assert intent.expected_bodies == []


def test_edit_plan_only_semantic_no_geometric_assert() -> None:
    # bloco de edição não conhece corpos pré-existentes → nenhuma asserção
    # geométrica (evita falso-positivo), só a camada semântica.
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Tampa"),
            kind=ModelingPlanKind.edit,
            parent="m3d_plan_parent",
            sub_goals=[ModelingSubGoal(seq=1, title="tampa", acceptance="tampa encaixa")],
        )
    )
    assert intent.expected_body_count is None
    assert intent.expected_bodies == []
    assert intent.disjoint_groups == []
    assert intent.acceptance_text == "tampa encaixa"


def test_acceptance_from_sub_goals() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Caixa"),
            sub_goals=[
                ModelingSubGoal(seq=1, title="a", acceptance="caixa ocada"),
                ModelingSubGoal(seq=2, title="b", acceptance="tampa encaixa"),
                ModelingSubGoal(seq=3, title="c", acceptance=""),
            ],
        )
    )
    assert intent.acceptance_text == "caixa ocada | tampa encaixa"


def test_at_ref_names_are_cleaned() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="@body('Caixa')"),
            _step(2, "fusion.add_box", name="@('Tampa')"),
        )
    )
    assert {b["name"] for b in intent.expected_bodies} == {"Caixa", "Tampa"}


def test_unknown_tool_is_defensive() -> None:
    intent = intent_from_plan(
        _plan(
            _step(1, "fusion.add_box", name="Caixa"),
            _step(2, "fusion.totally_unknown_tool", foo=1),
        )
    )
    assert intent.expected_body_count is None
    assert intent.expected_bodies == []
