"""Testes F7 (P3) — resolver puro de referência espacial (``spatial_ref``).

Camada de domínio pura: dado um ``ModelState`` (sem Fusion), resolve referências
declarativas — objeto e @-string — em ponto/eixo/escalar. Cobre a gramática, a
aritmética restrita, o passthrough de cardinais/números e os erros tipados
(``fusion.spatial_ref_unresolved``: NUNCA chuta).
"""

from __future__ import annotations

import pytest

from app.core.contracts import (
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.spatial_ref import (
    SPATIAL_REF_UNRESOLVED,
    SpatialRefError,
    is_spatial_ref,
    parse_at_expr,
    resolve_axis,
    resolve_point,
    resolve_scalar,
)


def _state() -> ModelState:
    """Placa 60x40x10 na origem, com face de topo (+z), face cilíndrica, aresta
    reta de topo (eixo x) e aresta circular (furo)."""
    return ModelState(
        bodies=[
            ModelStateBody(
                stable_id="ID_PLACA",
                name="Placa",
                dimensions_mm=[60, 40, 10],
                bbox_min_mm=[0, 0, 0],
                bbox_max_mm=[60, 40, 10],
                faces=[
                    ModelStateFace(
                        token="F_TOP",
                        type="planar",
                        normal_axis="+z",
                        center_mm=[30, 20, 10],
                        area_mm2=2400,
                    ),
                    ModelStateFace(
                        token="F_CYL",
                        type="cylindrical",
                        radius_mm=5,
                        center_mm=[30, 20, 5],
                    ),
                ],
                edges=[
                    ModelStateEdge(
                        token="E_TOPX",
                        length_mm=60,
                        is_circular=False,
                        start_point_mm=[0, 40, 10],
                        end_point_mm=[60, 40, 10],
                        direction=[1, 0, 0],
                    ),
                    ModelStateEdge(
                        token="E_HOLE",
                        length_mm=31.4,
                        is_circular=True,
                        radius_mm=5,
                    ),
                ],
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# is_spatial_ref / parse_at_expr                                              #
# --------------------------------------------------------------------------- #
def test_is_spatial_ref_distinguishes_refs_from_raw_values() -> None:
    assert is_spatial_ref("@token('F').center") is True
    assert is_spatial_ref({"face": "F", "point": "center"}) is True
    assert is_spatial_ref({"edge": "E"}) is True
    # Cardinais e números crus NÃO são refs (passam direto).
    assert is_spatial_ref("+z") is False
    assert is_spatial_ref([1, 0, 0]) is False
    assert is_spatial_ref(12.5) is False
    assert is_spatial_ref({"x": 1}) is False


def test_parse_at_expr_splits_kind_id_and_chain() -> None:
    assert parse_at_expr("@edge('E_TOPX').along(0.2)") == ("edge", "E_TOPX", [("along", 0.2)])
    assert parse_at_expr("@body('Placa').bbox.max_z") == ("body", "Placa", ["bbox", "max_z"])
    assert parse_at_expr("@token('F_TOP').center.z") == ("token", "F_TOP", ["center", "z"])


def test_parse_at_expr_rejects_malformed() -> None:
    with pytest.raises(SpatialRefError):
        parse_at_expr("@token(F_TOP)")  # sem aspas
    with pytest.raises(SpatialRefError):
        parse_at_expr("token('F')")  # sem @
    with pytest.raises(SpatialRefError):
        parse_at_expr("@stuff('x').center")  # kind desconhecido


# --------------------------------------------------------------------------- #
# resolve_point                                                               #
# --------------------------------------------------------------------------- #
def test_resolve_point_face_center_both_forms() -> None:
    st = _state()
    assert resolve_point("@token('F_TOP').center", st) == (30, 20, 10)
    assert resolve_point({"face": "F_TOP", "point": "center"}, st) == (30, 20, 10)


def test_resolve_point_edge_along_midpoint_and_ends() -> None:
    st = _state()
    assert resolve_point("@edge('E_TOPX').along(0.5)", st) == (30, 40, 10)
    assert resolve_point({"edge": "E_TOPX", "point": "along", "fraction": 0.25}, st) == (15, 40, 10)
    assert resolve_point({"edge": "E_TOPX", "point": "midpoint"}, st) == (30, 40, 10)
    assert resolve_point({"edge": "E_TOPX", "point": "start"}, st) == (0, 40, 10)
    assert resolve_point({"edge": "E_TOPX", "point": "end"}, st) == (60, 40, 10)


def test_resolve_point_body_center_corner_and_by_stable_id() -> None:
    st = _state()
    assert resolve_point({"body": "Placa", "point": "center"}, st) == (30, 20, 5)
    assert resolve_point({"body": "Placa", "point": "corner"}, st) == (0, 0, 0)
    # Aceita stable_id além do nome.
    assert resolve_point({"body": "ID_PLACA", "point": "center"}, st) == (30, 20, 5)


def test_resolve_point_passthrough_raw_vector() -> None:
    assert resolve_point([3, 4, 5], _state()) == (3, 4, 5)


def test_resolve_point_rejects_scalar_and_axis() -> None:
    st = _state()
    with pytest.raises(SpatialRefError):  # .z é escalar
        resolve_point("@token('F_TOP').center.z", st)
    with pytest.raises(SpatialRefError):  # normal é eixo
        resolve_point("@token('F_TOP').normal", st)


# --------------------------------------------------------------------------- #
# resolve_axis                                                                #
# --------------------------------------------------------------------------- #
def test_resolve_axis_face_normal_and_edge_direction() -> None:
    st = _state()
    assert resolve_axis("@token('F_TOP').normal", st) == (0, 0, 1)
    assert resolve_axis({"face": "F_TOP"}, st) == (0, 0, 1)  # default normal
    assert resolve_axis("@edge('E_TOPX').direction", st) == (1, 0, 0)
    assert resolve_axis({"edge": "E_TOPX"}, st) == (1, 0, 0)  # default direction


def test_resolve_axis_cardinal_and_raw_vector_normalized() -> None:
    st = _state()
    assert resolve_axis("+y", st) == (0, 1, 0)
    assert resolve_axis("-z", st) == (0, 0, -1)
    assert resolve_axis([0, 0, 2], st) == (0, 0, 1)  # normaliza
    assert resolve_axis({"face": "F_TOP", "axis": "+x"}, st) == (1, 0, 0)  # override cardinal


def test_resolve_axis_nonplanar_face_has_no_cardinal_normal() -> None:
    with pytest.raises(SpatialRefError):
        resolve_axis("@token('F_CYL').normal", _state())


# --------------------------------------------------------------------------- #
# resolve_scalar                                                              #
# --------------------------------------------------------------------------- #
def test_resolve_scalar_number_passthrough() -> None:
    assert resolve_scalar(12.5, _state()) == 12.5
    assert resolve_scalar(7, _state()) == 7.0


def test_resolve_scalar_component_and_bbox() -> None:
    st = _state()
    assert resolve_scalar("@token('F_TOP').center.z", st) == 10
    assert resolve_scalar("@body('Placa').bbox.max_z", st) == 10
    assert resolve_scalar("@body('Placa').max_x", st) == 60  # atalho sem bbox.
    assert resolve_scalar({"body": "Placa", "point": "bbox.max_z"}, st) == 10


def test_resolve_scalar_arithmetic_restricted_ast() -> None:
    st = _state()
    assert resolve_scalar("@body('Placa').bbox.max_z - 20", st) == -10
    # Largura = max_x - min_x.
    assert resolve_scalar("@body('Placa').bbox.max_x - @body('Placa').bbox.min_x", st) == 60
    # Sem @-ref: aritmética numérica pura.
    assert resolve_scalar("5 + 3 * 2", st) == 11


def test_resolve_scalar_rejects_vector_without_component() -> None:
    with pytest.raises(SpatialRefError):
        resolve_scalar("@token('F_TOP').center", _state())  # vetor, não escalar


def test_resolve_scalar_zero_division_is_typed() -> None:
    # Divisão/módulo por zero → SpatialRefError tipado (não ZeroDivisionError cru
    # escapando do executor).
    st = _state()
    for expr in ("10 / 0", "10 % 0", "@body('Placa').bbox.max_x / (3 - 3)"):
        with pytest.raises(SpatialRefError):
            resolve_scalar(expr, st)


def test_resolve_axis_rejects_body_or_point_ref() -> None:
    # Corpo/ponto NÃO define direção — erro tipado em vez de normalizar a posição.
    st = _state()
    with pytest.raises(SpatialRefError):
        resolve_axis({"body": "Placa"}, st)
    with pytest.raises(SpatialRefError):
        resolve_axis("@token('F_TOP').center", st)


def test_resolve_scalar_blocks_code_injection() -> None:
    st = _state()
    # Sem eval: nomes/chamadas/atributos arbitrários são rejeitados.
    for evil in ("__import__('os').system('x')", "(10).__class__", "2 ** 64", "foo + 1"):
        with pytest.raises(SpatialRefError):
            resolve_scalar(evil, st)


# --------------------------------------------------------------------------- #
# Erros tipados (NUNCA chuta)                                                 #
# --------------------------------------------------------------------------- #
def test_missing_token_raises_typed_error() -> None:
    st = _state()
    with pytest.raises(SpatialRefError) as ei:
        resolve_point("@token('NAO_EXISTE').center", st)
    assert ei.value.code == SPATIAL_REF_UNRESOLVED

    with pytest.raises(SpatialRefError):
        resolve_point({"body": "Fantasma", "point": "center"}, st)


def test_missing_bbox_raises_instead_of_guessing() -> None:
    # Corpo sem bbox (adapter antigo / corpo não capturado) → erro, não chute.
    state = ModelState(bodies=[ModelStateBody(name="X", faces=[], edges=[])])
    with pytest.raises(SpatialRefError):
        resolve_point({"body": "X", "point": "center"}, state)


def test_empty_state_raises() -> None:
    with pytest.raises(SpatialRefError):
        resolve_point("@body('Qualquer').center", None)
    with pytest.raises(SpatialRefError):
        resolve_point("@token('F').center", ModelState())
