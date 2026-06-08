"""Testes F8 (Sub 1) — referência por role/predicado (``entity_ref``), puro/mock.

Resolve descritor de domínio → handle estável (entityToken), medindo o
ModelState; desambiguação determinística (empate → AmbiguousRefError com
alternatives); erro tipado quando não casa. Nunca chuta.
"""

from __future__ import annotations

import pytest

from app.core.contracts import ModelState, ModelStateBody, ModelStateFace
from app.modeling.entity_ref import (
    ENTITY_REF_AMBIGUOUS,
    AmbiguousRefError,
    EntityRefError,
    resolve_entity,
)


def _state() -> ModelState:
    return ModelState(
        bodies=[
            ModelStateBody(
                name="Caixa",
                stable_id="ID1",
                faces=[
                    ModelStateFace(
                        token="F_TOP",
                        type="planar",
                        normal_axis="+z",
                        center_mm=[30, 20, 20],
                        area_mm2=2400,
                    ),
                    ModelStateFace(
                        token="F_BOT",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 0],
                        area_mm2=2350,
                    ),
                    ModelStateFace(
                        token="F_BORE",
                        type="cylindrical",
                        radius_mm=5.0,
                        center_mm=[30, 20, 10],
                        area_mm2=314,
                    ),
                    ModelStateFace(
                        token="F_SIDE",
                        type="planar",
                        normal_axis="+x",
                        center_mm=[60, 20, 10],
                        area_mm2=800,
                    ),
                ],
            )
        ]
    )


def test_resolve_face_by_role() -> None:
    st = _state()
    assert resolve_entity({"body": "Caixa", "role": "top_planar"}, st).handle == "F_TOP"
    assert resolve_entity({"body": "Caixa", "role": "bottom_planar"}, st).handle == "F_BOT"
    assert resolve_entity({"body": "Caixa", "role": "largest"}, st).handle == "F_TOP"


def test_bottom_planar_robust_to_misclassified_normal() -> None:
    # Bug do gate m3d_plan_18a68125: o read-back classifica o FUNDO da tampa como
    # '+z' (normal de superfície, não outward) → bottom_planar não achava candidato
    # e o place_body falhava. Agora resolve pela POSIÇÃO (menor z entre horizontais).
    st = ModelState(
        bodies=[
            ModelStateBody(
                name="Lid",
                stable_id="LID",
                faces=[
                    ModelStateFace(
                        token="L_TOP", type="planar", normal_axis="+z", center_mm=[30, 20, 23]
                    ),
                    ModelStateFace(
                        token="L_BOT", type="planar", normal_axis="+z", center_mm=[30, 20, 20]
                    ),  # BUG real: o fundo vem como +z
                ],
            )
        ]
    )
    assert resolve_entity({"body": "Lid", "role": "bottom_planar"}, st).handle == "L_BOT"
    assert resolve_entity({"body": "Lid", "role": "top_planar"}, st).handle == "L_TOP"


def test_resolve_face_by_predicate() -> None:
    st = _state()
    ref = resolve_entity({"body": "Caixa", "face": {"type": "cylindrical", "radius_mm": 5}}, st)
    assert ref.kind == "face" and ref.handle == "F_BORE" and ref.parent_body == "ID1"
    # predicado planar+largest desambigua por área.
    assert (
        resolve_entity({"body": "Caixa", "face": {"type": "planar", "largest": True}}, st).handle
        == "F_TOP"
    )
    # predicado por normal resolve único.
    assert (
        resolve_entity({"body": "Caixa", "face": {"type": "planar", "normal": "+x"}}, st).handle
        == "F_SIDE"
    )


def test_resolve_body() -> None:
    ref = resolve_entity({"body": "Caixa"}, _state())
    assert ref.kind == "body" and ref.handle == "ID1" and ref.name == "Caixa"


def test_ambiguous_predicate_raises_with_alternatives() -> None:
    # Vários planares sem desempate → erro tipado com alternativas (não chuta).
    with pytest.raises(AmbiguousRefError) as ei:
        resolve_entity({"body": "Caixa", "face": {"type": "planar"}}, _state())
    assert ei.value.code == ENTITY_REF_AMBIGUOUS
    assert set(ei.value.alternatives) <= {"F_TOP", "F_BOT", "F_SIDE"} and ei.value.alternatives


def test_ambiguous_role_when_two_top_faces_tie() -> None:
    st = ModelState(
        bodies=[
            ModelStateBody(
                name="Placa",
                stable_id="ID2",
                faces=[
                    ModelStateFace(
                        token="T1", type="planar", normal_axis="+z", center_mm=[10, 0, 20]
                    ),
                    ModelStateFace(
                        token="T2", type="planar", normal_axis="+z", center_mm=[40, 0, 20]
                    ),
                ],
            )
        ]
    )
    with pytest.raises(AmbiguousRefError):
        resolve_entity({"body": "Placa", "role": "top_planar"}, st)


def test_unresolved_raises_typed() -> None:
    st = _state()
    with pytest.raises(EntityRefError):
        resolve_entity({"body": "Caixa", "face": {"type": "cylindrical", "radius_mm": 99}}, st)
    with pytest.raises(EntityRefError):
        resolve_entity({"body": "Fantasma"}, st)
    with pytest.raises(EntityRefError):
        resolve_entity({"body": "Caixa", "role": "nope"}, st)
    with pytest.raises(EntityRefError):
        resolve_entity("nao-e-objeto", st)
