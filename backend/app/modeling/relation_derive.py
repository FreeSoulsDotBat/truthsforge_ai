"""F8 Sub 4 — Derivação de relação genérica → primitiva F7 (ADR-023).

Camada de domínio **pura** (sem ``adsk``): dado uma ``RelationSpec`` (vocabulário
FECHADO) + o ``ModelState``, **MEDE** o estado e produz a primitiva F7 concreta
(``place_body``/``align_axis``/``distribute_along``) com descritores role/predicado
que o resolver F7 (Sub1+P4) expande em ``make_component``/``joint``.

**Cada ``kind`` é uma COMPOSIÇÃO declarada de primitivas mensuráveis** (a recipe),
nunca uma derivação dedicada por produto — a barreira codificada contra
macro-disfarçada. A geometria ("qual face", "qual aresta") sai do LLM e vira
medição: o role é resolvido pelo ``entity_ref`` medindo o B-Rep; o raio do encaixe
coaxial é medido aqui. **NUNCA chuta:** corpo/relação não derivável ⇒ erro tipado
(``RelationUnderivableError``), nunca um palpite.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import DerivedRelation, ModelState, ModelStateBody, RelationSpec
from app.modeling.spatial_ref import SpatialRefError

__all__ = [
    "RELATION_KINDS",
    "RELATION_UNDERIVABLE",
    "RelationUnderivableError",
    "derive_relation",
]

RELATION_UNDERIVABLE = "fusion.relation_underivable"

RELATION_KINDS: frozenset[str] = frozenset(
    {
        "flush_mate",
        "cover_opening",
        "seat_in_pocket",
        "coaxial_insert",
        "hinge_along_shared_edge",
        "distribute_on_edge",
    }
)

# Recipe declarativa: kind → (primitiva F7, role da face do moving, role da face
# da referência). É a "composição de primitivas" auditável — mudar um kind é
# mudar a recipe, não escrever geometria nova.
_PLACE_RECIPES: dict[str, tuple[str, str]] = {
    # kind: (moving_role, reference_role)
    "flush_mate": ("bottom_planar", "top_planar"),
    "cover_opening": ("bottom_planar", "open_boundary"),
    "seat_in_pocket": ("bottom_planar", "largest_planar"),
}
# Relações coaxiais → align_axis (junta revolute medindo a face cilíndrica alvo).
_AXIS_KINDS: frozenset[str] = frozenset({"coaxial_insert", "hinge_along_shared_edge"})


class RelationUnderivableError(SpatialRefError):
    """A relação não pode ser derivada do estado (corpo ausente, sem face/aresta
    mensurável, kind fora do vocabulário). Subclasse de ``SpatialRefError`` ⇒ o
    executor já a trata como falha tipada (``_spatial_failure_outcome``)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code=RELATION_UNDERIVABLE)


def _find_body(state: ModelState | None, ref: Any) -> ModelStateBody:
    target = str(ref)
    for b in state.bodies if state else []:
        if b.stable_id == target or b.name == target:
            return b
    avail = [b.name for b in (state.bodies if state else [])]
    raise RelationUnderivableError(f"corpo {ref!r} não encontrado. Disponíveis: {avail}")


def _cylindrical_radius(body: ModelStateBody) -> float | None:
    """Maior raio de face cilíndrica do corpo (o diâmetro externo do pino/furo)."""

    radii = [
        f.radius_mm for f in body.faces if (f.type or "").lower() == "cylindrical" and f.radius_mm
    ]
    return max(radii) if radii else None


def _longest_straight_edge_token(body: ModelStateBody) -> str | None:
    straight = [
        e
        for e in body.edges
        if e.token and not e.is_circular and e.length_mm and e.start_point_mm and e.end_point_mm
    ]
    if not straight:
        return None
    return max(straight, key=lambda e: e.length_mm or 0.0).token


def _derive_place(spec: RelationSpec, state: ModelState | None) -> DerivedRelation:
    moving_role, ref_role = _PLACE_RECIPES[spec.kind]
    moving_role = spec.moving_role or moving_role
    ref_role = spec.reference_role or ref_role
    # Valida existência dos corpos ANTES (erro tipado claro); o token da face é
    # resolvido depois pelo entity_ref (mede o role no B-Rep).
    _find_body(state, spec.moving)
    _find_body(state, spec.reference)
    args = {
        "body": spec.moving,
        "anchor": {"body": spec.moving, "role": moving_role},
        "target": {"body": spec.reference, "role": ref_role},
        "mate": "flush",
    }
    return DerivedRelation(
        kind=spec.kind,
        primitive_tool="fusion.place_body",
        primitive_args=args,
        measured={"moving_role": moving_role, "reference_role": ref_role},
        notes=(
            f"{spec.kind}: encosta {moving_role} de {spec.moving} em {ref_role} de {spec.reference}"
        ),
    )


def _derive_axis(spec: RelationSpec, state: ModelState | None) -> DerivedRelation:
    moving = _find_body(state, spec.moving)
    _find_body(state, spec.reference)
    radius = _cylindrical_radius(moving)
    target_face: dict[str, Any] = {"type": "cylindrical"}
    measured: dict[str, Any] = {}
    if radius is not None:
        # Mede o raio do moving p/ mirar a face cilíndrica de raio compatível na
        # referência (o furo certo entre vários) — não chuta "o primeiro cilindro".
        target_face["radius_mm"] = round(radius, 3)
        measured["moving_radius_mm"] = round(radius, 3)
    args: dict[str, Any] = {
        "body": spec.moving,
        "target": {"body": spec.reference, "face": target_face},
    }
    notes = f"{spec.kind}: alinha eixo de {spec.moving} à face cilíndrica de {spec.reference}"
    if spec.kind == "hinge_along_shared_edge":
        notes += " (dobradiça revolute em torno do furo do pino)"
    # Eixo da junta revolute: o ModelState atual NÃO carrega o vetor-eixo da face
    # cilíndrica (só raio/centro), então não dá p/ MEDIR o eixo aqui. Em vez de
    # assumir Z no escuro (chute — viola "NUNCA chuta"), tornamos explícito:
    # `params.body_axis` define o eixo (ex.: "x" p/ dobradiça lateral); sem ele, a
    # junta cai no default Z do _expand_align_axis — declarado no `measured`/notes
    # p/ não ser silencioso. Medir o eixo da face é trabalho do gate (enriquecer
    # query_geometry com o axis-vector da face cilíndrica).
    body_axis = spec.params.get("body_axis")
    if body_axis is not None:
        args["body_axis"] = body_axis
        measured["body_axis"] = body_axis
    else:
        measured["axis_default"] = "z"
        notes += " [eixo=Z default; passe params.body_axis p/ eixo não-Z]"
    return DerivedRelation(
        kind=spec.kind,
        primitive_tool="fusion.align_axis",
        primitive_args=args,
        measured=measured,
        notes=notes,
    )


def _derive_distribute(spec: RelationSpec, state: ModelState | None) -> DerivedRelation:
    ref = _find_body(state, spec.reference)
    raw_count = spec.count if spec.count is not None else spec.params.get("count")
    # Coerção TIPADA: int() cru de um valor inválido levanta ValueError BASE, que
    # NÃO é SpatialRefError e escaparia do `except` do executor (derruba o plano).
    try:
        count = int(raw_count) if raw_count is not None else 0
    except (TypeError, ValueError):
        raise RelationUnderivableError(
            f"distribute_on_edge: 'count' inválido: {raw_count!r}"
        ) from None
    if count < 1:
        raise RelationUnderivableError("distribute_on_edge exige 'count' >= 1")
    edge = spec.params.get("edge") or _longest_straight_edge_token(ref)
    if not edge:
        raise RelationUnderivableError(
            f"distribute_on_edge: nenhuma aresta reta mensurável em '{spec.reference}' "
            "(passe params.edge ou rode query_geometry)"
        )
    args: dict[str, Any] = {
        "edge": edge,
        "count": count,
        "prototype": spec.params.get("prototype") or {"primitive": "cylinder"},
    }
    for opt in ("spacing_mm", "fit", "alternate"):
        if opt in spec.params:
            args[opt] = spec.params[opt]
    return DerivedRelation(
        kind=spec.kind,
        primitive_tool="fusion.distribute_along",
        primitive_args=args,
        measured={"edge_token": edge, "count": count},
        notes=f"distribute_on_edge: {count} nós ao longo da aresta de {spec.reference}",
    )


def derive_relation(spec: RelationSpec, state: ModelState | None) -> DerivedRelation:
    """Mede o estado e deriva a primitiva F7 concreta da relação. Erro tipado
    (``RelationUnderivableError``) quando o kind é desconhecido ou falta geometria
    mensurável — nunca um palpite."""

    if spec.kind not in RELATION_KINDS:
        raise RelationUnderivableError(
            f"kind de relação desconhecido: {spec.kind!r}. Vocabulário: {sorted(RELATION_KINDS)}"
        )
    if spec.kind in _PLACE_RECIPES:
        return _derive_place(spec, state)
    if spec.kind in _AXIS_KINDS:
        return _derive_axis(spec, state)
    if spec.kind == "distribute_on_edge":
        return _derive_distribute(spec, state)
    raise RelationUnderivableError(f"kind {spec.kind!r} sem recipe de derivação")
