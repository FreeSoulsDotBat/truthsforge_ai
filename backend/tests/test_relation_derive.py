"""Testes F8 (Sub 4) — derivação de relação → primitiva F7 (``relation_derive``).

Mede o ModelState e produz place_body/align_axis/distribute_along com descritores
role/predicado. NUNCA chuta: corpo/kind/geometria ausente → erro tipado.
"""

from __future__ import annotations

import pytest

from app.core.contracts import (
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
    RelationSpec,
)
from app.modeling.relation_derive import RelationUnderivableError, derive_relation


def _face(token, *, type="planar", normal=None, area=None, radius=None, center=None, open_b=None):
    return ModelStateFace(
        token=token,
        type=type,
        normal_axis=normal,
        area_mm2=area,
        radius_mm=radius,
        center_mm=center,
        is_open_boundary=open_b,
    )


def _body(name, *, faces=(), edges=()):
    return ModelStateBody(name=name, stable_id=name + "_id", faces=list(faces), edges=list(edges))


def _straight_edge(token, length):
    return ModelStateEdge(
        token=token, length_mm=length, start_point_mm=[0, 0, 0], end_point_mm=[length, 0, 0]
    )


def _state(*bodies):
    return ModelState(bodies=list(bodies))


def test_flush_mate_to_place_body() -> None:
    state = _state(_body("Tampa"), _body("Caixa"))
    d = derive_relation(RelationSpec(kind="flush_mate", moving="Tampa", reference="Caixa"), state)
    assert d.primitive_tool == "fusion.place_body"
    assert d.primitive_args["body"] == "Tampa"
    assert d.primitive_args["anchor"] == {"body": "Tampa", "role": "bottom_planar"}
    assert d.primitive_args["target"] == {"body": "Caixa", "role": "top_planar"}
    assert d.primitive_args["mate"] == "flush"


def test_cover_opening_targets_open_boundary() -> None:
    state = _state(_body("Tampa"), _body("Caixa"))
    spec = RelationSpec(kind="cover_opening", moving="Tampa", reference="Caixa")
    d = derive_relation(spec, state)
    assert d.primitive_args["target"] == {"body": "Caixa", "role": "open_boundary"}


def test_role_override_is_respected() -> None:
    state = _state(_body("Tampa"), _body("Caixa"))
    d = derive_relation(
        RelationSpec(
            kind="flush_mate",
            moving="Tampa",
            reference="Caixa",
            moving_role="largest_planar",
            reference_role="largest_planar",
        ),
        state,
    )
    assert d.primitive_args["anchor"]["role"] == "largest_planar"
    assert d.primitive_args["target"]["role"] == "largest_planar"


def test_coaxial_insert_measures_moving_radius() -> None:
    pino = _body("Pino", faces=[_face("t1", type="cylindrical", radius=2.5)])
    caixa_face = _face("t2", type="cylindrical", radius=2.6)
    caixa = _body("Caixa", faces=[caixa_face])
    spec = RelationSpec(kind="coaxial_insert", moving="Pino", reference="Caixa")
    d = derive_relation(spec, _state(pino, caixa))
    assert d.primitive_tool == "fusion.align_axis"
    # mede o raio do pino p/ mirar o furo de raio compatível (não "o primeiro").
    assert d.primitive_args["target"]["face"]["type"] == "cylindrical"
    assert d.primitive_args["target"]["face"]["radius_mm"] == 2.5
    assert d.measured["moving_radius_mm"] == 2.5


def test_coaxial_without_cylinder_still_derives_generic_target() -> None:
    # moving sem face cilíndrica → predicado sem raio (mira qualquer cilindro).
    d = derive_relation(
        RelationSpec(kind="coaxial_insert", moving="A", reference="B"),
        _state(_body("A"), _body("B")),
    )
    assert d.primitive_args["target"]["face"] == {"type": "cylindrical"}
    assert "moving_radius_mm" not in d.measured


def test_distribute_on_edge_derives_longest_edge() -> None:
    ref = _body("Caixa", edges=[_straight_edge("e_short", 10), _straight_edge("e_long", 40)])
    d = derive_relation(
        RelationSpec(kind="distribute_on_edge", moving="x", reference="Caixa", count=5),
        _state(ref),
    )
    assert d.primitive_tool == "fusion.distribute_along"
    assert d.primitive_args["edge"] == "e_long"  # mede a maior aresta reta
    assert d.primitive_args["count"] == 5


def test_distribute_requires_count() -> None:
    ref = _body("Caixa", edges=[_straight_edge("e", 40)])
    with pytest.raises(RelationUnderivableError):
        derive_relation(
            RelationSpec(kind="distribute_on_edge", moving="x", reference="Caixa"), _state(ref)
        )


def test_distribute_without_straight_edge_errors() -> None:
    circ = ModelStateEdge(token="e", length_mm=5, is_circular=True, radius_mm=2)
    ref = _body("Caixa", edges=[circ])
    with pytest.raises(RelationUnderivableError):
        derive_relation(
            RelationSpec(kind="distribute_on_edge", moving="x", reference="Caixa", count=3),
            _state(ref),
        )


def test_missing_body_is_typed_error() -> None:
    with pytest.raises(RelationUnderivableError):
        derive_relation(
            RelationSpec(kind="flush_mate", moving="Tampa", reference="Inexistente"),
            _state(_body("Tampa")),
        )
