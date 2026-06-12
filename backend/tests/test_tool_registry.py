"""Tests for :mod:`app.modeling.tool_registry`, the single source of truth
for the 3D modeling allowlist (ADR-013).

These tests pin the behaviour of the registry and the predicates so that
future edits cannot silently widen the allowlist or accidentally expose a
``run_script`` tool to the LLM planner.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.contracts import ModelingRiskLevel
from app.modeling.tool_registry import (
    BLENDER_TOOLS,
    BLOCKED_TOOL_PREFIXES,
    FUSION_TOOLS,
    HIGH_RISK_TOOL_NAMES,
    PLANNER_TOOLSET,
    READ_ONLY_TOOL_NAMES,
    TOOL_REGISTRY,
    ToolCategory,
    ToolDescriptor,
    ToolSoftware,
    descriptor,
    descriptors,
    is_blocked,
    is_destructive,
    is_high_risk,
    is_known,
    is_read_only,
    requires_approval,
)

# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


def test_registry_keys_match_descriptor_names() -> None:
    for name, entry in TOOL_REGISTRY.items():
        assert name == entry.name
        assert isinstance(entry, ToolDescriptor)


def test_registry_covers_every_documented_tool() -> None:
    expected = {
        "blender.measure_object",
        "blender.validate_mesh",
        "blender.validate_printability",
        "blender.create_mesh_primitive",
        "blender.export_stl",
        "blender.export_obj",
        "blender.export_3mf",
        "blender.apply_bevel",
        "blender.apply_subdivision",
        "blender.apply_solidify",
        "blender.assign_material",
        "blender.apply_boolean",
        "blender.repair_non_manifold",
        "blender.run_script",
        "fusion.validate_dimensions",
        "fusion.validate_printability",
        "fusion.open_design",
        "fusion.create_sketch",
        "fusion.add_rectangle",
        "fusion.add_circle",
        "fusion.export_step",
        "fusion.export_stl",
        "fusion.export_3mf",
        "fusion.extrude_profile",
        "fusion.set_parameter",
        "fusion.run_script",
        "project_store.restore_snapshot",
        "project_store.list_snapshots",
    }
    assert expected.issubset(set(TOOL_REGISTRY))


def test_descriptor_lookup_returns_none_for_unknown_tools() -> None:
    assert descriptor("blender.no_such_tool") is None
    assert is_known("fusion.imaginary") is False
    assert is_known("blender.apply_boolean") is True


def test_descriptors_iterates_in_registry_order() -> None:
    names = [entry.name for entry in descriptors()]
    assert names == list(TOOL_REGISTRY.keys())


def test_descriptor_is_immutable() -> None:
    entry = TOOL_REGISTRY["blender.apply_boolean"]
    with pytest.raises(ValidationError):
        entry.name = "blender.apply_boolean_v2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Derived collections
# ---------------------------------------------------------------------------


def test_planner_toolset_excludes_orchestrator_internal_tools() -> None:
    assert "project_store.restore_snapshot" not in PLANNER_TOOLSET
    assert "project_store.list_snapshots" not in PLANNER_TOOLSET
    # T3.2/T3.6: leitura de timeline e undo são internos do orchestrator
    # (reconciliação / botão de rollback), não passos que o planner deva emitir.
    assert "fusion.query_timeline" not in PLANNER_TOOLSET
    assert "fusion.rollback_timeline" not in PLANNER_TOOLSET


def test_planner_toolset_excludes_run_script_tools() -> None:
    assert "blender.run_script" not in PLANNER_TOOLSET
    assert "fusion.run_script" not in PLANNER_TOOLSET


def test_planner_toolset_matches_allowlist() -> None:
    """A allowlist visível ao planner = base v1 (24 tools) + Onda A.

    Onda A (spec adapter-tools-mvp.md) adicionou 4 tools de geometria/feature
    ao Fusion: add_polygon, add_line, add_arc, revolve_profile. Ao adicionar
    novas ondas (B-F), inclua as tools aqui.
    """

    expected = {
        "blender.create_mesh_primitive",
        "blender.apply_bevel",
        "blender.apply_boolean",
        "blender.apply_subdivision",
        "blender.apply_solidify",
        "blender.assign_material",
        "blender.measure_object",
        "blender.repair_non_manifold",
        "blender.validate_mesh",
        "blender.validate_printability",
        "blender.export_stl",
        "blender.export_obj",
        "blender.export_3mf",
        "fusion.open_design",
        "fusion.create_sketch",
        "fusion.add_rectangle",
        "fusion.add_circle",
        "fusion.extrude_profile",
        "fusion.set_parameter",
        "fusion.export_step",
        "fusion.export_stl",
        "fusion.export_3mf",
        "fusion.validate_dimensions",
        "fusion.validate_printability",
        # Onda A
        "fusion.add_polygon",
        "fusion.add_line",
        "fusion.add_arc",
        "fusion.revolve_profile",
        # Onda B
        "fusion.add_box",
        "fusion.add_cylinder",
        "fusion.add_sphere",
        "fusion.add_cone",
        # Onda C
        "fusion.fillet_edges",
        "fusion.chamfer_edges",
        "fusion.shell_body",
        "fusion.hole",
        # Onda D
        "fusion.pattern_rectangular",
        "fusion.pattern_circular",
        "fusion.mirror_feature",
        "fusion.combine_bodies",
        # F3 (mecanismos funcionais — features genéricas)
        "fusion.thread",
        "fusion.make_component",
        "fusion.joint",
        # F7 (posicionamento paramétrico — placement declarativo; o resolver de
        # backend as expande em componente/combine/junta antes do dispatch).
        "fusion.place_body",
        "fusion.align_axis",
        "fusion.distribute_along",
        # F8 Sub4: relate_bodies LIBERADO pós-gate F8.R1 (2026-06-09).
        "fusion.relate_bodies",
        # knuckle_hinge / metric_screw: DEPRECADOS do planner (macros de produto,
        # não escalam). Seguem no adapter, mas o LLM não os escolhe — ver
        # DEPRECATED_PLANNER_TOOLS e test_deprecated_macros_excluded_from_planner.
        # Onda E
        "fusion.loft_profiles",
        "fusion.sweep_profile",
        "fusion.add_construction_plane",
        "fusion.add_spline",
        # Onda F
        "fusion.move_body",
        "fusion.scale_body",
        "fusion.delete_body",
        # Onda 9 (G2.2 / G3)
        "fusion.query_geometry",
        "fusion.add_ellipse",
        "fusion.add_slot",
        "fusion.split_body",
        # Fase 5 (Superfícies — NURBS)
        "fusion.create_surface_patch",
        "fusion.thicken_surface",
        "fusion.stitch_surfaces",
        "fusion.trim_surface",
        "fusion.extend_surface",
        "fusion.offset_surface",
        "fusion.unstitch_surface",
        # Fase 6 (Sheet metal) REMOVIDA — API do Fusion não suporta (DT-011).
    }
    assert set(PLANNER_TOOLSET) == expected


def test_blender_tools_lists_every_blender_descriptor_except_run_script() -> None:
    # The adapter export already strips ``blender.run_script`` (see
    # ``blender_adapter.py``); the registry-level list keeps the descriptor
    # so policy/audit can still classify it.
    blender_entries = {
        entry.name for entry in descriptors() if entry.software is ToolSoftware.blender
    }
    assert blender_entries == set(BLENDER_TOOLS) | {"blender.run_script"}


def test_fusion_tools_lists_every_fusion_descriptor_except_run_script() -> None:
    fusion_entries = {
        entry.name for entry in descriptors() if entry.software is ToolSoftware.fusion
    }
    assert fusion_entries == set(FUSION_TOOLS) | {"fusion.run_script"}


def test_deprecated_macros_excluded_from_planner_but_kept_in_adapter() -> None:
    """Virada motor-genérico (2026-06-02): macros de PRODUTO (knuckle_hinge/
    metric_screw) saíram do planner (não escalam), mas os handlers seguem no
    adapter (backward-compat). O LLM compõe mecanismos de primitivas."""
    from app.modeling.tool_registry import DEPRECATED_PLANNER_TOOLS

    assert DEPRECATED_PLANNER_TOOLS == {"fusion.knuckle_hinge", "fusion.metric_screw"}
    for name in DEPRECATED_PLANNER_TOOLS:
        assert name not in PLANNER_TOOLSET  # LLM não escolhe mais
        assert name in FUSION_TOOLS  # adapter ainda conhece (smoke/compat)
    # As features GENÉRICAS continuam visíveis ao planner.
    assert "fusion.thread" in PLANNER_TOOLSET
    assert "fusion.joint" in PLANNER_TOOLSET
    assert "fusion.make_component" in PLANNER_TOOLSET


def test_relate_bodies_released_after_gate() -> None:
    """F8 Sub4: relate_bodies foi LIBERADO ao planner (2026-06-09) após o gate
    F8.R1 aprovar a derivação flush_mate no Fusion real."""
    from app.modeling.tool_registry import (
        UNRELEASED_PLANNER_TOOLS,
        is_known,
    )

    assert is_known("fusion.relate_bodies")
    assert "fusion.relate_bodies" in FUSION_TOOLS
    assert "fusion.relate_bodies" not in UNRELEASED_PLANNER_TOOLS
    assert "fusion.relate_bodies" in PLANNER_TOOLSET  # liberado pós-gate


# ---------------------------------------------------------------------------
# Visibilidade RUNTIME ao planner (auditoria 2026-06-10, linha 768): com a flag
# OFF as tools declarativas F7/F8 não podem aparecer no toolset do planner —
# o LLM era ensinado (schema no prompt + enum) a escolher tools que falhariam
# garantido no adapter. A executabilidade (executor/policy) NÃO muda.
# ---------------------------------------------------------------------------


def _set_planner_flags(monkeypatch: pytest.MonkeyPatch, *, spatial: bool, relation: bool) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "modeling_spatial_resolution_enabled", spatial, raising=False)
    monkeypatch.setattr(settings, "modeling_relation_placement_enabled", relation, raising=False)


def test_planner_toolset_runtime_hides_spatial_trio_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modeling.tool_registry import SPATIAL_PLANNER_TOOLS, planner_toolset

    assert SPATIAL_PLANNER_TOOLS == {
        "fusion.place_body",
        "fusion.align_axis",
        "fusion.distribute_along",
    }
    _set_planner_flags(monkeypatch, spatial=False, relation=True)
    visible = set(planner_toolset())
    assert not visible & SPATIAL_PLANNER_TOOLS
    assert "fusion.relate_bodies" in visible  # flag de relação segue ON

    _set_planner_flags(monkeypatch, spatial=True, relation=True)
    assert SPATIAL_PLANNER_TOOLS <= set(planner_toolset())


def test_planner_toolset_runtime_hides_relate_bodies_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modeling.tool_registry import RELATION_PLANNER_TOOLS, planner_toolset

    assert RELATION_PLANNER_TOOLS == {"fusion.relate_bodies"}
    _set_planner_flags(monkeypatch, spatial=True, relation=False)
    visible = set(planner_toolset())
    assert "fusion.relate_bodies" not in visible
    assert "fusion.place_body" in visible  # flag espacial segue ON

    _set_planner_flags(monkeypatch, spatial=True, relation=True)
    assert "fusion.relate_bodies" in planner_toolset()


def test_planner_toolset_runtime_equals_superset_with_flags_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flags ON ⇒ idêntico (inclusive ordem) ao superset estático PLANNER_TOOLSET."""

    from app.modeling.tool_registry import planner_toolset

    _set_planner_flags(monkeypatch, spatial=True, relation=True)
    assert planner_toolset() == PLANNER_TOOLSET


def test_planner_toolset_runtime_preserves_order_and_executability_with_flags_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flags OFF ⇒ some só o quarteto flag-gated (ordem preservada); a
    EXECUTABILIDADE não muda — as tools seguem no registry e em FUSION_TOOLS."""

    from app.modeling.tool_registry import (
        RELATION_PLANNER_TOOLS,
        SPATIAL_PLANNER_TOOLS,
        planner_toolset,
    )

    _set_planner_flags(monkeypatch, spatial=False, relation=False)
    gated = SPATIAL_PLANNER_TOOLS | RELATION_PLANNER_TOOLS
    expected = tuple(name for name in PLANNER_TOOLSET if name not in gated)
    assert planner_toolset() == expected
    for name in gated:
        assert is_known(name)  # registry/policy intactos
        assert name in FUSION_TOOLS  # adapter/executor seguem conhecendo


def test_read_only_set_matches_allowlist() -> None:
    expected = {
        "blender.measure_object",
        "blender.validate_mesh",
        "blender.validate_printability",
        "fusion.validate_dimensions",
        "fusion.validate_printability",
        "project_store.list_snapshots",
        # G2.2: inspeção de geometria para seleção por índice.
        "fusion.query_geometry",
        # Loop visual: render do viewport p/ verificação por visão (read-only).
        "fusion.capture_viewport",
        # T3.1: leitura da timeline (reconciliação/rollback; interna do orchestrator).
        "fusion.query_timeline",
    }
    assert set(READ_ONLY_TOOL_NAMES) == expected


def test_high_risk_set_matches_allowlist() -> None:
    expected = {
        "blender.apply_boolean",
        "blender.repair_non_manifold",
        "blender.run_script",
        "fusion.run_script",
        "project_store.restore_snapshot",
        # Onda D: boolean entre corpos existentes é high risk.
        "fusion.combine_bodies",
    }
    assert set(HIGH_RISK_TOOL_NAMES) == expected


def test_blocked_prefixes_unchanged() -> None:
    assert BLOCKED_TOOL_PREFIXES == (
        "shell.",
        "filesystem.delete",
        "python.exec",
        "network.",
    )


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def test_is_blocked_matches_prefixes() -> None:
    assert is_blocked("shell.rm")
    assert is_blocked("filesystem.delete")
    assert is_blocked("python.exec")
    assert is_blocked("network.fetch")
    assert not is_blocked("blender.apply_boolean")
    assert not is_blocked("filesystem.write")


def test_is_read_only_only_true_for_read_only_category() -> None:
    assert is_read_only("blender.measure_object")
    assert is_read_only("fusion.validate_printability")
    assert not is_read_only("blender.apply_bevel")
    assert not is_read_only("blender.no_such_tool")


def test_is_high_risk_only_true_for_high_risk_category() -> None:
    assert is_high_risk("blender.apply_boolean")
    assert is_high_risk("project_store.restore_snapshot")
    assert not is_high_risk("blender.apply_bevel")
    assert not is_high_risk("blender.no_such_tool")


def test_fusion_registry_tools_have_script_handlers() -> None:
    """Contrato cross-layer (fusion-operations.md §5): toda tool fusion do
    registry tem handler executável em ``fusion_mcp_scripts``, exceto as
    expandidas pelo resolver ANTES do dispatch (lista explícita). Foi a falta
    deste teste que deixou ``fusion.relate_bodies`` ser exposta inexecutável
    pelo MCP standalone."""

    from app.modeling.fusion_mcp_scripts import FUSION_SCRIPT_TOOLS

    sem_handler_por_design = {
        "fusion.relate_bodies",  # F7: o resolver expande ANTES do dispatch
        "fusion.run_script",  # RF-023: nunca executável (nem exposto)
    }
    missing = set(FUSION_TOOLS) - set(FUSION_SCRIPT_TOOLS) - sem_handler_por_design
    assert not missing, f"tools fusion sem handler executável: {sorted(missing)}"
    orphan_handlers = set(FUSION_SCRIPT_TOOLS) - set(FUSION_TOOLS)
    assert not orphan_handlers, f"handlers sem registro na allowlist: {sorted(orphan_handlers)}"


def test_is_destructive_only_true_for_destructive_category() -> None:
    assert is_destructive("fusion.delete_body")
    assert not is_destructive("blender.apply_bevel")
    assert not is_destructive("blender.no_such_tool")


def test_requires_approval_decision_table() -> None:
    # high_risk tool → always requires approval, no matter the declared risk
    assert requires_approval("blender.apply_boolean", ModelingRiskLevel.low)
    assert requires_approval("blender.apply_boolean", "high")
    # destructive tool → always requires approval (P6/P8), no matter o rótulo
    # de risco que o LLM atribuiu ao passo
    assert requires_approval("fusion.delete_body", ModelingRiskLevel.low)
    assert requires_approval("fusion.delete_body", ModelingRiskLevel.medium)
    assert requires_approval("fusion.delete_body", None)
    # read_only tool → never requires approval, even if marked high
    assert not requires_approval("blender.measure_object", ModelingRiskLevel.high)
    # additive/mutative tool at low risk → no approval
    assert not requires_approval("blender.apply_bevel", ModelingRiskLevel.low)
    # additive/mutative tool escalated to high → approval
    assert requires_approval("blender.apply_bevel", ModelingRiskLevel.high)
    # blocked prefix → approval regardless of registry membership
    assert requires_approval("shell.rm", ModelingRiskLevel.low)
    # unknown tool, low risk → no approval (caller is expected to reject the
    # step earlier, via planner allowlist enforcement)
    assert not requires_approval("blender.no_such_tool", ModelingRiskLevel.low)
    # ``None`` risk level still respects category-based rules
    assert requires_approval("blender.apply_boolean", None)
    assert not requires_approval("blender.measure_object", None)


def test_categories_are_disjoint_for_known_tools() -> None:
    read_only = {e.name for e in descriptors() if e.category is ToolCategory.read_only}
    high_risk = {e.name for e in descriptors() if e.category is ToolCategory.high_risk}
    assert not (read_only & high_risk)
