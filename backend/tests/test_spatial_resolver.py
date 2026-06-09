"""Testes F7 (P4) — resolver de posicionamento (``spatial_resolver``).

Puro dado um ``ModelState``: (1) resolução inline de refs nos campos de
coordenada/eixo de tools comuns (regressão-segura: no-op sem ref); (2) expansão
das tools declarativas F7 (place_body/align_axis/distribute_along) em passos
concretos de montagem nativa (make_component + combine-DENTRO + joint-ENTRE).
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.spatial_ref import (
    ALIGN_GAP_SIDE_UNDETERMINABLE,
    BBOX_NOT_AXIS_ALIGNED,
    RELATIVE_COORD_FORBIDDEN,
    SpatialRefError,
)
from app.modeling.spatial_resolver import (
    F7_PLACEMENT_TOOLS,
    _compute_place_delta,
    enforce_relative_coord,
    expand_placement,
    materialize_steps,
    needs_resolution,
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
                # Tampa FLUTUANDO 1,5 mm acima do topo da caixa (o bug real do
                # gate): base em z=21.5, topo da caixa em z=20.
                bbox_min_mm=[0, 0, 21.5],
                bbox_max_mm=[60, 40, 24.5],
                faces=[
                    ModelStateFace(
                        token="TAMPA_BOTTOM",
                        type="planar",
                        normal_axis="-z",
                        center_mm=[30, 20, 21.5],
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
# 2) place_body → move_body DETERMINÍSTICO (mede faces, calcula o delta)       #
# --------------------------------------------------------------------------- #
def test_place_body_static_deterministic_move_closes_gap() -> None:
    # O bug do gate: tampa flutuando 1,5 mm. O backend MEDE as faces e calcula o
    # delta EXATO (target.z=20 − anchor.z=21.5 = -1.5) → move_body. Folga 0, sem
    # o LLM calcular coordenada. Corpos separados (sem componente/junta).
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
    assert [s.tool_name for s in steps] == ["fusion.move_body"]
    assert steps[0].input_json["body_ref"] == "Tampa"
    assert steps[0].input_json["translation_mm"] == [0.0, 0.0, -1.5]  # fecha a folga
    assert actions[0].kind == "expand_placement"


def test_place_body_centers_body_created_offset() -> None:
    # Gate m3d_plan_fc7bc5: o add_box criou a tampa deslocada (Y=80..120, longe da
    # caixa em Y=0..40). O snap CONCÊNTRICO centra E encosta nas 3 direções — não
    # deixa a tampa longe (mate-axis-only deixava). anchor=[30,100,0] → [30,20,20]
    # → Δ=[0,-80,20].
    st = ModelState(
        bodies=[
            ModelStateBody(
                name="Caixa",
                stable_id="C",
                faces=[
                    ModelStateFace(
                        token="CTOP", type="planar", normal_axis="+z", center_mm=[30, 20, 20]
                    )
                ],
            ),
            ModelStateBody(
                name="Tampa",
                stable_id="T",
                faces=[
                    ModelStateFace(
                        token="TBOT", type="planar", normal_axis="-z", center_mm=[30, 100, 0]
                    )
                ],
            ),
        ]
    )
    steps, _ = expand_placement(
        "fusion.place_body",
        {"body": "Tampa", "anchor": "@token('TBOT')", "target": "@token('CTOP')"},
        st,
    )
    assert steps[0].tool_name == "fusion.move_body"
    assert steps[0].input_json["translation_mm"] == [0.0, -80.0, 20.0]


def test_place_body_role_descriptor_measures_same_delta() -> None:
    # F8: o LLM aponta por role (sem copiar token) → o backend mede as faces e
    # chega no MESMO delta determinístico.
    steps, _ = expand_placement(
        "fusion.place_body",
        {
            "body": "Tampa",
            "anchor": {"body": "Tampa", "role": "bottom_planar"},
            "target": {"body": "Caixa", "role": "top_planar"},
        },
        _state(),
    )
    assert steps[0].tool_name == "fusion.move_body"
    assert steps[0].input_json["translation_mm"] == [0.0, 0.0, -1.5]


def test_align_axis_accepts_predicate_descriptor() -> None:
    steps, _ = expand_placement(
        "fusion.align_axis",
        {
            "body": "Tampa",
            "target": {"body": "Caixa", "face": {"type": "cylindrical", "radius_mm": 2.5}},
        },
        _state(),
    )
    assert steps[0].input_json["face_token_two"] == "CAIXA_BORE"


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


def test_distribute_along_count_and_spacing_typed_not_valueerror() -> None:
    st = _state()
    # count/spacing malformados → SpatialRefError tipado (não ValueError cru que
    # escaparia do execute_plan inteiro).
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.distribute_along", {"edge": "E_HINGE", "count": "abc"}, st)
    with pytest.raises(SpatialRefError):
        expand_placement(
            "fusion.distribute_along",
            {"edge": "E_HINGE", "count": 3, "spacing_mm": "@nope"},
            st,
        )
    # count como @-ref válido resolve (bbox.max_z=20 → 20-17=3 nós).
    steps, _ = expand_placement(
        "fusion.distribute_along",
        {"edge": "E_HINGE", "count": "@body('Caixa').bbox.max_z - 17", "fit": True},
        st,
    )
    assert len([s for s in steps if s.tool_name == "fusion.add_cylinder"]) == 3


def test_distribute_along_spacing_overflow_is_typed() -> None:
    # 5 nós × 20 mm = 80 mm numa aresta de 60 mm → erro tipado, não clamp/overlap.
    with pytest.raises(SpatialRefError):
        expand_placement(
            "fusion.distribute_along",
            {"edge": "E_HINGE", "count": 5, "spacing_mm": 20},
            _state(),
        )


def test_place_body_empty_token_and_unsupported_controls_rejected() -> None:
    st = _state()
    base = {"body": "Tampa", "anchor": "@token('TAMPA_BOTTOM')", "target": "@token('CAIXA_TOP')"}
    # Token vazio não pode passar o guard (cairia no "último corpo" no handler).
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.place_body", {**base, "anchor": "@token('')"}, st)
    # mate/offset ainda não suportados pela junta → erro tipado, não no-op.
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.place_body", {**base, "mate": "coaxial"}, st)
    with pytest.raises(SpatialRefError):
        expand_placement("fusion.place_body", {**base, "offset_mm": 2}, st)


def test_resolve_step_ref_in_unsupported_field_is_typed() -> None:
    # Ref espacial em campo FORA do whitelist não vaza crua p/ o Fusion.
    with pytest.raises(SpatialRefError):
        resolve_step("fusion.add_rectangle", {"corner1_mm": "@token('CAIXA_TOP').center"}, _state())


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


# --------------------------------------------------------------------------- #
# needs_resolution / materialize_steps (apoio do wiring P5)                   #
# --------------------------------------------------------------------------- #
def test_needs_resolution_gates_on_f7_tool_or_ref() -> None:
    assert needs_resolution("fusion.place_body", {}) is True
    assert needs_resolution("fusion.add_cylinder", {"origin_mm": "@token('F').center"}) is True
    box_args = {"center_mm": ["@body('P').bbox.max_z", 0, 0]}
    assert needs_resolution("fusion.add_box", box_args) is True
    # Coordenada absoluta / sem ref → não precisa (no-op, sem probe).
    assert needs_resolution("fusion.add_cylinder", {"origin_mm": [1, 2, 3], "axis": "+z"}) is False
    # Read-only (probe query_geometry) → nunca resolve (evita recursão).
    assert needs_resolution("fusion.query_geometry", {}, read_only=True) is False


def test_materialize_steps_inherits_seq_software_risk_with_fresh_ids() -> None:
    original = ModelingPlanStep(
        seq=7,
        title="Monta tampa",
        software=ModelingSoftware.fusion,
        tool_name="fusion.place_body",
        risk_level=ModelingRiskLevel.medium,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json={"body": "Tampa"},
    )
    concrete, _ = expand_placement(
        "fusion.place_body",
        {"body": "Tampa", "anchor": "@token('TAMPA_BOTTOM')", "target": "@token('CAIXA_TOP')"},
        _state(),
    )
    steps = materialize_steps(original, concrete)
    assert [s.tool_name for s in steps] == ["fusion.move_body"]
    assert all(s.seq == 7 and s.software is ModelingSoftware.fusion for s in steps)
    assert all(s.risk_level is ModelingRiskLevel.medium for s in steps)
    assert all(s.status is ModelingStepStatus.approved and not s.approval_required for s in steps)
    # IDs novos e distintos (não colidem em tool_calls).
    ids = [s.id for s in steps]
    assert len(set(ids)) == len(ids) and original.id not in ids


# --------------------------------------------------------------------------- #
# 3) F9 Pilar 3 — enforcement de coordenada relativa (Gate B)                  #
# --------------------------------------------------------------------------- #
def test_enforce_rejects_overlapping_absolute_move() -> None:
    # Move a Tampa (z=21.5..24.5) PARA DENTRO da caixa (z=0..20) → sobreposição
    # de bbox grande → recusa tipada (o bug "corpos sobrepostos").
    with pytest.raises(SpatialRefError) as exc:
        enforce_relative_coord(
            _state(), "fusion.move_body", {"body_ref": "Tampa", "translation_mm": [0, 0, -15]}
        )
    assert exc.value.code == RELATIVE_COORD_FORBIDDEN
    assert "SOBREPONDO" in str(exc.value)


def test_enforce_rejects_far_absolute_move() -> None:
    # Move a Tampa 80 mm p/ cima → fica longe de tudo → recusa (o bug "tampa a
    # 80 mm"). Aceita ref por nome OU stable_id.
    with pytest.raises(SpatialRefError) as exc:
        enforce_relative_coord(
            _state(), "fusion.move_body", {"body_ref": "ID_TAMPA", "translation_mm": [0, 0, 80]}
        )
    assert exc.value.code == RELATIVE_COORD_FORBIDDEN
    assert "mais próximo" in str(exc.value)


def test_enforce_allows_clean_flush_move() -> None:
    # Move a Tampa -1,5 mm → encosta no topo (folga 0), sem sobrepor → passa.
    enforce_relative_coord(
        _state(), "fusion.move_body", {"body_ref": "Tampa", "translation_mm": [0, 0, -1.5]}
    )  # não levanta


def test_enforce_noop_without_state_or_other_bodies() -> None:
    # NUNCA inventa veredito: sem read-back (state None) ou com 1 só corpo → no-op.
    far = {"body_ref": "Tampa", "translation_mm": [0, 0, 80]}
    enforce_relative_coord(None, "fusion.move_body", far)
    one = ModelState(bodies=[_state().bodies[0]])
    enforce_relative_coord(one, "fusion.move_body", {**far, "body_ref": "Caixa"})


def test_enforce_noop_for_non_move_tool_and_missing_args() -> None:
    st = _state()
    # Tool fora do escopo v1 (add_box) → no-op (não recusa o 1º corpo).
    enforce_relative_coord(st, "fusion.add_box", {"origin_mm": [999, 999, 999]})
    # move_body sem translation/ref → no-op (não há o que medir).
    enforce_relative_coord(st, "fusion.move_body", {"body_ref": "Tampa"})
    enforce_relative_coord(st, "fusion.move_body", {"translation_mm": [0, 0, 80]})
    # Corpo-alvo ausente no estado → no-op.
    absent = {"body_ref": "Inexistente", "translation_mm": [0, 0, 80]}
    enforce_relative_coord(st, "fusion.move_body", absent)


# --------------------------------------------------------------------------- #
# 4) F9 Pilar 1 — modos de alinhamento do place_body (_compute_place_delta)    #
# --------------------------------------------------------------------------- #
def _aligned_body(name: str, bmin: list[float], bmax: list[float]) -> ModelStateBody:
    """Corpo com bbox + UMA face planar de normal cardinal (= alinhado aos eixos,
    pré-requisito de edge/corner)."""
    return ModelStateBody(
        name=name,
        bbox_min_mm=bmin,
        bbox_max_mm=bmax,
        faces=[ModelStateFace(token=f"{name}_BOT", type="planar", normal_axis="-z")],
    )


def test_compute_delta_center_is_concentric_snap() -> None:
    # center (default) = snap concêntrico nos 3 eixos (regressão bit-a-bit do atual).
    assert _compute_place_delta("center", [10, 5, 21.5], [30, 20, 20], 2) == [20.0, 15.0, -1.5]


def test_compute_delta_coplanar_moves_only_normal_axis() -> None:
    # coplanar: só o eixo da normal encosta; NÃO recentraliza o plano (mantém o
    # offset em-plano que o planner deu).
    assert _compute_place_delta("coplanar", [10, 5, 21.5], [30, 20, 20], 2) == [0.0, 0.0, -1.5]


def test_compute_delta_gap_opens_on_anchor_side() -> None:
    # anchor ACIMA do alvo → a folga abre p/ cima (sinal medido, não fixo).
    assert _compute_place_delta("gap", [30, 20, 21.5], [30, 20, 20], 2, gap_mm=2) == [0.0, 0.0, 0.5]
    # anchor ABAIXO → a folga abre p/ baixo (anchor já está 2 mm abaixo → fica).
    assert _compute_place_delta("gap", [30, 20, 18], [30, 20, 20], 2, gap_mm=2) == [0.0, 0.0, 0.0]


def test_compute_delta_gap_follows_target_normal_not_position() -> None:
    # Bug do gate teste 2: a tampa é criada ABAIXO do topo (ac=0 < tc=20). A folga
    # deve abrir no sentido da NORMAL OUTWARD do destino (topo +z → sobe p/ z=22),
    # NÃO pelo lado pré-move (que daria -z e enfiaria a tampa 2 mm DENTRO da caixa).
    box_top = ModelStateFace(token="BT", type="planar", normal_axis="+z")
    lid_bottom = ModelStateFace(token="LB", type="planar", normal_axis="-z")
    delta = _compute_place_delta(
        "gap", [0, 0, 0], [0, 0, 20], 2, gap_mm=2,
        anchor_face=lid_bottom, target_face=box_top,
    )
    assert delta == [0.0, 0.0, 22.0]
    # Só a normal da âncora (alvo sem cardinal) → INWARD da âncora (-(-z)=+z).
    delta2 = _compute_place_delta(
        "gap", [0, 0, 0], [0, 0, 20], 2, gap_mm=2,
        anchor_face=lid_bottom, target_face=ModelStateFace(type="planar"),
    )
    assert delta2 == [0.0, 0.0, 22.0]


def test_compute_delta_gap_recenters_in_plane() -> None:
    # Gate teste 2: tampa criada deslocada (centro 0,0) sobre uma caixa centrada em
    # (25,25). O gap CENTRA no plano (como center) E abre a folga só no eixo da
    # normal — "tampa 2 mm acima" fica centrada E 2 mm acima do topo (z=30).
    box_top = ModelStateFace(token="BT", type="planar", normal_axis="+z")
    lid_bottom = ModelStateFace(token="LB", type="planar", normal_axis="-z")
    delta = _compute_place_delta(
        "gap", [0, 0, 0], [25, 25, 30], 2, gap_mm=2,
        anchor_face=lid_bottom, target_face=box_top,
    )
    assert delta == [25.0, 25.0, 32.0]


def test_compute_delta_gap_coincident_faces_is_typed_error() -> None:
    # Faces coincidentes no eixo do mate + folga≠0 → lado indeterminável → erro
    # tipado (NUNCA chuta o lado).
    with pytest.raises(SpatialRefError) as exc:
        _compute_place_delta("gap", [30, 20, 20], [30, 20, 20], 2, gap_mm=2)
    assert exc.value.code == ALIGN_GAP_SIDE_UNDETERMINABLE
    # gap_mm=0 degenera p/ coplanar (folga 0) → sem erro.
    assert _compute_place_delta("gap", [30, 20, 20], [30, 20, 20], 2, gap_mm=0) == [0.0, 0.0, 0.0]


def test_compute_delta_corner_aligns_both_in_plane_mins() -> None:
    moving = _aligned_body("Tampa", [5, 5, 21.5], [25, 15, 24.5])
    ref = _aligned_body("Caixa", [0, 0, 0], [60, 40, 20])
    # ac = centro da face inferior do moving; tc = centro do topo do ref.
    delta = _compute_place_delta(
        "corner", [15, 10, 21.5], [30, 20, 20], 2, moving=moving, reference=ref
    )
    # x,y: min do moving (5,5) → min do ref (0,0); z: flush (20-21.5).
    assert delta == [-5.0, -5.0, -1.5]


def test_compute_delta_edge_aligns_dominant_axis_centers_other() -> None:
    moving = _aligned_body("Tampa", [5, 5, 21.5], [25, 15, 24.5])
    ref = _aligned_body("Caixa", [0, 0, 0], [60, 40, 20])
    delta = _compute_place_delta(
        "edge", [15, 10, 21.5], [30, 20, 20], 2, moving=moving, reference=ref
    )
    # eixo dominante do ref = x (60>40): alinha min (0-5); y centra (20-10); z flush.
    assert delta == [-5.0, 10.0, -1.5]


def test_compute_delta_edge_corner_reject_rotated_body() -> None:
    # Corpo "rotacionado": planar SEM normal cardinal → AABB não confiável → recusa.
    rotated = ModelStateBody(
        name="Girada",
        bbox_min_mm=[0, 0, 0],
        bbox_max_mm=[10, 10, 10],
        faces=[ModelStateFace(token="R_F", type="planar", normal_axis=None)],
    )
    ref = _aligned_body("Caixa", [0, 0, 0], [60, 40, 20])
    for mode in ("edge", "corner"):
        with pytest.raises(SpatialRefError) as exc:
            _compute_place_delta(mode, [5, 5, 10], [30, 20, 20], 2, moving=rotated, reference=ref)
        assert exc.value.code == BBOX_NOT_AXIS_ALIGNED


def test_compute_delta_edge_corner_require_bboxes() -> None:
    ref = _aligned_body("Caixa", [0, 0, 0], [60, 40, 20])
    no_bbox = ModelStateBody(name="X", faces=[ModelStateFace(type="planar", normal_axis="-z")])
    with pytest.raises(SpatialRefError):
        _compute_place_delta("corner", [0, 0, 0], [0, 0, 0], 2, moving=no_bbox, reference=ref)


def test_compute_delta_unknown_mode_is_typed_error() -> None:
    with pytest.raises(SpatialRefError):
        _compute_place_delta("diagonal", [0, 0, 0], [1, 1, 1], 2)


def test_place_body_align_honored_only_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tampa DESLOCADA em y (centro y=60) p/ distinguir center (recentra) de
    # coplanar (mantém o offset). Caixa topo em z=20, centro [30,20,20].
    st = ModelState(
        bodies=[
            ModelStateBody(
                name="Caixa",
                bbox_min_mm=[0, 0, 0],
                bbox_max_mm=[60, 40, 20],
                faces=[
                    ModelStateFace(
                        token="CX_TOP", type="planar", normal_axis="+z", center_mm=[30, 20, 20]
                    )
                ],
            ),
            ModelStateBody(
                name="Tampa",
                bbox_min_mm=[0, 40, 21.5],
                bbox_max_mm=[60, 80, 24.5],
                faces=[
                    ModelStateFace(
                        token="TP_BOT", type="planar", normal_axis="-z", center_mm=[30, 60, 21.5]
                    )
                ],
            ),
        ]
    )
    args = {
        "body": "Tampa",
        "anchor": "@token('TP_BOT')",
        "target": "@token('CX_TOP')",
        "align": "coplanar",
    }
    # Flag ON: coplanar move só em z (mantém o offset em y).
    monkeypatch.setattr(settings, "modeling_align_modes_enabled", True, raising=False)
    on_steps, _ = expand_placement("fusion.place_body", args, st)
    assert on_steps[0].input_json["translation_mm"] == [0.0, 0.0, -1.5]
    # Flag OFF: align IGNORADO → center recentraliza (delta_y = 20-60 = -40).
    monkeypatch.setattr(settings, "modeling_align_modes_enabled", False, raising=False)
    off_steps, _ = expand_placement("fusion.place_body", args, st)
    assert off_steps[0].input_json["translation_mm"] == [0.0, -40.0, -1.5]
