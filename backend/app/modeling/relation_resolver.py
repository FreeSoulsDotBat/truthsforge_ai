"""F8 Sub 4 — Resolução de relação → passos concretos (ADR-023).

Camada **pura** que costura o Sub 4 ao F7: pega um passo declarativo
``fusion.relate_bodies``, **deriva** a primitiva F7 medindo o estado
(``relation_derive``) e a **expande** nos passos concretos
(``make_component``/``joint``) reusando o resolver F7 provado (P1/P4) — a relação
é açúcar sobre primitivas, não um motor de geometria novo.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import ModelState, RelationSpec
from app.modeling.relation_derive import RelationUnderivableError, derive_relation
from app.modeling.spatial_resolver import ConcreteStep, ResolveAction, resolve_step

__all__ = ["RELATE_TOOL", "resolve_relation", "spec_from_args"]

RELATE_TOOL = "fusion.relate_bodies"


def _clean_ref(value: Any) -> str:
    s = str(value or "").strip()
    if s.startswith("@"):
        inner = s[1:]
        if "(" in inner:
            inner = inner[inner.index("(") + 1 :]
        s = inner.strip().rstrip(")").strip().strip("'\"")
    return s


def spec_from_args(args: dict[str, Any]) -> RelationSpec:
    """Constrói a ``RelationSpec`` a partir do ``input_json`` do passo, limpando
    wrappers ``@body('X')`` dos corpos. ``RelationUnderivableError`` (tipado)
    quando faltam campos obrigatórios."""

    kind = str(args.get("kind") or "").strip()
    moving = _clean_ref(args.get("moving") or args.get("body"))
    reference = _clean_ref(args.get("reference") or args.get("target"))
    if not kind or not moving or not reference:
        raise RelationUnderivableError("relate_bodies exige 'kind', 'moving' e 'reference'.")
    return RelationSpec(
        kind=kind,  # type: ignore[arg-type]  # validado em derive_relation
        moving=moving,
        reference=reference,
        moving_role=args.get("moving_role"),
        reference_role=args.get("reference_role"),
        count=args.get("count"),
        params=dict(args.get("params") or {}),
    )


def resolve_relation(
    args: dict[str, Any], state: ModelState | None
) -> tuple[list[ConcreteStep], list[ResolveAction]]:
    """Deriva a relação (medindo) e expande na primitiva F7 → passos concretos +
    ações. Erro tipado (``RelationUnderivableError``/``SpatialRefError``) — nunca
    posiciona no escuro."""

    try:
        spec = RelationSpec.model_validate(spec_from_args(args).model_dump())
    except RelationUnderivableError:
        raise
    except Exception as exc:  # pydantic: kind fora do Literal etc.
        raise RelationUnderivableError(f"relate_bodies inválido: {exc}") from exc

    derived = derive_relation(spec, state)
    concrete, actions = resolve_step(derived.primitive_tool, derived.primitive_args, state)
    head = ResolveAction(
        "derive_relation",
        spec.kind,
        f"{spec.kind} → {derived.primitive_tool} (medido: {derived.measured})",
    )
    return concrete, [head, *actions]
