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

from app.core.contracts import (
    ModelingPlanStep,
    ModelingStepStatus,
    ModelState,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.spatial_ref import (
    ALIGN_GAP_SIDE_UNDETERMINABLE,
    BBOX_NOT_AXIS_ALIGNED,
    RELATIVE_COORD_FORBIDDEN,
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
    "needs_resolution",
    "resolve_inline_refs",
    "expand_placement",
    "resolve_step",
    "materialize_steps",
    "enforce_relative_coord",
]

# F9 Pilar 3 (Gate B) — tolerâncias do enforcement de coordenada relativa. No
# molde das tolerâncias-constante do ``geometry_verifier`` (_CONTACT_TOL etc.),
# não em ``config.py`` (evita bloat; estes são limiares de medição, não política).
_RELATIVE_OVERLAP_TOL_MM3 = 1.0  # overlap de bbox acima disto = interferência real
_RELATIVE_FAR_TOL_MM = 5.0  # folga ao corpo mais próximo acima disto = "flutuando longe"

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


def _has_leftover_ref(value: Any) -> bool:
    """Sobrou alguma ref espacial (objeto ou @-string) num valor já resolvido?
    Vasculha listas/dicts aninhados."""

    if is_spatial_ref(value) or _has_at(value):
        return True
    if isinstance(value, dict):
        return any(_has_leftover_ref(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_leftover_ref(v) for v in value)
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
    # Ref espacial sobrando em campo FORA do whitelist (ex.: corner1_mm,
    # points_mm) seria despachada CRUA ao Fusion → mis-place. Falha tipada em
    # vez de chute (invariante "NUNCA chuta").
    for key, value in out.items():
        if _has_leftover_ref(value):
            raise SpatialRefError(
                f"referência espacial em campo não suportado: {key!r} "
                "(o resolver só cobre campos de ponto/eixo/escalar conhecidos)"
            )
    for a in actions:
        logger.info("spatial_resolver %s [%s] %s", a.kind, a.field, a.detail)
    return out, actions


# --------------------------------------------------------------------------- #
# 2) Expansão das tools declarativas F7                                       #
# --------------------------------------------------------------------------- #
def _face_token_of(ref: Any, state: ModelState | None = None) -> str | None:
    # Token VAZIO ('') é tratado como ausência: senão passaria o guard
    # `is None` do expander e o handler cairia no "último corpo" (mis-mate).
    if isinstance(ref, dict):
        face = ref.get("face")
        # 'face' como STRING (ou 'token') = token direto; 'face' como DICT =
        # predicado semântico (resolvido abaixo, NÃO é token).
        tok = ref.get("token") or (face if isinstance(face, str) else None)
        if tok:
            return tok
        # F8: descritor SEMÂNTICO {body, role}/{body, face:{...}} → resolve por
        # role/predicado medindo o ModelState (o LLM não copia token opaco).
        # entity_ref levanta erro TIPADO (subclasse de SpatialRefError) se
        # ambíguo/inexistente — propaga, nunca chuta.
        if state is not None and ("role" in ref or isinstance(face, dict)):
            from app.modeling.entity_ref import resolve_entity

            handle = resolve_entity(ref, state)
            return handle.handle if handle.kind == "face" else None
        return None
    if isinstance(ref, str) and ref.strip().startswith("@"):
        try:
            kind, id_, _ = parse_at_expr(ref)
        except SpatialRefError:
            return None
        if kind in ("token", "face"):
            return id_ or None
    return None


def _resolve_face(ref: Any, state: ModelState | None) -> ModelStateFace | None:
    """Resolve um descritor de face (role/predicado/@token/{face:tok}) para a
    ``ModelStateFace`` REAL (com center_mm + normal) — base do placement estático
    determinístico (medir a face, não copiar token)."""

    token = _face_token_of(ref, state)
    if token is None or state is None:
        return None
    for b in state.bodies:
        for f in b.faces:
            if f.token == token:
                return f
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


def _shifted_body(body: Any, translation_mm: list[float]) -> Any:
    """Copia o corpo com a bbox transladada — o efeito de ``move_body`` SEM
    executar. Usado pelo Gate B p/ medir a posição RESULTANTE antes do dispatch."""

    bmin = [round(body.bbox_min_mm[i] + translation_mm[i], 4) for i in range(3)]
    bmax = [round(body.bbox_max_mm[i] + translation_mm[i], 4) for i in range(3)]
    return body.model_copy(update={"bbox_min_mm": bmin, "bbox_max_mm": bmax})


def enforce_relative_coord(
    state: ModelState | None,
    tool_name: str,
    args: dict[str, Any],
    *,
    overlap_tol_mm3: float = _RELATIVE_OVERLAP_TOL_MM3,
    far_tol_mm: float = _RELATIVE_FAR_TOL_MM,
) -> None:
    """Gate B (F9 Pilar 3): recusa coordenada ABSOLUTA chutada num ``move_body``.

    Mede a posição RESULTANTE do corpo (bbox transladada pela ``translation_mm``,
    sem executar) e, se ela **sobrepõe** outro corpo OU fica **longe** de todos
    (os dois bugs reais: tampa sobreposta / tampa a 80 mm), levanta
    ``SpatialRefError(code=RELATIVE_COORD_FORBIDDEN)`` instruindo a usar
    ``place_body`` declarativo (o backend mede as faces e encaixa com folga 0).

    **INVARIANTE: só RECUSA** — nunca adivinha a posição certa. ``state`` None /
    < 2 corpos / corpo-alvo ausente / bbox faltando ⇒ **no-op** (sem read-back não
    há veredito; não inventa). Escopo v1: ``move_body`` (o vetor de chute
    documentado); ``add_box`` fica de follow-up conservador.

    Limitação conhecida (aceita, flag opt-in): um encaixe por contenção feito por
    ``move_body`` cru (pino no furo → overlap esperado) seria recusado — sob a
    flag ON o caminho correto é declarativo (``align_axis``/``relate_bodies``).
    """

    if tool_name != "fusion.move_body":
        return
    if state is None or len(state.bodies) < 2:
        return
    ref = args.get("body_ref") or args.get("body")
    translation = args.get("translation_mm")
    if not ref or not isinstance(translation, (list, tuple)) or len(translation) < 3:
        return

    from app.modeling.geometry_verifier import (
        _bbox_overlap_volume,
        _find_body,
        _gap_along,
        _mate_axis,
    )

    moving = _find_body(state, str(ref))
    if moving is None or not (moving.bbox_min_mm and moving.bbox_max_mm):
        return
    try:
        deltas = [float(t) for t in translation[:3]]
    except (TypeError, ValueError):
        # Componente declarativo (``@body(...).bbox...``/objeto-ref) na
        # translação: este é exatamente o caminho que o Gate B quer INCENTIVAR
        # — a resolução inline (downstream) mede e materializa o delta. Sem
        # este guard, o ``float()`` estourava ValueError crua e derrubava o
        # execute_plan inteiro (ADR-024: erro tipado, nunca exceção crua).
        return
    moved = _shifted_body(moving, deltas)
    others = [b for b in state.bodies if b is not moving and b.bbox_min_mm and b.bbox_max_mm]
    if not others:
        return

    # Sobreposição: a posição resultante penetra outro corpo → sempre errado.
    for other in others:
        if _bbox_overlap_volume(moved, other) > overlap_tol_mm3:
            raise SpatialRefError(
                f"move_body posiciona '{ref}' SOBREPONDO o corpo '{other.name}' "
                "(coordenada absoluta chutada). Use place_body declarativo: o "
                "backend mede as faces e encaixa com folga 0, sem coordenada.",
                code=RELATIVE_COORD_FORBIDDEN,
            )

    # Longe: o corpo móvel fica afastado de TODOS (não encaixa em nada). Mede a
    # folga no eixo de maior separação de cada par; recusa se o vizinho mais
    # próximo está além da tolerância (o caso "tampa a 80 mm").
    nearest = min(abs(_gap_along(moved, o, _mate_axis(moved, o))) for o in others)
    if nearest > far_tol_mm:
        raise SpatialRefError(
            f"move_body deixa '{ref}' a {nearest:.1f} mm do corpo mais próximo "
            "(coordenada absoluta chutada — não encaixa em nada). Use place_body "
            "declarativo p/ medir as faces e encostar.",
            code=RELATIVE_COORD_FORBIDDEN,
        )


_AXIS_TO_INDEX = {"x": 0, "y": 1, "z": 2}
_PLACE_ALIGN_MODES = frozenset({"center", "coplanar", "gap", "edge", "corner"})
# Abaixo deste delta (mm) o corpo JÁ está na posição calculada → placement vira
# no-op (mover por ~0 faz o adapter rejeitar com invalid_dimensions; comum ao
# re-aplicar um place_body numa EDIÇÃO de modelo já montado).
_PLACE_NOOP_TOL = 1e-3


def _mate_axis_index(target_face: ModelStateFace, ac: list[float], tc: list[float]) -> int:
    """Eixo do mate: a normal CARDINAL da face-alvo se houver; senão o eixo de
    maior separação entre os centros (fallback robusto p/ face não-planar)."""

    na = target_face.normal_axis
    if isinstance(na, str):
        letter = na.strip().lower().lstrip("+-")
        if letter in _AXIS_TO_INDEX:
            return _AXIS_TO_INDEX[letter]
    return max(range(3), key=lambda i: abs(tc[i] - ac[i]))


def _normal_sign_along(face: Any, axis: str) -> int:
    """+1/-1 se a normal OUTWARD da face aponta no sentido +/-axis; 0 se não-cardinal."""

    na = ((getattr(face, "normal_axis", None) or "") if face is not None else "").strip().lower()
    if na in ("+" + axis, axis):
        return 1
    if na == "-" + axis:
        return -1
    return 0


def _gap_direction(
    na: int, anchor_face: Any, target_face: Any, ac: list[float], tc: list[float]
) -> int:
    """Sentido (+1/-1) em que a folga do align='gap' abre. A folga abre p/ o lado
    de FORA do alvo — a normal OUTWARD da face de DESTINO (gate teste 2: tampa
    criada ABAIXO do topo deve subir, não enfiar na caixa). Cascata de fallback:
    normal do alvo → normal INWARD da âncora (-outward) → posição pré-move (frágil)
    → erro tipado. NUNCA chuta o lado."""

    axis = "xyz"[na]
    s = _normal_sign_along(target_face, axis)
    if s:
        return s
    s = _normal_sign_along(anchor_face, axis)
    if s:
        return -s  # normal da âncora é OUTWARD do corpo móvel; o volume vai p/ o INWARD
    if abs(ac[na] - tc[na]) > 1e-6:
        return 1 if ac[na] > tc[na] else -1
    raise SpatialRefError(
        "place_body align='gap': faces sem normal cardinal e coincidentes no eixo do "
        "mate — lado da folga indeterminável. Use align='coplanar' ou reposicione antes.",
        code=ALIGN_GAP_SIDE_UNDETERMINABLE,
    )


def _is_axis_aligned(body: Any) -> bool:
    """Heurística p/ edge/corner: o corpo está alinhado aos eixos do mundo? A
    evidência vem das normais das faces planares (cardinais quando alinhado). Sem
    NENHUMA planar cardinal o corpo parece rotacionado → a AABB não representa as
    bordas reais e o caller RECUSA (NUNCA chuta uma borda torta). Sem faces
    planares (cilindro/esfera) não há como afirmar rotação → assume alinhado."""

    planar = [f for f in (body.faces or []) if f.type == "planar"]
    if not planar:
        return True
    return any(
        isinstance(f.normal_axis, str)
        and f.normal_axis.strip().lower().lstrip("+-") in _AXIS_TO_INDEX
        for f in planar
    )


def _owner_body(state: ModelState | None, face_token: str | None) -> Any | None:
    if not face_token:
        return None
    for b in state.bodies if state else []:
        if any(f.token == face_token for f in b.faces):
            return b
    return None


def _compute_place_delta(
    align: str,
    ac: list[float],
    tc: list[float],
    na: int,
    *,
    gap_mm: float = 0.0,
    moving: Any | None = None,
    reference: Any | None = None,
    anchor_face: Any | None = None,
    target_face: Any | None = None,
) -> list[float]:
    """Calcula o delta de translação do place_body por MODO de alinhamento (F9
    Pilar 1). ``center`` reproduz o snap concêntrico atual bit-a-bit; os demais
    são direcionais. Erros tipados (NUNCA chuta) p/ gap-sem-lado e AABB rotacionada."""

    if align == "center":
        # Snap CONCÊNTRICO (comportamento histórico): o centro da face ANCHOR mapeia
        # no centro da face TARGET nos 3 eixos → centra E encosta (folga 0).
        return [round(tc[i] - ac[i], 4) for i in range(3)]

    if align == "coplanar":
        # Só o eixo da normal: as faces ficam coplanares (folga 0) SEM recentralizar
        # — respeita o offset em-plano que o planner deu de propósito.
        delta = [0.0, 0.0, 0.0]
        delta[na] = round(tc[na] - ac[na], 4)
        return delta

    if align == "gap":
        # CONCÊNTRICO no plano (como center) + folga no eixo da normal, no lado de
        # FORA do alvo. "Tampa 2 mm acima" = CENTRADA e 2 mm acima (gate teste 2: o
        # gap antes herdava o "não recentralizar" do coplanar e deixava a tampa
        # deslocada). O sentido da folga vem da normal OUTWARD do destino, não da
        # posição pré-move; sem sinal derivável → erro tipado (NUNCA chuta o lado).
        delta = [round(tc[i] - ac[i], 4) for i in range(3)]
        base = tc[na] - ac[na]
        if gap_mm:
            base += gap_mm * _gap_direction(na, anchor_face, target_face, ac, tc)
        delta[na] = round(base, 4)
        return delta

    if align in ("edge", "corner"):
        if (
            moving is None
            or reference is None
            or not (moving.bbox_min_mm and moving.bbox_max_mm)
            or not (reference.bbox_min_mm and reference.bbox_max_mm)
        ):
            raise SpatialRefError(
                f"place_body align='{align}': exige a bbox dos dois corpos — rode "
                "query_geometry (a borda/canto vem da caixa-limite medida)."
            )
        if not (_is_axis_aligned(moving) and _is_axis_aligned(reference)):
            raise SpatialRefError(
                f"place_body align='{align}' usa a caixa-limite (AABB), que só representa "
                "as bordas reais de corpos alinhados aos eixos; este corpo parece "
                "rotacionado. Use align='center'/'coplanar' (medem faces).",
                code=BBOX_NOT_AXIS_ALIGNED,
            )
        # Eixo do mate: flush (faces encostam). Eixos no plano: alinha o bbox-min do
        # MOVING ao do REFERENCE — corner = ambos os eixos; edge = só o de MAIOR
        # extensão do reference (o outro centra, como center).
        in_plane = [i for i in range(3) if i != na]
        delta = [0.0, 0.0, 0.0]
        delta[na] = round(tc[na] - ac[na], 4)
        dom = max(in_plane, key=lambda i: reference.bbox_max_mm[i] - reference.bbox_min_mm[i])
        for i in in_plane:
            if align == "corner" or i == dom:
                delta[i] = round(reference.bbox_min_mm[i] - moving.bbox_min_mm[i], 4)
            else:
                delta[i] = round(tc[i] - ac[i], 4)
        return delta

    raise SpatialRefError(
        f"place_body: align='{align}' desconhecido. Use center | coplanar | gap | edge | corner."
    )


def _expand_place_body(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    """Placement estático DETERMINÍSTICO: o LLM declara a relação (face do corpo
    encosta na face de destino) + o MODO de alinhamento (``align``); o backend MEDE
    as duas faces no read-back e calcula a translação EXATA → emite um ``move_body``
    com o delta medido. Folga = 0 por construção (ou ``gap_mm`` no modo gap), SEM o
    LLM calcular coordenada (a fonte da folga de 1,5 mm). Corpos seguem SEPARADOS
    (sem componente/junta — a junta é papel do align_axis, p/ cinemática).

    ``align`` (F9 Pilar 1, atrás de ``modeling_align_modes_enabled``): center
    (default, snap concêntrico) | coplanar | gap | edge | corner. Flag OFF ⇒ align
    IGNORADO, sempre center (regressão bit-a-bit)."""

    from app.core.config import settings

    body = args.get("body") or args.get("body_ref")
    if not body:
        raise SpatialRefError("place_body exige 'body'")
    moving = find_body(state, body)  # valida existência (erro tipado se não houver)

    mate = str(args.get("mate") or "flush").lower()
    if mate != "flush":
        raise SpatialRefError(
            f"place_body: mate='{mate}' ainda não suportado; use 'flush' (contato) ou "
            "align_axis para coaxialidade."
        )
    # offset/clearance: legado (o eixo/sinal eram fáceis de errar). A folga direcional
    # agora é o modo align='gap' com gap_mm (lado medido). Mantém a recusa do legado.
    for opt in ("offset_mm", "clearance_mm"):
        if args.get(opt) not in (None, 0, 0.0):
            raise SpatialRefError(
                f"place_body: '{opt}' ainda não suportado (use align='gap' + gap_mm)."
            )

    # F9 Pilar 1: modo de alinhamento (flag OFF ⇒ sempre center = regressão).
    align = (
        str(args.get("align") or "center").lower()
        if settings.modeling_align_modes_enabled
        else "center"
    )
    if align not in _PLACE_ALIGN_MODES:
        raise SpatialRefError(
            f"place_body: align='{align}' desconhecido. Use "
            "center | coplanar | gap | edge | corner."
        )

    anchor_face = _resolve_face(args.get("anchor"), state)  # face do MOVING (mede)
    target_face = _resolve_face(args.get("target"), state)  # face de DESTINO (mede)
    if anchor_face is None or target_face is None:
        raise SpatialRefError(
            "place_body: 'anchor' (face no corpo) e 'target' (face de destino) precisam "
            "referenciar FACES — role ({body, role:'bottom_planar'}), @token('<face>') ou "
            "{face:'<token>'}. O placement mede as faces, não usa coordenada."
        )
    ac, tc = anchor_face.center_mm, target_face.center_mm
    if not ac or not tc or len(ac) < 3 or len(tc) < 3:
        raise SpatialRefError(
            "place_body: faces sem center_mm medido — rode query_geometry (o delta "
            "determinístico vem da medição do centro das faces)."
        )

    na = _mate_axis_index(target_face, ac, tc)
    reference = _owner_body(state, target_face.token) if align in ("edge", "corner") else None
    gap_mm = _coerce_float(args.get("gap_mm") or args.get("gap"))
    delta = _compute_place_delta(
        align,
        ac,
        tc,
        na,
        gap_mm=gap_mm,
        moving=moving,
        reference=reference,
        anchor_face=anchor_face,
        target_face=target_face,
    )
    if all(abs(d) < _PLACE_NOOP_TOL for d in delta):
        # Corpo já está na posição calculada (Δ≈0) — NÃO emite move_body (o adapter
        # rejeita translação zero). Placement vira no-op de sucesso. Comum ao editar
        # um modelo já montado (gate: place_body num corpo já posicionado).
        logger.debug("place_body %s: Δ≈0, corpo já posicionado — no-op", body)
        return []
    return [
        ConcreteStep(
            "fusion.move_body",
            {"body_ref": body, "translation_mm": delta},
            f"Encaixa {body} (flush '{align}', Δ={delta})",
        )
    ]


def _coerce_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _expand_align_axis(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    body = args.get("body") or args.get("body_ref")
    if not body:
        raise SpatialRefError("align_axis exige 'body'")
    find_body(state, body)
    target_face = _face_token_of(args.get("target"), state)
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
        if total > length:
            # Não cabe: erro tipado em vez de clamp silencioso (nós colados/
            # sobrepostos seriam um "chute" geométrico).
            raise SpatialRefError(
                f"spacing_mm não cabe na aresta: {count} nós exigem {total:.1f} mm, "
                f"aresta tem {length:.1f} mm. Reduza count/spacing_mm ou use fit=True."
            )
        start = (length - total) / 2.0  # centra a fileira na aresta
        return [(start + i * step) / length for i in range(count)]
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


# F7/F8 estendido: aresta por ROLE (em vez de token chutado). Cada palavra-chave
# soma um sentido; o role é a aresta reta cujo PONTO-MÉDIO é mais extremo nessa
# direção (rear_top = +y+z = a aresta horizontal do fundo-topo). Espelha o
# entity_ref de faces — o LLM declara a intenção, o backend MEDE.
_EDGE_DIR: dict[str, tuple[float, float, float]] = {
    "rear": (0.0, 1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "front": (0.0, -1.0, 0.0),
    "top": (0.0, 0.0, 1.0),
    "bottom": (0.0, 0.0, -1.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}
_EDGE_POS_TOL = 0.1  # mm — margem p/ separar a aresta extrema da 2ª (senão ambíguo)
_EDGE_COLLINEAR_TOL = 0.1  # mm — desvio perpendicular p/ tratar fragmentos como a MESMA reta


def _merge_collinear_edges(
    tied: list[ModelStateEdge], body: Any, role: str
) -> str | None:
    """F7: fragmentos COLINEARES (mesma reta) de uma aresta partida por features
    fundidas ao longo dela — ex.: knuckles soldados na aresta da dobradiça — NÃO
    são ambíguos: são a MESMA aresta conceitual fragmentada. Funde-os no span
    completo (min..max ao longo da direção comum), injeta um edge sintético no
    ``body`` (o ModelState aqui é um read-back descartável por-passo) e devolve o
    token. ``None`` se as candidatas NÃO forem colineares — aí o chamador ergue
    erro tipado (arestas geometricamente distintas, ambiguidade real). Mantém o
    invariante: NUNCA chuta — só funde o que é, medidamente, a mesma reta."""

    base = tied[0]
    p0 = [float(c) for c in base.start_point_mm]  # type: ignore[union-attr]
    d = [float(base.end_point_mm[i]) - p0[i] for i in range(3)]  # type: ignore[index]
    dlen = sum(c * c for c in d) ** 0.5
    if dlen <= 1e-9:
        return None
    d = [c / dlen for c in d]  # unitário da reta de referência

    pts: list[list[float]] = []
    for e in tied:
        if not e.start_point_mm or not e.end_point_mm:
            return None
        pts.append([float(c) for c in e.start_point_mm])
        pts.append([float(c) for c in e.end_point_mm])

    # Colinearidade: cada endpoint a ≤ tol da reta (p0, d) na perpendicular.
    for pt in pts:
        w = [pt[i] - p0[i] for i in range(3)]
        t = sum(w[i] * d[i] for i in range(3))
        perp = sum((pt[i] - (p0[i] + t * d[i])) ** 2 for i in range(3)) ** 0.5
        if perp > _EDGE_COLLINEAR_TOL:
            return None  # não-colinear → ambiguidade real

    # Span: projeta todos os endpoints em d e pega min..max.
    ts = [sum((pt[i] - p0[i]) * d[i] for i in range(3)) for pt in pts]
    t_lo, t_hi = min(ts), max(ts)
    if (t_hi - t_lo) <= 1e-6:
        return None
    start = [round(p0[i] + t_lo * d[i], 4) for i in range(3)]
    end = [round(p0[i] + t_hi * d[i], 4) for i in range(3)]
    token = f"__merged__{role}__{body.name or 'body'}"
    body.edges.append(
        ModelStateEdge(
            token=token,
            is_circular=False,
            start_point_mm=start,
            end_point_mm=end,
            direction=[round(c, 6) for c in d],
            length_mm=round(t_hi - t_lo, 4),
        )
    )
    return token


def _resolve_edge_by_role(role: str, body_name: Any, state: ModelState | None) -> str:
    """Resolve um role de aresta ({body, role:'rear_top'|'longest'|...}) para o
    edge_token REAL, MEDINDO o ModelState. Ambíguo/sem aresta → erro tipado
    (NUNCA chuta) — espelha ``entity_ref._resolve_face_by_role`` para arestas."""

    body = find_body(state, body_name)  # erro tipado se o corpo não existir
    straight = [
        e
        for e in body.edges
        if e.token and not e.is_circular and e.start_point_mm and e.end_point_mm
    ]
    if not straight:
        raise SpatialRefError(
            f"distribute_along: corpo '{body_name}' sem aresta reta medida — rode "
            "query_geometry (o role da aresta vem da medição)."
        )
    role = role.strip().lower()
    if role in ("longest", "longer", "maior", "mais_longa"):
        return max(straight, key=lambda e: e.length_mm or 0.0).token  # type: ignore[return-value]

    direction = [0.0, 0.0, 0.0]
    if not any(word in role for word in _EDGE_DIR):
        raise SpatialRefError(
            f"distribute_along: role de aresta desconhecido: {role!r} "
            "(use 'longest' ou combinação rear/front + top/bottom + left/right)."
        )
    for word, vec in _EDGE_DIR.items():
        if word in role:
            direction = [direction[i] + vec[i] for i in range(3)]

    def _score(e: Any) -> float:
        mid = [(e.start_point_mm[i] + e.end_point_mm[i]) / 2.0 for i in range(3)]
        return sum(mid[i] * direction[i] for i in range(3))

    ranked = sorted(straight, key=_score, reverse=True)
    top = ranked[0]
    tied = [e for e in ranked if abs(_score(e) - _score(top)) <= _EDGE_POS_TOL]
    if len(tied) > 1:
        # Empate no extremo: fragmentos colineares (aresta partida por features
        # fundidas ao longo dela — ex.: knuckles na dobradiça) são a MESMA reta e
        # se fundem no span completo; só erra quando são NÃO-colineares.
        merged = _merge_collinear_edges(tied, body, role)
        if merged is not None:
            return merged
        raise SpatialRefError(
            f"distribute_along: role '{role}' ambíguo em '{body_name}' (≥2 arestas "
            "NÃO-colineares no extremo) — qualifique melhor o role."
        )
    return top.token  # type: ignore[return-value]


def _resolve_edge_token(edge_ref: Any, state: ModelState | None) -> str:
    """Normaliza o campo ``edge`` do distribute_along para um edge_token REAL:
    descritor ``{body, role}`` → mede; token real → valida e passa; token
    chutado/inexistente → erro tipado pedindo o descritor (NUNCA chuta)."""

    if isinstance(edge_ref, dict) and edge_ref.get("role") and edge_ref.get("body"):
        return _resolve_edge_by_role(str(edge_ref["role"]), edge_ref["body"], state)
    if isinstance(edge_ref, str) and edge_ref.strip():
        find_edge(state, edge_ref)  # valida; SpatialRefError tipado se não existir
        return edge_ref
    raise SpatialRefError(
        "distribute_along: 'edge' precisa ser um edge_token real OU um descritor "
        "{body, role:'rear_top'} (o backend mede a aresta — não invente token)."
    )


def _expand_distribute_along(args: dict[str, Any], state: ModelState | None) -> list[ConcreteStep]:
    edge_tok = _resolve_edge_token(args.get("edge"), state)
    raw_count = args.get("count")
    if raw_count is None:
        raise SpatialRefError("distribute_along exige 'edge' e 'count' >= 1")
    # count/spacing_mm podem vir como @-ref ou número — resolve_scalar (no-op em
    # número) garante erro TIPADO em vez de ValueError cru que escaparia do
    # execute_plan inteiro.
    try:
        count = int(resolve_scalar(raw_count, state))
    except SpatialRefError:
        raise
    except (TypeError, ValueError):
        raise SpatialRefError(f"distribute_along: 'count' inválido: {raw_count!r}")
    if count < 1:
        raise SpatialRefError("distribute_along: 'count' precisa ser >= 1")
    edge = find_edge(state, edge_tok)
    proto = dict(args.get("prototype") or {})
    alternate = args.get("alternate")
    axis_vec = list(resolve_axis({"edge": edge_tok}, state))  # eixo dos nós = direção da aresta
    spacing = args.get("spacing_mm")
    spacing_val = resolve_scalar(spacing, state) if spacing is not None else None
    fractions = _distribute_fractions(count, edge.length_mm, spacing_val, args.get("fit"))

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

    # Furo do pino (declarativo): canal COAXIAL atravessando os nós ao longo da
    # MESMA aresta (eixo da dobradiça). Tira o furo das mãos do LLM — que senão
    # usa fusion.hole (perfura ⟂ à face, não faz furo axial) e/ou chuta a
    # coordenada no frame errado. Cilindro de furo coaxial à aresta, CORTADO de
    # cada corpo-pai (1 por grupo: o cut consome a ferramenta) DEPOIS do join, p/
    # o canal contínuo do pino. Sem 'alternate' não há corpo-pai → erro tipado.
    bore_d = args.get("bore_diameter_mm")
    if bore_d is not None:
        if not groups:
            raise SpatialRefError(
                "distribute_along: 'bore_diameter_mm' exige 'alternate' (o furo é "
                "cortado dos corpos-pai que recebem os nós)."
            )
        bore_d_val = resolve_scalar(bore_d, state)
        # Margem = altura do nó, p/ o furo atravessar mesmo nós nas pontas.
        proto_h = _coerce_float(proto.get("height_mm") or 0.0)
        margin = proto_h if proto_h > 0 else 1.0
        start = [float(c) for c in (edge.start_point_mm or [0.0, 0.0, 0.0])]
        ax = [float(c) for c in axis_vec]
        origin = [round(start[i] - margin * ax[i], 4) for i in range(3)]
        height = round((edge.length_mm or 0.0) + 2 * margin, 4)
        for idx, parent in enumerate(groups):
            bore_name = f"{base_name}_Bore_{idx + 1}"
            steps.append(
                _prototype_step(
                    {
                        "primitive": "cylinder",
                        "diameter_mm": bore_d_val,
                        "height_mm": height,
                        "name": bore_name,
                    },
                    origin,
                    bore_name,
                    ax,
                )
            )
            steps.append(
                ConcreteStep(
                    "fusion.combine_bodies",
                    {"target_ref": parent, "tool_refs": [bore_name], "operation": "cut"},
                    f"Abre o canal do pino (Ø{bore_d_val}) em {parent}",
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
def needs_resolution(tool_name: str, args: Any, *, read_only: bool = False) -> bool:
    """``True`` se o passo precisa do resolver F7: tool declarativa OU args com
    referência espacial. ``read_only`` (probe ``query_geometry`` etc.) → ``False``
    (não dispara probe nem recursão — o executor pula a resolução)."""

    if read_only:
        return False
    if tool_name in F7_PLACEMENT_TOOLS:
        return True
    if not isinstance(args, dict):
        return False
    return any(is_spatial_ref(v) or _has_at(v) for v in args.values())


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


def materialize_steps(
    original: ModelingPlanStep, concrete_steps: list[ConcreteStep]
) -> list[ModelingPlanStep]:
    """Materializa ``ConcreteStep`` → ``ModelingPlanStep`` concretos, herdando
    seq/software/risk do passo declarativo (já aprovado; os concretos auto-
    executam na sequência). IDs novos por passo (não colidem em tool_calls)."""

    out: list[ModelingPlanStep] = []
    for c in concrete_steps:
        out.append(
            ModelingPlanStep(
                seq=original.seq,
                title=c.title or original.title,
                software=original.software,
                tool_name=c.tool_name,
                risk_level=original.risk_level,
                approval_required=False,
                status=ModelingStepStatus.approved,
                input_json=dict(c.input_json),
            )
        )
    return out
