"""F8 Sub 1 — Referência robusta de entidades por role/predicado (ADR-023).

Camada de domínio **pura** (sem ``adsk``): resolve um DESCRITOR de domínio
declarativo — ``{body:"Tampa", role:"bottom_planar"}`` ou predicado
``{body:"Caixa", face:{type:"cylindrical", radius_mm:5}}`` — num **handle estável
que JÁ existe** (``entityToken`` da face/aresta, ``stable_id`` do corpo),
MEDINDO o ``ModelState``. O LLM ECOA um apelido legível (role) ou descreve por
predicado; **nunca copia o token opaco** (causa do bug `@token('<...>')`).

Desambiguação determinística: filtra candidatos, ordena por score, e se o top-1
não se separa do top-2 por margem ⇒ ``AmbiguousRefError`` com ``alternatives``
(NUNCA escolhe no escuro). Espelha o ``SpatialRefError`` do ``spatial_ref``.

> Honestidade (ADR-023): role NÃO é prometido estável a edição paramétrica; é o
> caminho conveniente. A robustez de verdade p/ geometria complexa vem das
> RELAÇÕES (Sub 4). Quando o role ecoado não casa mais ⇒ erro tipado pedindo
> re-leitura, nunca resolve errado.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import EntityRef, ModelState, ModelStateBody, ModelStateFace
from app.modeling.spatial_ref import SpatialRefError

__all__ = [
    "ENTITY_REF_UNRESOLVED",
    "ENTITY_REF_AMBIGUOUS",
    "EntityRefError",
    "AmbiguousRefError",
    "resolve_entity",
]

ENTITY_REF_UNRESOLVED = "fusion.entity_ref_unresolved"
ENTITY_REF_AMBIGUOUS = "fusion.entity_ref_ambiguous"

_AREA_TOL = 0.5  # mm² — margem p/ separar top-1 de top-2 em "largest"
_POS_TOL = 0.1  # mm — margem p/ separar extremos (top/bottom)
_RADIUS_TOL = 0.5  # mm — casamento de raio


class EntityRefError(SpatialRefError):
    """Descritor de entidade fora da gramática / sem candidato no ModelState.

    Subclasse de ``SpatialRefError`` p/ o executor já tratar (``_spatial_failure_
    outcome``) sem código novo — é a mesma família "resolução falhou, tipado,
    nunca chuta"."""

    def __init__(self, message: str, *, code: str = ENTITY_REF_UNRESOLVED) -> None:
        super().__init__(message, code=code)


class AmbiguousRefError(EntityRefError):
    """Mais de um candidato empatado — exige qualificar melhor o descritor."""

    def __init__(self, message: str, alternatives: list[str]) -> None:
        super().__init__(message, code=ENTITY_REF_AMBIGUOUS)
        self.alternatives = alternatives


# --------------------------------------------------------------------------- #
def _find_body(state: ModelState | None, ref: Any) -> ModelStateBody:
    target = str(ref)
    for b in state.bodies if state else []:
        if b.stable_id == target or b.name == target:
            return b
    avail = [b.name for b in (state.bodies if state else [])]
    raise EntityRefError(f"corpo {ref!r} não encontrado. Disponíveis: {avail}")


def _candidate_faces(
    state: ModelState | None, body_ref: Any
) -> list[tuple[ModelStateBody, ModelStateFace]]:
    out: list[tuple[ModelStateBody, ModelStateFace]] = []
    for b in state.bodies if state else []:
        if body_ref and b.name != str(body_ref) and b.stable_id != str(body_ref):
            continue
        for f in b.faces:
            if f.token:
                out.append((b, f))
    return out


def _pick_extreme(
    cands: list[tuple[ModelStateBody, ModelStateFace]],
    key,
    *,
    maximize: bool,
    tol: float,
    label: str,
) -> tuple[ModelStateBody, ModelStateFace]:
    ranked = sorted(cands, key=key, reverse=maximize)
    top = ranked[0]
    if len(ranked) > 1 and abs(key(top) - key(ranked[1])) <= tol:
        alts = [f.token for _, f in ranked[:3] if f.token]
        raise AmbiguousRefError(
            f"{label}: candidatos empatados ({key(top)}≈{key(ranked[1])}); "
            "qualifique melhor (role/predicado mais específico).",
            alternatives=alts,
        )
    return top


def _center_z(bf: tuple[ModelStateBody, ModelStateFace]) -> float:
    c = bf[1].center_mm
    return c[2] if c and len(c) >= 3 else 0.0


def _area(bf: tuple[ModelStateBody, ModelStateFace]) -> float:
    return bf[1].area_mm2 or 0.0


def _resolve_face_by_role(
    role: str, cands: list[tuple[ModelStateBody, ModelStateFace]]
) -> tuple[ModelStateBody, ModelStateFace]:
    role = role.lower()
    if role in ("top_planar", "top", "bottom_planar", "bottom"):
        # Face HORIZONTAL (normal no eixo z, qualquer sinal) extrema em z: top = a
        # de MAIOR center_z, bottom = a de MENOR. Ranquear por POSIÇÃO (não pelo
        # sinal do normal) é robusto ao read-back que classifica o normal do FUNDO
        # como '+z' (normal de superfície, não outward) — o bug que deixava
        # 'bottom_planar' sem candidato e quebrava o place_body da tampa.
        horizontal = [
            bf for bf in cands if (bf[1].normal_axis or "").lower() in ("+z", "-z", "z")
        ]
        if not horizontal:
            raise EntityRefError(f"role '{role}': nenhuma face planar horizontal (eixo z)")
        top = role in ("top_planar", "top")
        return _pick_extreme(horizontal, _center_z, maximize=top, tol=_POS_TOL, label=role)
    if role == "largest":
        return _pick_extreme(cands, _area, maximize=True, tol=_AREA_TOL, label=role)
    if role in ("largest_planar", "largest_flat"):
        planar = [bf for bf in cands if (bf[1].type or "").lower() == "planar"]
        if not planar:
            raise EntityRefError(f"role '{role}': nenhuma face planar")
        return _pick_extreme(planar, _area, maximize=True, tol=_AREA_TOL, label=role)
    if role in ("open_boundary", "opening"):
        # F8 Sub4: a face da ABERTURA (ex.: topo de caixa ocada). Prefere as
        # marcadas is_open_boundary (medidas pelo script atrás do gate); sem o
        # sinal, cai na maior planar +z (a borda aberta típica de um shell top).
        flagged = [bf for bf in cands if bf[1].is_open_boundary]
        if flagged:
            return _pick_extreme(flagged, _area, maximize=True, tol=_AREA_TOL, label=role)
        planar_up = [bf for bf in cands if (bf[1].normal_axis or "").lower() in ("+z", "z")]
        if not planar_up:
            raise EntityRefError(f"role '{role}': nenhuma face de abertura (+z planar)")
        return _pick_extreme(planar_up, _area, maximize=True, tol=_AREA_TOL, label=role)
    raise EntityRefError(
        f"role de face desconhecido: {role!r} "
        "(top_planar/bottom_planar/largest/largest_planar/open_boundary)"
    )


def _resolve_face_by_predicate(
    pred: dict[str, Any], cands: list[tuple[ModelStateBody, ModelStateFace]]
) -> tuple[ModelStateBody, ModelStateFace]:
    filtered = cands
    if "type" in pred:
        t = str(pred["type"]).lower()
        filtered = [bf for bf in filtered if (bf[1].type or "").lower() == t]
    if "normal" in pred:
        n = str(pred["normal"]).lower()
        filtered = [bf for bf in filtered if (bf[1].normal_axis or "").lower() == n]
    if pred.get("radius_mm") is not None:
        r = float(pred["radius_mm"])
        filtered = [
            bf
            for bf in filtered
            if bf[1].radius_mm is not None and abs(bf[1].radius_mm - r) <= _RADIUS_TOL
        ]
    if not filtered:
        raise EntityRefError(f"nenhuma face casa o predicado {pred!r}")
    if pred.get("largest"):
        return _pick_extreme(
            filtered, _area, maximize=True, tol=_AREA_TOL, label="predicado:largest"
        )
    if len(filtered) == 1:
        return filtered[0]
    alts = [f.token for _, f in filtered[:3] if f.token]
    raise AmbiguousRefError(
        f"{len(filtered)} faces casam {pred!r}; qualifique (ex.: largest:true ou normal).",
        alternatives=alts,
    )


def resolve_entity(descriptor: Any, state: ModelState | None) -> EntityRef:
    """Resolve um descritor de domínio num ``EntityRef`` com handle estável.

    Formas: ``{body:"X"}`` (corpo), ``{body:"X", role:"top_planar"}`` (face por
    apelido), ``{body:"X", face:{type:"cylindrical", radius_mm:5}}`` (predicado).
    Levanta ``EntityRefError``/``AmbiguousRefError`` — nunca chuta.
    """

    if not isinstance(descriptor, dict):
        raise EntityRefError(f"descritor de entidade inválido: {descriptor!r}")

    # Face por role/predicado.
    if "role" in descriptor or isinstance(descriptor.get("face"), dict):
        cands = _candidate_faces(state, descriptor.get("body"))
        if not cands:
            raise EntityRefError(
                f"sem faces p/ {descriptor.get('body') or 'qualquer corpo'} no ModelState "
                "(rode query_geometry)"
            )
        if "role" in descriptor:
            b, f = _resolve_face_by_role(str(descriptor["role"]), cands)
            name = str(descriptor["role"])
        else:
            b, f = _resolve_face_by_predicate(descriptor["face"], cands)
            name = f.type or "face"
        return EntityRef(kind="face", handle=f.token, name=name, parent_body=b.stable_id or b.name)

    # Corpo.
    if "body" in descriptor:
        b = _find_body(state, descriptor["body"])
        return EntityRef(kind="body", handle=b.stable_id or b.name or "?", name=b.name)

    raise EntityRefError(f"descritor não reconhecido: {descriptor!r}")
