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
_DESTR = ToolCategory.destructive
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
        "fusion.query_geometry",
        _FUSION,
        _RO,
        "Lista bodies/faces/arestas com índice estável + metadata para seleção precisa (G2.2).",
    ),
    _t(
        "fusion.capture_viewport",
        _FUSION,
        _RO,
        "Renderiza o viewport e devolve a imagem (base64) p/ verificação visual no loop.",
    ),
    _t(
        "fusion.query_timeline",
        _FUSION,
        _RO,
        "Lê a timeline (features/ordem/supressão) + parâmetros atuais p/ reconciliação (T3.1).",
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
        "fusion.add_polygon",
        _FUSION,
        _ADD,
        "Adiciona um polígono regular de N lados a um sketch (Onda A).",
    ),
    _t(
        "fusion.add_line",
        _FUSION,
        _ADD,
        "Adiciona uma polilinha (perfil arbitrário, opcionalmente fechado) a um sketch (Onda A).",
    ),
    _t(
        "fusion.add_arc",
        _FUSION,
        _ADD,
        "Adiciona um arco por centro/início/ângulo a um sketch (Onda A).",
    ),
    _t(
        "fusion.add_ellipse",
        _FUSION,
        _ADD,
        "Adiciona uma elipse (major/minor) a um sketch (G3).",
    ),
    _t(
        "fusion.add_slot",
        _FUSION,
        _ADD,
        "Adiciona um slot oblongo (length/width) a um sketch (G3).",
    ),
    _t(
        "fusion.add_box",
        _FUSION,
        _ADD,
        "Cria uma caixa paramétrica (sketch+extrude interno) num passo (Onda B).",
    ),
    _t(
        "fusion.add_cylinder",
        _FUSION,
        _ADD,
        "Cria um cilindro paramétrico num passo (Onda B).",
    ),
    _t(
        "fusion.add_sphere",
        _FUSION,
        _ADD,
        "Cria uma esfera paramétrica (semicírculo revolvido) num passo (Onda B).",
    ),
    _t(
        "fusion.add_cone",
        _FUSION,
        _ADD,
        "Cria um cone/tronco de cone paramétrico num passo (Onda B).",
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
        "fusion.revolve_profile",
        _FUSION,
        _MUT,
        "Revolve um perfil em torno de um eixo (esferas, cones, vasos) (Onda A).",
    ),
    _t(
        "fusion.fillet_edges",
        _FUSION,
        _MUT,
        "Arredonda arestas de um corpo (selector semântico all/top/bottom/...) (Onda C).",
    ),
    _t(
        "fusion.chamfer_edges",
        _FUSION,
        _MUT,
        "Chanfra arestas de um corpo (selector semântico) (Onda C).",
    ),
    _t(
        "fusion.shell_body",
        _FUSION,
        _MUT,
        "Oca um corpo deixando paredes de espessura definida (open_faces top/bottom/none) (Onda C).",
    ),
    _t(
        "fusion.hole",
        _FUSION,
        _MUT,
        "Faz um furo (cut) na face superior de um corpo (Onda C).",
    ),
    _t(
        "fusion.pattern_rectangular",
        _FUSION,
        _MUT,
        "Replica um corpo em grade retangular ao longo de 2 eixos (Onda D).",
    ),
    _t(
        "fusion.pattern_circular",
        _FUSION,
        _MUT,
        "Replica um corpo em torno de um eixo (Onda D).",
    ),
    _t(
        "fusion.mirror_feature",
        _FUSION,
        _MUT,
        "Espelha um corpo em torno de um plano construtivo (Onda D).",
    ),
    _t(
        "fusion.loft_profiles",
        _FUSION,
        _MUT,
        "Loft entre 2+ profiles de sketches (Onda E).",
    ),
    _t(
        "fusion.sweep_profile",
        _FUSION,
        _MUT,
        "Varre um profile ao longo de um caminho (Onda E).",
    ),
    _t(
        "fusion.create_surface_patch",
        _FUSION,
        _MUT,
        "Cria SurfaceBody preenchendo um boundary fechado (sketch ou edge_ids) — Fase 5 T5.1b.",
    ),
    _t(
        "fusion.thicken_surface",
        _FUSION,
        _MUT,
        "Espessa SurfaceBody(ies) gerando Body sólido (ponte surface→solid) — Fase 5 T5.2d.",
    ),
    _t(
        "fusion.stitch_surfaces",
        _FUSION,
        _MUT,
        "Costura 2+ SurfaceBodies; pode fechar volume e virar sólido — Fase 5 T5.2e.",
    ),
    _t(
        "fusion.trim_surface",
        _FUSION,
        _MUT,
        "Apara SurfaceBody com ferramenta (sketch/face); keep=largest — Fase 5 T5.2a.",
    ),
    _t(
        "fusion.extend_surface",
        _FUSION,
        _MUT,
        "Estende SurfaceBody ao longo de arestas livres — Fase 5 T5.2b.",
    ),
    _t(
        "fusion.offset_surface",
        _FUSION,
        _MUT,
        "Cria SurfaceBody paralela a face(s)/superfície(s) por distância — Fase 5 T5.2c.",
    ),
    _t(
        "fusion.unstitch_surface",
        _FUSION,
        _MUT,
        "Quebra body em superfícies individuais por face — inverso do stitch — Fase 5 T5.2f.",
    ),
    # Fase 6 (sheet metal) REMOVIDA — a API Python do Fusion não expõe o
    # workflow (só flangeFeatures read-only; sem convert/bend/unbend/rebend).
    # Ver DT-011 e micro/fase-6-sheet-metal.md. Reintroduzir só se a Autodesk
    # expor a API.
    _t(
        "fusion.move_body",
        _FUSION,
        _MUT,
        "Translada um corpo (Onda F).",
    ),
    _t(
        "fusion.scale_body",
        _FUSION,
        _MUT,
        "Escala uniformemente um corpo (Onda F).",
    ),
    _t(
        "fusion.split_body",
        _FUSION,
        _MUT,
        "Divide um corpo por um plano construtivo/offset (G3).",
    ),
    _t(
        "fusion.add_construction_plane",
        _FUSION,
        _ADD,
        "Cria um plano construtivo por offset de um plano base (Onda E).",
    ),
    _t(
        "fusion.add_spline",
        _FUSION,
        _ADD,
        "Adiciona uma spline ajustada por pontos a um sketch (Onda E).",
    ),
    _t(
        "fusion.combine_bodies",
        _FUSION,
        _HR,
        "Boolean (join/cut/intersect) entre corpos existentes — high risk (Onda D).",
    ),
    _t(
        "fusion.thread",
        _FUSION,
        _MUT,
        "Rosca modelada (real) em face cilíndrica — externa/interna (F3).",
    ),
    _t(
        "fusion.make_component",
        _FUSION,
        _MUT,
        "Transforma um corpo em componente (occurrence) p/ montagens/juntas (F3).",
    ),
    _t(
        "fusion.joint",
        _FUSION,
        _MUT,
        "Junta revolute/rigid/slider/cylindrical entre corpos/componentes (F3).",
    ),
    _t(
        "fusion.place_body",
        _FUSION,
        _ADD,
        "Posiciona um corpo encostando uma face na outra (flush) por referência "
        "declarativa; o backend MEDE as faces e calcula a translação EXATA "
        "(move_body determinístico, folga 0) — sem coordenada chutada (F7).",
    ),
    _t(
        "fusion.align_axis",
        _FUSION,
        _ADD,
        "Alinha o eixo de um corpo a uma face cilíndrica de destino; o resolver "
        "F7 expande em junta revolute/cilíndrica (F7).",
    ),
    _t(
        "fusion.distribute_along",
        _FUSION,
        _ADD,
        "Distribui N primitivas (ex.: knuckles) ao longo de uma aresta, com "
        "alternância e combine-DENTRO; resolvido no backend F7 (F7).",
    ),
    _t(
        "fusion.relate_bodies",
        _FUSION,
        _ADD,
        "Relação declarativa entre 2 corpos (flush_mate/cover_opening/coaxial_insert/"
        "hinge_along_shared_edge/seat_in_pocket/distribute_on_edge); o backend deriva "
        "a geometria medindo e expande nas primitivas F7 (F8 Sub4).",
    ),
    _t(
        "fusion.knuckle_hinge",
        _FUSION,
        _ADD,
        "Macro: dobradiça de knuckles que abre em torno de um pino (F3).",
    ),
    _t(
        "fusion.metric_screw",
        _FUSION,
        _ADD,
        "Macro: parafuso métrico (haste + cabeça + rosca modelada) (F3).",
    ),
    _t(
        "fusion.delete_body",
        _FUSION,
        _DESTR,
        "Remove um corpo — destrutivo, exige aprovação (Onda F).",
    ),
    _t(
        "fusion.rollback_timeline",
        _FUSION,
        _DESTR,
        "Rollback da última edição: apaga features da timeline após um ponto (destrutivo; T3.6).",
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


# Macros com forma de PRODUTO (não de feature genérica). Deprecados do planner
# na virada para o "motor genérico" (2026-06-02): a inteligência mora na
# composição + verificação visual/geométrica do loop, não em macros por caso —
# que não escalam (1 macro por produto = milhares). Os handlers seguem no
# adapter (backward-compat / smoke), mas o LLM não os escolhe mais; ele compõe
# mecanismos a partir de primitivas + features genéricas (thread/joint/pattern).
DEPRECATED_PLANNER_TOOLS: frozenset[str] = frozenset(
    {"fusion.knuckle_hinge", "fusion.metric_screw"}
)


# Tools registradas mas AINDA NÃO oferecidas ao planner LLM — atrás de flag +
# pendentes de gate Fusion (não ofereça um mecanismo não validado ao modelo). O
# executor as resolve quando a flag liga; o owner valida via probe no gate; só
# então entram no nudge/PLANNER_TOOLSET. F8 Sub4: relate_bodies (gate P6).
UNRELEASED_PLANNER_TOOLS: frozenset[str] = frozenset({"fusion.relate_bodies"})


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

    Excludes ``project_store.*`` (orchestrator-internal), ``*.run_script``
    (never exposed to LLM-generated plans), ``*.rollback_timeline`` (undo do
    usuário acionado por botão — nunca planejado pelo LLM) e
    ``*.query_timeline`` (leitura interna do orchestrator p/ reconciliação/
    rollback — o planner não deve gastar passo com ela).
    """

    def visible(entry: ToolDescriptor) -> bool:
        if entry.software is ToolSoftware.project_store:
            return False
        if entry.name.endswith(".run_script"):
            return False
        if entry.name.endswith(".rollback_timeline"):
            return False
        if entry.name.endswith(".query_timeline"):
            return False
        if entry.name.endswith(".capture_viewport"):
            return False  # probe do loop visual (render→visão), não passo do plano
        if entry.name in DEPRECATED_PLANNER_TOOLS:
            return False
        if entry.name in UNRELEASED_PLANNER_TOOLS:
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
