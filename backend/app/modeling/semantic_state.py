"""F9 Pilar 2 — estado semântico DERIVADO por medição (ADR-024).

Enriquece o ``ModelState`` com a SEMÂNTICA que o LLM ecoa entre steps (em vez de
chutar coordenada): papéis de face (``roles``), adjacência entre corpos
(``touches``) e rótulo de corpo (``body_label``). Tudo derivado MEDINDO o B-Rep —
reusa o ranking de role do ``entity_ref`` e a medição de folga/overlap do
``geometry_verifier``. **Best-effort**: o que não dá p/ afirmar fica vazio/None
(NUNCA rotula errado). Camada pura (sem ``adsk``), 100% testável em mock.
"""

from __future__ import annotations

from app.core.contracts import BodyAdjacency, ModelState, ModelStateBody, ModelStateFace

__all__ = ["derive_semantic_state"]

# Papéis de face derivados por POSIÇÃO/área (robustos a normal mal-sinada). O
# ``open_boundary`` é tratado à parte (só faces de fato marcadas, sem o fallback
# do resolver que rotularia o topo comum como abertura).
_ROLE_CANDIDATES = ("top_planar", "bottom_planar", "largest_planar")
_CONTACT_TOL = 0.2  # mm — |folga| abaixo disto = contato
_INTERFERENCE_EPS = 1e-3  # mm³ — penetração acima disto = interferência real
# Fração do volume da MENOR bbox coberta pela interseção a partir da qual a
# sobreposição é CONTENÇÃO esperada (pino no furo, peça no bolso) — espelha o
# ``geometry_verifier._CONTAIN_KINDS``, onde o overlap é o resultado CORRETO do
# encaixe e nunca deve ser reportado como "interfere com" (senão o planner tenta
# "consertar" o que está certo). Interferência parcial real cobre bem menos que
# isso (ex.: 50% no caso típico de penetração acidental).
_CONTAINMENT_BBOX_RATIO = 0.8


def derive_semantic_state(state: ModelState | None) -> ModelState | None:
    """Popula ``roles``/``touches``/``body_label`` no ``state`` (mutação in-place)
    e o devolve. ``None``/sem corpos ⇒ no-op."""

    if state is None or not state.bodies:
        return state
    _derive_roles(state)
    _derive_touches(state)
    _derive_labels(state)
    return state


def _add_role(face: ModelStateFace, role: str) -> None:
    if role not in face.roles:
        face.roles = [*face.roles, role]


def _derive_roles(state: ModelState) -> None:
    from app.modeling.entity_ref import EntityRefError, _resolve_face_by_role

    for b in state.bodies:
        cands = [(b, f) for f in b.faces if f.token]
        if not cands:
            continue
        for role in _ROLE_CANDIDATES:
            try:
                _, face = _resolve_face_by_role(role, cands)
            except EntityRefError:
                continue  # ambíguo/ausente → não marca (NUNCA chuta)
            _add_role(face, role)
        # open_boundary: SÓ as faces de fato marcadas pelo script (medição do
        # B-Rep). Não usar o fallback do resolver — ele rotularia o topo comum
        # como abertura, um falso papel.
        for _, f in cands:
            if f.is_open_boundary:
                _add_role(f, "open_boundary")


def _perp_overlap_area(a: ModelStateBody, b: ModelStateBody, axis: int) -> float:
    """Sobreposição das bboxes nos DOIS eixos perpendiculares ao do mate. >0 =
    os corpos compartilham área de contato (não só estão alinhados e à parte)."""

    area = 1.0
    for i in range(3):
        if i == axis:
            continue
        lo = max(a.bbox_min_mm[i], b.bbox_min_mm[i])
        hi = min(a.bbox_max_mm[i], b.bbox_max_mm[i])
        if hi - lo <= 0:
            return 0.0
        area *= hi - lo
    return area


def _bbox_volume(b: ModelStateBody) -> float:
    vol = 1.0
    for i in range(3):
        d = b.bbox_max_mm[i] - b.bbox_min_mm[i]
        if d <= 0:
            return 0.0
        vol *= d
    return vol


def _derive_touches(state: ModelState) -> None:
    from app.modeling.geometry_verifier import (
        _bbox_overlap_volume,
        _gap_along,
        _mate_axis,
    )

    bodies = [b for b in state.bodies if b.bbox_min_mm and b.bbox_max_mm]
    for b in bodies:
        adj: list[BodyAdjacency] = []
        for o in bodies:
            if o is b:
                continue
            axis = _mate_axis(b, o)
            gap = _gap_along(b, o, axis)
            # Só conta como adjacência se compartilham área no plano perpendicular
            # (exclui corpos lado-a-lado, alinhados mas sem contato real).
            if _perp_overlap_area(b, o, axis) <= 0:
                continue
            overlap = _bbox_overlap_volume(b, o)
            # CONTENÇÃO esperada (pino no furo): a interseção cobre ≥80% da menor
            # bbox ⇒ um corpo está essencialmente DENTRO do outro — encaixe, não
            # colisão. O render do <model-state> (model_state.py, fora deste
            # grupo) só conhece interference=True→"interfere com" / False→
            # "encosta em"; reportamos contenção como interference=False (contato
            # esperado), o que o render já apresenta corretamente como "encosta
            # em" — sem quebrar o contrato nem convidar o planner a "consertar".
            contained = False
            if overlap > _INTERFERENCE_EPS:
                smaller = min(_bbox_volume(b), _bbox_volume(o))
                contained = smaller > 0 and overlap >= _CONTAINMENT_BBOX_RATIO * smaller
            interfering = overlap > _INTERFERENCE_EPS and gap < -_CONTACT_TOL and not contained
            if abs(gap) <= _CONTACT_TOL or interfering or contained:
                adj.append(
                    BodyAdjacency(
                        other=o.name or o.stable_id or "?",
                        axis="xyz"[axis],
                        gap_mm=round(gap, 4),
                        interference=interfering,
                    )
                )
        b.touches = adj


def _min_dim(b: ModelStateBody) -> float:
    return min(b.bbox_max_mm[i] - b.bbox_min_mm[i] for i in range(3))


def _derive_labels(state: ModelState) -> None:
    """Rótulo de corpo best-effort. ``container`` = tem face de abertura medida;
    ``lid`` = NÃO-container que encosta num container e é o ÚNICO mais fino. Sem
    container detectado, ou empate de espessura ⇒ nada (NUNCA chuta)."""

    containers = [b for b in state.bodies if any(f.is_open_boundary for f in b.faces)]
    for c in containers:
        c.body_label = "container"
    if not containers:
        return  # sem âncora confiável → não arrisca rotular um "lid"

    container_names = {c.name for c in containers if c.name}
    non_containers = [
        b for b in state.bodies if b not in containers and b.bbox_min_mm and b.bbox_max_mm
    ]
    # Candidato a lid: ENCOSTA de verdade no container (folga ~0). Contenção
    # (interference=False mas folga bem negativa — pino dentro da caixa) não
    # qualifica: um corpo embutido não é tampa.
    touching = [
        b
        for b in non_containers
        if any(
            t.other in container_names
            and not t.interference
            and t.gap_mm is not None
            and abs(t.gap_mm) <= _CONTACT_TOL
            for t in b.touches
        )
    ]
    if not touching:
        return
    thinnest = min(touching, key=_min_dim)
    floor = _min_dim(thinnest)
    ties = [b for b in touching if abs(_min_dim(b) - floor) < 1e-6]
    if len(ties) == 1:  # espessura única → seguro rotular
        thinnest.body_label = "lid"
