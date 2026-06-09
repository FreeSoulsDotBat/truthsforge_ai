"""Testes F9 Pilar 2 — estado semântico derivado (``semantic_state``).

Camada pura: dado um ``ModelState`` medido, deriva papéis de face (roles),
adjacência entre corpos (touches) e rótulo de corpo (body_label). Best-effort:
ambíguo/sem âncora ⇒ vazio/None (NUNCA rotula errado). Cobre também a injeção no
``<model-state>`` e o gate por flag em ``capture_model_state``.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.contracts import ModelState, ModelStateBody, ModelStateFace
from app.modeling.model_state import _maybe_enrich_semantic, render_model_state_block
from app.modeling.semantic_state import derive_semantic_state


def _container_lid() -> ModelState:
    """Caixa OCA (face de topo marcada is_open_boundary) 60x40x20 + Tampa fina
    60x40x3 encostada no topo (base z=20 = topo da caixa)."""
    return ModelState(
        bodies=[
            ModelStateBody(
                name="Caixa",
                stable_id="C",
                bbox_min_mm=[0, 0, 0],
                bbox_max_mm=[60, 40, 20],
                is_solid=True,
                faces=[
                    ModelStateFace(
                        token="CX_TOP",
                        type="planar",
                        normal_axis="+z",
                        center_mm=[30, 20, 20],
                        area_mm2=2400.0,
                        is_open_boundary=True,
                    ),
                    ModelStateFace(
                        token="CX_BOT",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 0],
                        area_mm2=2400.0,
                    ),
                ],
            ),
            ModelStateBody(
                name="Tampa",
                stable_id="T",
                bbox_min_mm=[0, 0, 20],
                bbox_max_mm=[60, 40, 23],
                is_solid=True,
                faces=[
                    ModelStateFace(
                        token="TP_BOT",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 20],
                        area_mm2=2400.0,
                    ),
                    ModelStateFace(
                        token="TP_TOP",
                        type="planar",
                        normal_axis="+z",
                        center_mm=[30, 20, 23],
                        area_mm2=2400.0,
                    ),
                ],
            ),
        ]
    )


def test_derive_roles_tags_top_bottom_and_open_boundary() -> None:
    state = derive_semantic_state(_container_lid())
    caixa = state.bodies[0]
    by_token = {f.token: f for f in caixa.faces}
    # Topo = maior center_z; também é a abertura marcada.
    assert "top_planar" in by_token["CX_TOP"].roles
    assert "open_boundary" in by_token["CX_TOP"].roles
    assert "bottom_planar" in by_token["CX_BOT"].roles
    # A Tampa (sem is_open_boundary) NÃO ganha open_boundary (sem fallback falso).
    tampa = state.bodies[1]
    assert all("open_boundary" not in f.roles for f in tampa.faces)


def test_derive_touches_detects_flush_contact() -> None:
    state = derive_semantic_state(_container_lid())
    caixa, tampa = state.bodies
    # Caixa encosta na Tampa (folga 0 no eixo z) e vice-versa, sem interferência.
    assert any(t.other == "Tampa" and not t.interference and t.gap_mm == 0.0 for t in caixa.touches)
    assert any(t.other == "Caixa" and t.axis == "z" for t in tampa.touches)


def test_derive_touches_ignores_side_by_side_bodies() -> None:
    # Dois corpos alinhados em z (folga 0) mas LADO A LADO em x (sem área comum)
    # → NÃO são adjacentes (exclui o falso-contato por bbox).
    state = ModelState(
        bodies=[
            ModelStateBody(name="A", bbox_min_mm=[0, 0, 0], bbox_max_mm=[10, 10, 10]),
            ModelStateBody(name="B", bbox_min_mm=[20, 0, 0], bbox_max_mm=[30, 10, 10]),
        ]
    )
    derive_semantic_state(state)
    assert state.bodies[0].touches == [] and state.bodies[1].touches == []


def test_derive_touches_flags_interference() -> None:
    # Corpo B penetra A (overlap de volume real) → interference=True.
    state = ModelState(
        bodies=[
            ModelStateBody(name="A", bbox_min_mm=[0, 0, 0], bbox_max_mm=[10, 10, 10]),
            ModelStateBody(name="B", bbox_min_mm=[0, 0, 5], bbox_max_mm=[10, 10, 15]),
        ]
    )
    derive_semantic_state(state)
    assert any(t.other == "B" and t.interference for t in state.bodies[0].touches)


def test_derive_labels_container_and_lid() -> None:
    state = derive_semantic_state(_container_lid())
    caixa, tampa = state.bodies
    assert caixa.body_label == "container"  # tem abertura medida
    assert tampa.body_label == "lid"  # encosta no container e é a mais fina


def test_derive_labels_none_without_open_boundary() -> None:
    # Sem nenhuma face is_open_boundary → nenhum container → nenhum lid (NUNCA
    # rotula no escuro).
    state = _container_lid()
    for f in state.bodies[0].faces:
        f.is_open_boundary = None
    derive_semantic_state(state)
    assert all(b.body_label is None for b in state.bodies)


def test_derive_labels_no_lid_on_thickness_tie() -> None:
    # Dois corpos igualmente finos encostam no container → empate → nenhum vira
    # "lid" (ambiguidade ⇒ None).
    state = _container_lid()
    state.bodies.append(
        ModelStateBody(
            name="Tampa2",
            stable_id="T2",
            bbox_min_mm=[0, 0, 20],
            bbox_max_mm=[60, 40, 23],  # mesma espessura (3) da Tampa
            faces=[
                ModelStateFace(
                    token="T2_BOT", type="planar", normal_axis="-z", center_mm=[30, 20, 20]
                )
            ],
        )
    )
    derive_semantic_state(state)
    assert state.bodies[1].body_label is None and state.bodies[2].body_label is None


def test_derive_is_noop_for_none_or_empty() -> None:
    assert derive_semantic_state(None) is None
    empty = ModelState(bodies=[])
    assert derive_semantic_state(empty) is empty


def test_capture_enrichment_is_gated_by_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    # Flag OFF (default): _maybe_enrich_semantic devolve o state intacto (regressão).
    monkeypatch.setattr(settings, "modeling_semantic_state_enabled", False, raising=False)
    off = _maybe_enrich_semantic(_container_lid())
    assert all(not f.roles for b in off.bodies for f in b.faces)
    assert all(b.body_label is None for b in off.bodies)
    # Flag ON: enriquece (roles + label).
    monkeypatch.setattr(settings, "modeling_semantic_state_enabled", True, raising=False)
    on = _maybe_enrich_semantic(_container_lid())
    assert on.bodies[0].body_label == "container"
    assert any(f.roles for f in on.bodies[0].faces)


def test_render_block_shows_roles_touches_and_label() -> None:
    state = derive_semantic_state(_container_lid())
    block = render_model_state_block(state)
    assert "papel=container" in block and "papel=lid" in block
    assert "papéis=" in block and "open_boundary" in block
    assert "encosta em 'Tampa'" in block or "encosta em 'Caixa'" in block
