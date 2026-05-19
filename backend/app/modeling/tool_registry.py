"""Single source of truth for the 3D modeling tool allowlist.

Until v2 this allowlist lived in three different places: ``planner.py``
(``PLANNER_TOOLSET``), ``policy.py`` (``READ_ONLY_TOOL_NAMES`` /
``HIGH_RISK_TOOL_NAMES`` / ``BLOCKED_TOOL_PREFIXES``) and each adapter
(``BLENDER_TOOLS`` / ``FUSION_TOOLS``). Keeping them in sync was manual and
error-prone — ADR-013 demands a single registry that downstream modules
consume.

This module exports:

* :class:`ToolDescriptor` — Pydantic model that describes one tool (name,
  owning software, safety category, short description).
* :data:`TOOL_REGISTRY` — canonical ``dict[str, ToolDescriptor]``.
* Derived collections that preserve the old names for backwards
  compatibility (``PLANNER_TOOLSET``, ``READ_ONLY_TOOL_NAMES``,
  ``HIGH_RISK_TOOL_NAMES``, ``BLENDER_TOOLS``, ``FUSION_TOOLS``,
  ``BLOCKED_TOOL_PREFIXES``).
* Helper predicates (:func:`is_blocked`, :func:`is_read_only`,
  :func:`is_high_risk`, :func:`requires_approval`).

Importers should derive everything from :data:`TOOL_REGISTRY` going
forward. The legacy module-level constants will remain only as compatibility
shims while Ondas 1–3 land; once the rest of the code reads the registry
directly they can be dropped.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.core.contracts import ModelingRiskLevel


class ToolCategory(StrEnum):
    """Safety category each modeling tool falls into.

    The policy layer maps these categories to ``approval_required`` and the
    executor uses them when deciding whether a mini-plan in ``editing``
    stage can auto-execute.

    * ``read_only``  — pure inspection. Always safe, ignores ``risk_level``.
    * ``additive``   — adds geometry/files without mutating existing state
                       (primitives, sketches, exports).
    * ``mutative``   — changes existing geometry in a reversible-by-snapshot
                       way (bevel, subdivision, parameter change).
    * ``destructive``— removes geometry/files. Always requires approval.
    * ``high_risk``  — irreversible topology / sandbox-escape operations
                       (booleans, repair_non_manifold, restore_snapshot,
                       run_script). Always requires approval.
    """

    read_only = "read_only"
    additive = "additive"
    mutative = "mutative"
    destructive = "destructive"
    high_risk = "high_risk"


class ToolSoftware(StrEnum):
    """Which subsystem actually executes the tool."""

    blender = "blender"
    fusion = "fusion"
    project_store = "project_store"


class ToolDescriptor(BaseModel):
    """Canonical description of an allowlisted modeling tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    software: ToolSoftware
    category: ToolCategory
    description: str = ""


def _t(
    name: str,
    software: ToolSoftware,
    category: ToolCategory,
    description: str = "",
) -> ToolDescriptor:
    return ToolDescriptor(name=name, software=software, category=category, description=description)


# ---------------------------------------------------------------------------
# Registry. Order matters only for stable derived tuples.
# ---------------------------------------------------------------------------

_BLENDER = ToolSoftware.blender
_FUSION = ToolSoftware.fusion
_PROJECT_STORE = ToolSoftware.project_store

_RO = ToolCategory.read_only
_ADD = ToolCategory.additive
_MUT = ToolCategory.mutative
_DESTR = ToolCategory.destructive  # noqa: F841 — kept for future tools
_HR = ToolCategory.high_risk


_REGISTRY_ENTRIES: tuple[ToolDescriptor, ...] = (
    # ---- Blender: read-only ----
    _t(
        "blender.measure_object",
        _BLENDER,
        _RO,
        "Mede bounding box, dimensões e volume aproximado de um objeto.",
    ),
    _t(
        "blender.validate_mesh",
        _BLENDER,
        _RO,
        "Checks rápidos: non-manifold, loose verts, loose parts.",
    ),
    _t(
        "blender.validate_printability",
        _BLENDER,
        _RO,
        "Relatório completo via bmesh com risk_score.",
    ),
    # ---- Blender: additive ----
    _t(
        "blender.create_mesh_primitive",
        _BLENDER,
        _ADD,
        "Cria primitivos (cube, cylinder, sphere, icosphere, plane, cone, torus).",
    ),
    _t(
        "blender.export_stl",
        _BLENDER,
        _ADD,
        "Exporta a cena para STL no diretório de exports do workspace.",
    ),
    _t(
        "blender.export_obj",
        _BLENDER,
        _ADD,
        "Exporta a cena para OBJ no diretório de exports do workspace.",
    ),
    _t(
        "blender.export_3mf",
        _BLENDER,
        _ADD,
        "Exporta a cena para 3MF no diretório de exports do workspace.",
    ),
    # ---- Blender: mutative ----
    _t(
        "blender.apply_bevel",
        _BLENDER,
        _MUT,
        "Aplica bevel uniforme em todos os meshes da cena.",
    ),
    _t(
        "blender.apply_subdivision",
        _BLENDER,
        _MUT,
        "Aplica modifier SUBSURF (levels 1–6).",
    ),
    _t(
        "blender.apply_solidify",
        _BLENDER,
        _MUT,
        "Aplica modifier SOLIDIFY com thickness_mm e offset.",
    ),
    _t(
        "blender.assign_material",
        _BLENDER,
        _MUT,
        "Cria/atualiza material Principled BSDF e atribui ao slot do objeto.",
    ),
    # ---- Blender: high_risk ----
    _t(
        "blender.apply_boolean",
        _BLENDER,
        _HR,
        "Boolean union/difference/intersect entre objetos; remove auxiliar por padrão.",
    ),
    _t(
        "blender.repair_non_manifold",
        _BLENDER,
        _HR,
        "Sequência destrutiva: dissolve_degenerate, delete_loose, remove_doubles, "
        "normals_make_consistent, fill_holes.",
    ),
    _t(
        "blender.run_script",
        _BLENDER,
        _HR,
        "Execução de script Blender livre. Reservado; nunca exposto ao planner LLM.",
    ),
    # ---- Fusion: read-only ----
    _t(
        "fusion.validate_dimensions",
        _FUSION,
        _RO,
        "Valida dimensões e tolerâncias de um corpo/sketch.",
    ),
    _t(
        "fusion.validate_printability",
        _FUSION,
        _RO,
        "Roda checks de impressibilidade no B-Rep (is_solid, volume, parede, overhang).",
    ),
    # ---- Fusion: additive ----
    _t(
        "fusion.open_design",
        _FUSION,
        _ADD,
        "Abre ou cria um documento Fusion ativo.",
    ),
    _t(
        "fusion.create_sketch",
        _FUSION,
        _ADD,
        "Cria um sketch paramétrico em um plano.",
    ),
    _t(
        "fusion.add_rectangle",
        _FUSION,
        _ADD,
        "Adiciona um perfil retangular dimensionado a um sketch.",
    ),
    _t(
        "fusion.add_circle",
        _FUSION,
        _ADD,
        "Adiciona um perfil circular dimensionado a um sketch.",
    ),
    _t(
        "fusion.export_step",
        _FUSION,
        _ADD,
        "Exporta o design para STEP no diretório de exports.",
    ),
    _t(
        "fusion.export_stl",
        _FUSION,
        _ADD,
        "Exporta o design para STL no diretório de exports.",
    ),
    _t(
        "fusion.export_3mf",
        _FUSION,
        _ADD,
        "Exporta o design para 3MF no diretório de exports.",
    ),
    # ---- Fusion: mutative ----
    _t(
        "fusion.extrude_profile",
        _FUSION,
        _MUT,
        "Extruda um perfil de sketch (operação new_body/join/cut/intersect).",
    ),
    _t(
        "fusion.set_parameter",
        _FUSION,
        _MUT,
        "Altera um parâmetro paramétrico nomeado do design.",
    ),
    # ---- Fusion: high_risk ----
    _t(
        "fusion.run_script",
        _FUSION,
        _HR,
        "Execução de Python via fusion_mcp_execute. Reservado; nunca exposto ao planner LLM.",
    ),
    # ---- project_store: high_risk ----
    _t(
        "project_store.restore_snapshot",
        _PROJECT_STORE,
        _HR,
        "Restaura um snapshot do workspace 3D; sobrescreve estado atual.",
    ),
    # ---- project_store: read-only ----
    _t(
        "project_store.list_snapshots",
        _PROJECT_STORE,
        _RO,
        "Lista snapshots persistidos do projeto/plano.",
    ),
)


TOOL_REGISTRY: dict[str, ToolDescriptor] = {entry.name: entry for entry in _REGISTRY_ENTRIES}
"""Single canonical mapping ``tool_name → ToolDescriptor``.

Imports should prefer reading this dict (or the helper predicates below)
over the legacy module-level tuples/sets.
"""


# ---------------------------------------------------------------------------
# Blocklist (prefix-based). These names are never accepted by the planner or
# the policy layer; they exist to defend against generic catch-all tools that
# the LLM might invent or that upstream MCP servers might add.
# ---------------------------------------------------------------------------

BLOCKED_TOOL_PREFIXES: tuple[str, ...] = (
    "shell.",
    "filesystem.delete",
    "python.exec",
    "network.",
)


# ---------------------------------------------------------------------------
# Derived collections. Computed at import time so legacy callers keep working
# while we migrate to direct registry access in Ondas 2–3.
# ---------------------------------------------------------------------------


def _by_software(software: ToolSoftware) -> tuple[str, ...]:
    return tuple(entry.name for entry in _REGISTRY_ENTRIES if entry.software is software)


def _by_category(category: ToolCategory) -> tuple[str, ...]:
    return tuple(entry.name for entry in _REGISTRY_ENTRIES if entry.category is category)


def _planner_visible() -> tuple[str, ...]:
    """Tools the LLM planner is allowed to choose.

    Excludes ``project_store.*`` (orchestrator-internal) and ``*.run_script``
    (never exposed to LLM-generated plans even though the descriptor exists
    for the policy/audit layers).
    """

    def visible(entry: ToolDescriptor) -> bool:
        if entry.software is ToolSoftware.project_store:
            return False
        if entry.name.endswith(".run_script"):
            return False
        return True

    return tuple(entry.name for entry in _REGISTRY_ENTRIES if visible(entry))


PLANNER_TOOLSET: tuple[str, ...] = _planner_visible()
"""Tools the LLM planner can pick. Subset of ``TOOL_REGISTRY``."""

BLENDER_TOOLS: list[str] = list(_by_software(_BLENDER))
"""Allowlist consumed by :class:`BlenderAdapter`."""

FUSION_TOOLS: tuple[str, ...] = _by_software(_FUSION)
"""Allowlist consumed by :class:`FusionDesktopAdapter`."""

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(_by_category(ToolCategory.read_only))
"""Tools that are always safe to auto-execute regardless of risk_level."""

HIGH_RISK_TOOL_NAMES: frozenset[str] = frozenset(_by_category(ToolCategory.high_risk))
"""Tools that always require human approval, even if the LLM marked them low."""


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def descriptor(tool_name: str) -> ToolDescriptor | None:
    """Return the descriptor for ``tool_name`` or ``None`` if not in the registry."""

    return TOOL_REGISTRY.get(tool_name)


def is_blocked(tool_name: str) -> bool:
    """``True`` when the tool matches a hard blocklist prefix."""

    return tool_name.startswith(BLOCKED_TOOL_PREFIXES)


def is_read_only(tool_name: str) -> bool:
    """``True`` when the tool is classified as read-only."""

    entry = TOOL_REGISTRY.get(tool_name)
    return entry is not None and entry.category is ToolCategory.read_only


def is_high_risk(tool_name: str) -> bool:
    """``True`` when the tool is classified as high-risk."""

    entry = TOOL_REGISTRY.get(tool_name)
    return entry is not None and entry.category is ToolCategory.high_risk


def is_known(tool_name: str) -> bool:
    """``True`` when the tool is registered (regardless of category)."""

    return tool_name in TOOL_REGISTRY


def requires_approval(tool_name: str, risk_level: ModelingRiskLevel | str | None) -> bool:
    """Single decision point for approval gating.

    A step requires approval iff it is high-risk **and** not read-only. The
    ``risk_level`` parameter lets callers escalate medium/low tools when the
    planner explicitly marked them ``high``.
    """

    if is_blocked(tool_name):
        return True
    if is_read_only(tool_name):
        return False
    if is_high_risk(tool_name):
        return True
    if risk_level is None:
        return False
    level = (
        ModelingRiskLevel(risk_level)
        if not isinstance(risk_level, ModelingRiskLevel)
        else risk_level
    )
    return level is ModelingRiskLevel.high


def descriptors() -> Iterable[ToolDescriptor]:
    """Iterate every descriptor in registry order."""

    return iter(_REGISTRY_ENTRIES)


__all__ = [
    "BLENDER_TOOLS",
    "BLOCKED_TOOL_PREFIXES",
    "FUSION_TOOLS",
    "HIGH_RISK_TOOL_NAMES",
    "PLANNER_TOOLSET",
    "READ_ONLY_TOOL_NAMES",
    "TOOL_REGISTRY",
    "ToolCategory",
    "ToolDescriptor",
    "ToolSoftware",
    "descriptor",
    "descriptors",
    "is_blocked",
    "is_high_risk",
    "is_known",
    "is_read_only",
    "requires_approval",
]
