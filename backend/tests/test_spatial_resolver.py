"""Testes F7 (P4) — resolver de posicionamento (``spatial_resolver``).

Puro dado um ``ModelState``: (1) resolução inline de refs nos campos de
coordenada/eixo de tools comuns (regressão-segura: no-op sem ref); (2) expansão
das tools declarativas F7 (place_body/align_axis/distribute_along) em passos
concretos de montagem nativa (make_component + combine-DENTRO + joint-ENTRE).
"""

from __future__ import annotations

import pytest

from app.core.contracts import (
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.spatial_ref import SpatialRefError
from app.modeling.spatial_resolver import (
    F7_PLACEMENT_TOOLS,
    expand_placement,
    resolve_inline_refs,
    resolve_step,
)


def _state() -> ModelState:
    """Caixa 60x40x20 (face de topo +z, furo cilíndrico, aresta de dobradiça em
    x) + Tampa 60x40x3 (face inferior -z)."""
    return ModelState(
        bodies=[
            ModelStateBody(
                stable_id="ID_CAIXA",
                name="Caixa",
                dimensions_mm=[60, 40, 20],
                bbox_min_mm=[0, 0, 0],
                bbox_max_mm=[60, 40, 20],
                faces=[
                    ModelStateFace(
                        token="CAIXA_TOP", type="planar", normal_axis="+z", center_mm=[30, 20, 20]
                    ),
                    ModelStateFace(
                        token="CAIXA_BORE",
                        type="cylindrical",
                        radius_mm=2.5,
                        center_mm=[30, 40, 18],
                    ),
                ],
                edges=[
                    ModelStateEdge(
                        token="E_HINGE",
                        length_mm=60,
                        is_circular=False,
                        start_point_mm=[0, 40, 20],
                        end_point_mm=[60, 40, 20],
                        direction=[1, 0, 0],
                    ),
                ],
            ),
            ModelStateBody(
                stable_id="ID_TAMPA",
                name="Tampa",
                dimensions_mm=[60, 40, 3],
                bbox_min_mm=[0, 0, 20],
                bbox_max_mm=[60, 40, 23],
                faces=[
                    ModelStateFace(
                        token="TAMPA_BOTTOM",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 20],
                    ),
                ],
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# 1) Resolução inline                                                         #
# --------------------------------------------------------------------------- #
def test_inline_resolves_point_field_single_ref() -> None:
    out, actions = resolve_inline_refs(
        "fusion.add_cylinder",
        {"origin_mm": "@token('CAIXA_TOP').center", "diameter_mm": 5},
        _state(),
    )
    assert out["origin_mm"] == [30, 20, 20]
    assert out["diameter_mm"] == 5
    assert len(actions) == 1 and actions[0].field == "origin_mm"


def test_inline_resolves_mixed_component_list_and_axis() -> None:
    st = _state()
    out, _ = resolve_inline_refs(
        "fusion.add_box",
        {"center_mm": ["@body('Caixa').bbox.max_x - 10", 0, "@body('Caixa').bbox.max_z"]},
        st,
    )
    assert out["center_mm"] == [50, 0, 20]
    out2, _ = resolve_inline_refs("fusion.move_body", {"axis": "@edge('E_HINGE').direction"}, st)
    assert out2["axis"] == [1, 0, 0]
    out3, _ = resolve_inline_refs("fusion.hole", {"offset_mm": "@body('Caixa').bbox.max_z"}, st)
    assert out3["offset_mm"] == 20


def test_inline_is_noop_for_absolute_coordinates() -> None:
    # Plano de coordenada absoluta atual: NADA muda, NENHUMA ação (regressão).
    args = {"center_mm": [10, 20, 30], "diameter_mm": 5, "axis": "+z"}
    out, actions = resolve_inline_refs("fusion.add_cylinder", args, _state())
    assert out == args and actions == []


def test_inline_unresolved_ref_raises_typed() -> None:
    with pytest.raises(SpatialRefError):
        resolve_inline_refs(
            "fusion.add_cylinder", {"origin_mm": "@token('GHOST').center"}, _state()
        )


# --------------------------------------------------------------------------- #
# 2) place_body → make_component + joint                                      #
# --------------------------------------------------------------------------- #
def test_place_body_expands_to_component_and_rigid_joint() -> None:
    steps, actions = expand_placement(
        "fusion.place_body",
        {
            "body": "Tampa",
            "anchor": "@token('TAMPA_BOTTOM')",
            "target": "@token('CAIXA_TOP')",
            "mate": "flush",
            "offset_mm": 0,
        },
        _state(),
    )
    assert [s.tool_name for s in steps] == ["fusion.make_component", "fusion.joint"]
    assert steps[0].input_json["body_ref"] == "Tampa"
    j = steps[1].input_json
    assert j["joint_type"] == "rigid"
    assert j["body_one"] == "Tampa" and j["face_token_one"] == "TAMPA_BOTTOM"
    assert j["face_token_two"] == "CAIXA_TOP" and j["body_two"] == "Caixa"
    assert actions[0].kind == "expand_placement"


def test_place_body_requires_face_refs() -> None:
    with pytest.raises(SpatialRefError):
        expand_placement(
            "fusion.place_body",
            {"body": "Tampa", "anchor": "@token('TAMPA_BOTTOM')", "target": "@edge('E_HINGE')"},
            _state(),
        )


# --------------------------------------------------------------------------- #
# 3) align_axis → revolute joint                                              #
# --------------------------------------------------------------------------- #
def test_align_axis_expands_to_revolute_joint_on_cylindrical_face() -> None:
    steps, _ = expand_placement(
        "fusion.align_axis",
        {"body": "Tampa", "target": "@token('CAIXA_BORE')", "body_axis": "x"},
        _state(),
    )
    assert len(steps) == 1 and steps[0].tool_name == "fusion.joint"
    j = steps[0].input_json
    assert j["joint_type"] == "revolute" and j["axis"] == "x"
    assert j["face_token_two"] == "CAIXA_BORE" and j["body_two"] == "Caixa"
    assert j["face_selector_one"] == "cylindrical"


def test_align_axis_rejects_edge_target() -> None:
    with pytest.raises(SpatialRefError):
        expand_placement(
            "fusion.align_axis", {"body": "Tampa", "target": "@edge('E_HINGE')"}, _state()
        )


# --------------------------------------------------------------------------- #
# 4) distribute_along → N primitivas (+ combine-DENTRO se alternado)          #
# --------------------------------------------------------------------------- #
def test_distribute_along_fit_places_n_cylinders_along_edge() -> None:
    steps, _ = expand_placement(
        "fusion.distribute_along",
        {
            "edge": "E_HINGE",
            "count": 5,
            "fit": True,
            "prototype": {
                "primitive": "cylinder",
                "diameter_mm": 5,
                "height_mm": 8,
                "name": "Knuckle",
            },
        },
        _state(),
    )
    assert len(steps) == 5
    assert all(s.tool_name == "fusion.add_cylinder" for s in steps)
    # Frações 0/0.25/0.5/0.75/1 ao longo da aresta x (0..60), y=40, z=20.
    xs = [s.input_json["origin_mm"][0] for s in steps]
    assert xs == [0, 15, 30, 45, 60]
    assert steps[1].input_json["origin_mm"] == [15, 40, 20]
    # Eixo do nó = direção da aresta; nomes sequenciais.
    assert steps[0].input_json["axis"] == [1, 0, 0]
    assert [s.input_json["name"] for s in steps] == [f"Knuckle_{i}" for i in range(1, 6)]


def test_distribute_along_alternate_combines_within_each_parent() -> None:
    steps, _ = expand_placement(
        "fusion.distribute_along",
        {
            "edge": "E_HINGE",
            "count": 5,
            "fit": True,
            "alternate": ["Caixa", "Tampa"],
            "prototype": {
                "primitive": "cylinder",
                "diameter_mm": 5,
                "height_mm": 8,
                "name": "Knuckle",
            },
        },
        _state(),
    )
    cyls = [s for s in steps if s.tool_name == "fusion.add_cylinder"]
    combines = [s for s in steps if s.tool_name == "fusion.combine_bodies"]
    assert len(cyls) == 5 and len(combines) == 2
    by_parent = {c.input_json["target_ref"]: c.input_json["tool_refs"] for c in combines}
    # Combine-DENTRO: nós alternados fundem com seu corpo-pai (parte imprimível).
    assert by_parent["Caixa"] == ["Knuckle_1", "Knuckle_3", "Knuckle_5"]
    assert by_parent["Tampa"] == ["Knuckle_2", "Knuckle_4"]
    assert all(c.input_json["operation"] == "join" for c in combines)


def test_distribute_along_spacing_centers_the_row() -> None:
    steps, _ = expand_placement(
        "fusion.distribute_along",
        {"edge": "E_HINGE", "count": 3, "spacing_mm": 10, "prototype": {"primitive": "cylinder"}},
        _state(),
    )
    xs = [s.input_json["origin_mm"][0] for s in steps]
    # total = 20mm centrado em 60mm → começa em 20: 20/30/40.
    assert xs == [20, 30, 40]


def test_distribute_along_validates_inputs() -> None:
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.distribute_along", {"count": 3}, _state())  # sem edge
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.distribute_along", {"edge": "E_HINGE", "count": 0}, _state())


# --------------------------------------------------------------------------- #
# resolve_step (entrada única do executor)                                    #
# --------------------------------------------------------------------------- #
def test_resolve_step_routes_f7_to_expansion_and_others_to_inline() -> None:
    st = _state()
    assert F7_PLACEMENT_TOOLS == {
        "fusion.place_body",
        "fusion.align_axis",
        "fusion.distribute_along",
    }
    # Tool comum: 1 passo, refs inline resolvidas.
    steps, _ = resolve_step("fusion.add_cylinder", {"origin_mm": "@token('CAIXA_TOP').center"}, st)
    assert len(steps) == 1 and steps[0].tool_name == "fusion.add_cylinder"
    assert steps[0].input_json["origin_mm"] == [30, 20, 20]
    # Tool F7: expande.
    steps2, _ = resolve_step(
        "fusion.align_axis", {"body": "Tampa", "target": "@token('CAIXA_BORE')"}, st
    )
    assert steps2[0].tool_name == "fusion.joint"
