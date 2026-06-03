"""F7 — Resolver de posicionamento (pré-pass determinístico no backend).

Roda ENTRE o planner e o dispatch (no mesmo molde do ``plan_sanitizer`` F6, e
reusando o probe ``query_geometry`` que já alimenta ``capture_model_state``).
Duas responsabilidades, ambas **puras** dado um ``ModelState`` (testáveis em
mock, sem ``adsk``):

1. **Resolução inline** (:func:`resolve_inline_refs`): em QUALQUER tool, troca
   referências espaciais (``@token('F').center.z``, ``{edge:..., point:along}``)
   nos campos de coordenada/eixo (``origin_mm``/``center_mm``/``position_mm``/
   ``translation_mm``/``axis``…) pelos números concretos. Campos sem ref ficam
   intactos → regressão-segura para os planos de coordenada absoluta atuais.

2. **Expansão declarativa** (:func:`expand_placement`): as 3 tools F7
   (``place_body``/``align_axis``/``distribute_along``) são DECLARATIVAS; o
   resolver as expande em passos CONCRETOS de montagem nativa do Fusion —
   ``make_component`` + ``combine_bodies`` (combine-DENTRO) + ``joint``
   (joint-ENTRE) — ou em N primitivas distribuídas. Reusa os handlers já
   existentes (não reescreve geometria).

Filosofia (ADR-022): a matemática de posição sai do LLM e vira código
determinístico. Fora da gramática / token inexistente → :class:`SpatialRefError`
(``fusion.spatial_ref_unresolved``): NUNCA chuta.

Notas de montagem (a confirmar nos gates Fusion P1/P6):
- O ``joint`` do Fusion deriva geometria de **faces** (``_joint_geo_from_ref``);
  refs de aresta servem para distribuir/medir, não para alimentar a junta
  diretamente — por isso ``align_axis`` exige uma face cilíndrica como alvo.
- ``offset_mm``/``clearance_mm`` são passados adiante no passo de junta; o
  suporte a offset de junta é gate P6 (hoje o handler ignora extras).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.contracts import ModelState
from app.modeling.spatial_ref import (
    SpatialRefError,
    find_body,
    find_edge,
    is_spatial_ref,
    parse_at_expr,
    resolve_axis,
    resolve_point,
    resolve_scalar,
)

logger = logging.getLogger(__name__)

__all__ = [
    "F7_PLACEMENT_TOOLS",
    "ConcreteStep",
    "ResolveAction",
    "resolve_inline_refs",
    "expand_placement",
    "resolve_step",
]

F7_PLACEMENT_TOOLS: frozenset[str] = frozenset(
    {"fusion.place_body", "fusion.align_axis", "fusion.distribute_along"}
)

# Campos cujos valores são pontos (triplas em mm) — resolvidos como ponto, ou,
# se forem lista, com componentes @ resolvidos um a um.
_POINT_FIELDS = frozenset(
    {
        "origin_mm",
        "center_mm",
        "position_mm",
        "translation_mm",
        "base_center_mm",
        "start_mm",
        "end_mm",
    }
)
# Campos cujos valores são eixos (vetor unitário ou cardinal).
_AXIS_FIELDS = frozenset({"axis", "direction", "axis_vector"})
# Campos escalares em que uma @-expr faz sentido (offset/distância).
_SCALAR_FIELDS = frozenset({"offset_mm", "distance_mm", "depth_mm", "clearance_mm", "spacing_mm"})


@dataclass(frozen=True)
class ResolveAction:
    """Registro de uma resolução/expansão (telemetria + teste), no molde de
    ``plan_sanitizer.SanitizeAction``."""

    kind: str  # "resolve_inline_ref" | "expand_placement"
    field: str
    detail: str


@dataclass(frozen=True)
class ConcreteStep:
    """Passo concreto emitido pelo resolver (tool real + args). O executor (P5)
    materializa em ``ModelingPlanStep`` herdando seq/risk do passo declarativo."""

    tool_name: str
    input_json: dict[str, Any] = field(default_factory=dict)
    title: str = ""


# --------------------------------------------------------------------------- #
# 1) Resolução inline de refs em tools comuns                                 #
# --------------------------------------------------------------------------- #
def _has_at(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().startswith("@")
    if isinstance(value, (list, tuple)):
        return any(_has_at(v) for v in value)
    return False


def _resolve_point_field(value: Any, state: ModelState | None) -> tuple[Any, bool]:
    """Resolve um campo-ponto. ``True`` no 2º item se mudou algo."""

    if is_spatial_ref(value):
        return list(resolve_point(value, state)), True
    if isinstance(value, (list, tuple)) and any(_has_at(v) or is_spatial_ref(v) for v in value):
        out = [resolve_scalar(v, state) if (_has_at(v) or is_spatial_ref(v)) else v for v in value]
        return out, True
    return value, False


def resolve_inline_refs(
    tool_name: str, args: Any, state: ModelState | None
) -> tuple[Any, list[ResolveAction]]:
    """Resolve refs espaciais nos campos de coordenada/eixo/escalar de um step.

    Só REESCREVE um campo que contenha ref espacial — planos de coordenada
    absoluta passam intactos (no-op). Não-dict passa direto.
    """

    if not isinstance(args, dict):
        return args, []
    out = dict(args)
    actions: list[ResolveAction] = []
    for key, value in list(out.items()):
        try:
            if key in _POINT_FIELDS:
                new, changed = _resolve_point_field(value, state)
                if changed:
                    out[key] = new
                    actions.append(ResolveAction("resolve_inline_ref", key, f"{value!r} → {new!r}"))
            elif key in _AXIS_FIELDS and is_spatial_ref(value):
                new = list(resolve_axis(value, state))
                out[key] = new
                actions.append(ResolveAction("resolve_inline_ref", key, f"{value!r} → {new!r}"))
            elif key in _SCALAR_FIELDS and _has_at(value):
                new = resolve_scalar(value, state)
                out[key] = new
                actions.append(ResolveAction("resolve_inline_ref", key, f"{value!r} → {new!r}"))
        except SpatialRefError:
            raise
    for a in actions:
        logger.info("spatial_resolver %s [%s] %s", a.kind, a.field, a.detail)
    return out, actions


# --------------------------------------------------------------------------- #
# 2) Expansão das tools declarativas F7                                       #
# --------------------------------------------------------------------------- #
def _face_token_of(ref: Any) -> str | None:
    if isinstance(ref, dict):
        return ref.get("face") or ref.get("token")
    if isinstance(ref, str) and ref.strip().startswith("@"):
        try:
            kind, id_, _ = parse_at_expr(ref)
        except SpatialRefError:
            return None
        if kind in ("token", "face"):
            return id_
    return None


def _owner_body_name(state: ModelState | None, face_token: str | None) -> str | None:
    if not face_token:
        return None
    for b in state.bodies if state else []:
        for f in b.faces:
            if f.token == face_token:
                return b.name
    return None


def _axis_letter(axis: Any) -> str:
    if isinstance(axis, str):
        a = axis.strip().lower().lstrip("+-")
        if a in ("x", "y", "z"):
            return a
    if isinstance(axis, (list, tuple)) and len(axis) >= 3:
        comps = [abs(float(c)) for c in axis[:3]]
        return "xyz"[comps.index(max(comps))]
    return "z"


def _expand_place_body(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    body = args.get("body") or args.get("body_ref")
    if not body:
        raise SpatialRefError("place_body exige 'body'")
    find_body(state, body)  # valida existência (erro tipado se não houver)
    anchor_face = _face_token_of(args.get("anchor"))
    target_face = _face_token_of(args.get("target"))
    if anchor_face is None or target_face is None:
        raise SpatialRefError(
            "place_body: 'anchor' (face no corpo) e 'target' (face de destino) precisam "
            "referenciar FACES — @token('<face>') ou {face:'<token>'}. O mate do Fusion "
            "casa faces, não coordenadas."
        )
    mate = str(args.get("mate") or "flush").lower()
    # Placement estático = junta rígida casando as duas faces resolvidas.
    # (revolute/cilíndrica móvel é papel de align_axis.)
    jargs: dict[str, Any] = {
        "joint_type": "rigid",
        "body_one": body,
        "face_token_one": anchor_face,
        "body_two": _owner_body_name(state, target_face),
        "face_token_two": target_face,
        "mate": mate,
    }
    for opt in ("offset_mm", "clearance_mm"):
        if args.get(opt) is not None:
            jargs[opt] = resolve_scalar(args[opt], state) if _has_at(args[opt]) else args[opt]
    return [
        ConcreteStep(
            "fusion.make_component", {"body_ref": body, "name": body}, f"Componente {body}"
        ),
        ConcreteStep("fusion.joint", jargs, f"Monta {body} ({mate})"),
    ]


def _expand_align_axis(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    body = args.get("body") or args.get("body_ref")
    if not body:
        raise SpatialRefError("align_axis exige 'body'")
    find_body(state, body)
    target_face = _face_token_of(args.get("target"))
    if target_face is None:
        raise SpatialRefError(
            "align_axis: 'target' precisa referenciar uma FACE cilíndrica "
            "(@token('<face do furo/pino>')). O eixo da junta do Fusion vem de faces; "
            "uma aresta sozinha não o alimenta."
        )
    jargs = {
        "joint_type": "revolute",
        "body_one": body,
        "face_selector_one": "cylindrical",
        "body_two": _owner_body_name(state, target_face),
        "face_token_two": target_face,
        "axis": _axis_letter(args.get("body_axis")),
    }
    return [ConcreteStep("fusion.joint", jargs, f"Alinha eixo de {body}")]


def _distribute_fractions(
    count: int, length: float | None, spacing_mm: Any, fit: Any
) -> list[float]:
    if count <= 1:
        return [0.5]
    if spacing_mm and not fit and length and length > 0:
        step = float(spacing_mm)
        total = step * (count - 1)
        start = (length - total) / 2.0  # centra a fileira na aresta
        return [max(0.0, min(1.0, (start + i * step) / length)) for i in range(count)]
    # fit / default: distribui uniformemente incluindo as pontas.
    return [i / (count - 1) for i in range(count)]


def _prototype_step(
    proto: dict[str, Any], point: tuple[float, float, float], name: str, axis_vec: list[float]
) -> ConcreteStep:
    primitive = str(proto.get("primitive") or "cylinder").lower()
    base = {k: v for k, v in proto.items() if k not in ("primitive", "name")}
    base["name"] = name
    if primitive in ("cylinder", "cyl"):
        base.setdefault("axis", axis_vec)
        base["origin_mm"] = list(point)
        return ConcreteStep("fusion.add_cylinder", base, f"Nó {name}")
    if primitive == "box":
        base["center_mm"] = list(point)
        return ConcreteStep("fusion.add_box", base, f"Nó {name}")
    base["position_mm"] = list(point)
    return ConcreteStep(f"fusion.add_{primitive}", base, f"Nó {name}")


def _expand_distribute_along(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    edge_tok = args.get("edge")
    count = int(args.get("count") or 0)
    if not edge_tok or count < 1:
        raise SpatialRefError("distribute_along exige 'edge' (token) e 'count' >= 1")
    edge = find_edge(state, edge_tok)
    proto = dict(args.get("prototype") or {})
    alternate = args.get("alternate")
    axis_vec = list(resolve_axis({"edge": edge_tok}, state))  # eixo dos nós = direção da aresta
    fractions = _distribute_fractions(
        count, edge.length_mm, args.get("spacing_mm"), args.get("fit")
    )

    steps: list[ConcreteStep] = []
    groups: dict[str, list[str]] = {}
    base_name = str(proto.get("name") or "Node")
    for i, frac in enumerate(fractions):
        point = resolve_point({"edge": edge_tok, "point": "along", "fraction": frac}, state)
        name = f"{base_name}_{i + 1}"
        steps.append(_prototype_step(proto, point, name, axis_vec))
        if isinstance(alternate, (list, tuple)) and len(alternate) >= 2:
            parent = str(alternate[i % 2])
            groups.setdefault(parent, []).append(name)

    # combine-DENTRO: cada grupo alternado funde com seu corpo-pai (parte
    # imprimível). O movimento (joint-ENTRE) é declarado à parte (align_axis).
    for parent, nodes in groups.items():
        steps.append(
            ConcreteStep(
                "fusion.combine_bodies",
                {"target_ref": parent, "tool_refs": nodes, "operation": "join"},
                f"Funde {len(nodes)} nó(s) em {parent}",
            )
        )
    return steps


def expand_placement(
    tool_name: str, args: Any, state: ModelState | None
) -> tuple[list[ConcreteStep], list[ResolveAction]]:
    """Expande uma tool declarativa F7 em passos concretos de montagem."""

    if not isinstance(args, dict):
        raise SpatialRefError(f"{tool_name}: argumentos inválidos (esperava objeto)")
    if tool_name == "fusion.place_body":
        steps = _expand_place_body(args, state)
    elif tool_name == "fusion.align_axis":
        steps = _expand_align_axis(args, state)
    elif tool_name == "fusion.distribute_along":
        steps = _expand_distribute_along(args, state)
    else:
        raise SpatialRefError(f"{tool_name} não é uma tool de placement F7")
    action = ResolveAction(
        "expand_placement", tool_name, f"{tool_name} → {len(steps)} passo(s) concreto(s)"
    )
    logger.info("spatial_resolver %s [%s] %s", action.kind, action.field, action.detail)
    return steps, [action]


# --------------------------------------------------------------------------- #
# Entrada única para o executor (P5)                                          #
# --------------------------------------------------------------------------- #
def resolve_step(
    tool_name: str, args: Any, state: ModelState | None
) -> tuple[list[ConcreteStep], list[ResolveAction]]:
    """Resolve UM passo do plano → lista de passos concretos + ações.

    Tool F7 declarativa → expande; qualquer outra → 1 passo com as refs inline
    resolvidas (no-op se não houver ref).
    """

    if tool_name in F7_PLACEMENT_TOOLS:
        return expand_placement(tool_name, args, state)
    new_args, actions = resolve_inline_refs(tool_name, args, state)
    return [ConcreteStep(tool_name, new_args, "")], actions
