"""F7 — Referência espacial declarativa (resolver puro sobre ``ModelState``).

Camada de domínio **pura** (sem ``adsk``): traduz referências DECLARATIVAS à
geometria real — por token estável de face/aresta (F1) ou por corpo + selector
semântico — em **ponto/eixo/escalar** concretos em mm. É o que faz o LLM parar
de chutar coordenada absoluta: ele declara "centro da face X", "20% ao longo da
aresta Y", "bbox.max_z do corpo Placa", e este módulo computa o número a partir
do ``ModelState`` capturado por ``fusion.query_geometry`` (F1 + enriquecimento
F7-P2: bbox absoluto do corpo, pontas/direção de aresta reta).

Duas formas de entrada:

- **objeto**: ``{"face": "<token>", "point": "center", "axis": "normal"}``,
  ``{"edge": "<token>", "point": "along", "fraction": 0.2}``,
  ``{"body": "Placa", "point": "bbox.max_z"}``.
- **@-string** (faz as refs hoje-proibidas FUNCIONAREM em campos existentes):
  ``"@token('<face>').center.z"``, ``"@edge('<e>').along(0.2)"``,
  ``"@body('Placa').bbox.max_z - 20"`` (aritmética por AST restrito, sem
  ``eval``).

Fora da gramática / token inexistente → :class:`SpatialRefError` tipado
(``fusion.spatial_ref_unresolved``), espelhando ``fusion.edge_token_stale``:
**NUNCA** chuta um número.
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

from app.core.contracts import (
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)

__all__ = [
    "SPATIAL_REF_UNRESOLVED",
    "SpatialRefError",
    "is_spatial_ref",
    "parse_at_expr",
    "strip_at_refs",
    "resolve_point",
    "resolve_axis",
    "resolve_scalar",
    "find_body",
    "find_face",
    "find_edge",
]

SPATIAL_REF_UNRESOLVED = "fusion.spatial_ref_unresolved"

Vec3 = tuple[float, float, float]

# Eixos cardinais (e suas variações +/-). Strings cardinais NÃO são refs
# espaciais (não começam com @) — são valores crus aceitos como eixo.
_CARDINAL: dict[str, Vec3] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}
_COMPONENT_INDEX = {"x": 0, "y": 1, "z": 2}
_BBOX_SCALAR = {"min_x", "max_x", "min_y", "max_y", "min_z", "max_z"}

# Uma referência @: @<kind>('<id>')<.selector(.arg)?>* — o id é o token
# estável da face/aresta ou o nome/stable_id do corpo.
_AT_RE = re.compile(
    r"@(?P<kind>token|face|edge|body)\(\s*'(?P<id>[^']*)'\s*\)"
    r"(?P<chain>(?:\.[a-zA-Z_]+(?:\([^)]*\))?)*)"
)
_SEG_RE = re.compile(r"\.([a-zA-Z_]+)(?:\(([^)]*)\))?")


class SpatialRefError(ValueError):
    """Referência espacial fora da gramática ou inexistente no ``ModelState``.

    Carrega ``code`` (default ``fusion.spatial_ref_unresolved``) para o executor
    devolver um erro tipado em vez de chutar — espelha ``fusion.edge_token_stale``.
    """

    def __init__(self, message: str, *, code: str = SPATIAL_REF_UNRESOLVED) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Predicado e parsing                                                          #
# --------------------------------------------------------------------------- #
def is_spatial_ref(value: Any) -> bool:
    """``True`` se ``value`` é uma referência espacial declarativa.

    @-string (começa com ``@``) ou objeto com chave ``face``/``token``/``edge``/
    ``body``. Cardinais (``"+z"``) e números crus NÃO são refs (passam direto).
    """

    if isinstance(value, str):
        return value.strip().startswith("@")
    if isinstance(value, dict):
        return any(k in value for k in ("face", "token", "edge", "body"))
    return False


def parse_at_expr(s: str) -> tuple[str, str, list[Any]]:
    """Parseia UMA referência @ (sem aritmética) em ``(kind, id, segments)``.

    ``segments`` é lista de ``str`` (ex.: ``"center"``, ``"z"``) ou ``(nome,
    float)`` para selectors com argumento (ex.: ``("along", 0.2)``). Levanta
    :class:`SpatialRefError` se não casar exatamente.
    """

    if not isinstance(s, str):
        raise SpatialRefError(f"referência @ precisa ser string, veio {type(s).__name__}")
    m = _AT_RE.fullmatch(s.strip())
    if m is None:
        raise SpatialRefError(f"referência @ malformada: {s!r}")
    return m.group("kind"), m.group("id"), _parse_chain(m.group("chain"))


def strip_at_refs(text: str) -> str:
    """Remove todas as referências @ válidas de ``text`` (substitui por espaço).

    Usado pelo ``plan_sanitizer`` (F6) para não confundir um @-ref VÁLIDO
    (ex.: ``@body('Placa').bbox.max_z``) com uma referência geométrica crua
    PROIBIDA (ex.: ``Placa.bbox.max_z``) — só a forma sem ``@`` deve cair.
    """

    if not isinstance(text, str):
        return text
    return _AT_RE.sub(" ", text)


def _parse_chain(chain: str) -> list[Any]:
    segs: list[Any] = []
    for m in _SEG_RE.finditer(chain):
        name, arg = m.group(1), m.group(2)
        if arg is None:
            segs.append(name)
        else:
            try:
                segs.append((name, float(arg)))
            except ValueError as exc:
                raise SpatialRefError(f"argumento inválido em .{name}({arg})") from exc
    return segs


def _parse_dotted(sel: Any) -> list[str]:
    if not isinstance(sel, str):
        raise SpatialRefError(f"selector inválido: {sel!r}")
    return [p for p in sel.split(".") if p]


# --------------------------------------------------------------------------- #
# Busca de entidades no ModelState                                            #
# --------------------------------------------------------------------------- #
def find_body(state: ModelState | None, ref: Any) -> ModelStateBody:
    if state is None or not state.bodies:
        raise SpatialRefError(f"corpo {ref!r} não encontrado (ModelState vazio)")
    target = str(ref)
    for b in state.bodies:
        if b.stable_id == target or b.name == target:
            return b
    avail = [b.name for b in state.bodies]
    raise SpatialRefError(f"corpo {ref!r} não encontrado. Disponíveis: {avail}")


def find_face(state: ModelState | None, token: Any) -> ModelStateFace:
    for b in state.bodies if state else []:
        for f in b.faces:
            if f.token and f.token == token:
                return f
    raise SpatialRefError(f"face token {token!r} não encontrada no ModelState")


def find_edge(state: ModelState | None, token: Any) -> ModelStateEdge:
    for b in state.bodies if state else []:
        for e in b.edges:
            if e.token and e.token == token:
                return e
    raise SpatialRefError(f"aresta token {token!r} não encontrada no ModelState")


# --------------------------------------------------------------------------- #
# Geometria a partir das entidades                                            #
# --------------------------------------------------------------------------- #
def _require_vec(v: Any, what: str) -> Vec3:
    if (
        not isinstance(v, (list, tuple))
        or len(v) < 3
        or any(not isinstance(c, (int, float)) or isinstance(c, bool) for c in v[:3])
    ):
        raise SpatialRefError(f"{what} ausente/inválido no ModelState (rode query_geometry)")
    return (float(v[0]), float(v[1]), float(v[2]))


def _normalize(vec: Any) -> Vec3:
    x, y, z = _require_vec(vec, "vetor de eixo")
    mag = (x * x + y * y + z * z) ** 0.5
    if mag <= 1e-9:
        raise SpatialRefError("vetor de eixo tem magnitude ~0")
    return (x / mag, y / mag, z / mag)


def _face_center(f: ModelStateFace) -> Vec3:
    return _require_vec(f.center_mm, "centro da face")


def _face_normal(f: ModelStateFace) -> Vec3:
    if not f.normal_axis:
        raise SpatialRefError(
            "face sem normal cardinal (não-planar); use um eixo explícito (+x..-z) "
            "ou a direção de uma aresta"
        )
    key = str(f.normal_axis).strip().lower()
    if key not in _CARDINAL:
        raise SpatialRefError(f"normal de face {f.normal_axis!r} não reconhecida")
    return _CARDINAL[key]


def _body_center(b: ModelStateBody) -> Vec3:
    lo = _require_vec(b.bbox_min_mm, f"bbox do corpo {b.name!r}")
    hi = _require_vec(b.bbox_max_mm, f"bbox do corpo {b.name!r}")
    return ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)


def _bbox_scalar(b: ModelStateBody, name: str) -> float:
    lohi, _, axis = name.partition("_")  # "min_x" -> ("min","_","x")
    if lohi not in ("min", "max") or axis not in _COMPONENT_INDEX:
        raise SpatialRefError(f"selector de bbox inválido: {name!r}")
    vec = b.bbox_min_mm if lohi == "min" else b.bbox_max_mm
    return _require_vec(vec, f"bbox do corpo {b.name!r}")[_COMPONENT_INDEX[axis]]


def _edge_point(e: ModelStateEdge, *, fraction: float) -> Vec3:
    s = _require_vec(e.start_point_mm, "ponta inicial da aresta")
    t = _require_vec(e.end_point_mm, "ponta final da aresta")
    return tuple(s[i] + fraction * (t[i] - s[i]) for i in range(3))  # type: ignore[return-value]


def _edge_direction(e: ModelStateEdge) -> Vec3:
    if e.direction is not None:
        return _normalize(e.direction)
    s = _require_vec(e.start_point_mm, "ponta inicial da aresta")
    t = _require_vec(e.end_point_mm, "ponta final da aresta")
    return _normalize((t[0] - s[0], t[1] - s[1], t[2] - s[2]))


# --------------------------------------------------------------------------- #
# Avaliação da cadeia de selectors                                            #
# --------------------------------------------------------------------------- #
def _seg_name(seg: Any) -> str:
    return seg[0] if isinstance(seg, tuple) else seg


def _eval_chain(kind: str, entity: Any, segs: list[Any]) -> tuple[str, Any]:
    """Avalia a cadeia de selectors numa entidade → ``("vector"|"axis"|"scalar",
    valor)``. Um componente final ``.x/.y/.z`` transforma vetor/eixo em escalar.
    """

    if not segs:
        raise SpatialRefError(
            f"@{kind} precisa de um selector (.center / .along(..) / .bbox.max_z)"
        )
    head, rest = segs[0], segs[1:]
    name = _seg_name(head)
    vkind: str
    val: Any

    if kind in ("token", "face"):
        if name == "center":
            vkind, val = "vector", _face_center(entity)
        elif name == "normal":
            vkind, val = "axis", _face_normal(entity)
        else:
            raise SpatialRefError(f"selector .{name} inválido para face (use center/normal)")

    elif kind == "edge":
        if name == "along":
            if not isinstance(head, tuple):
                raise SpatialRefError(".along precisa de fração, ex.: .along(0.2)")
            vkind, val = "vector", _edge_point(entity, fraction=head[1])
        elif name in ("midpoint", "mid"):
            vkind, val = "vector", _edge_point(entity, fraction=0.5)
        elif name in ("start", "start_point"):
            vkind, val = "vector", _require_vec(entity.start_point_mm, "ponta inicial da aresta")
        elif name in ("end", "endpoint", "end_point"):
            vkind, val = "vector", _require_vec(entity.end_point_mm, "ponta final da aresta")
        elif name == "direction":
            vkind, val = "axis", _edge_direction(entity)
        else:
            raise SpatialRefError(
                f"selector .{name} inválido para aresta (along/midpoint/start/end/direction)"
            )

    elif kind == "body":
        if name == "center":
            vkind, val = "vector", _body_center(entity)
        elif name == "corner":
            vkind = "vector"
            val = _require_vec(entity.bbox_min_mm, f"bbox do corpo {entity.name!r}")
        elif name == "bbox":
            if not rest:
                raise SpatialRefError(".bbox precisa de .min_x/.max_z/.corner/.center")
            sub = _seg_name(rest[0])
            rest = rest[1:]
            if sub == "corner":
                vkind, val = (
                    "vector",
                    _require_vec(entity.bbox_min_mm, f"bbox do corpo {entity.name!r}"),
                )
            elif sub == "center":
                vkind, val = "vector", _body_center(entity)
            elif sub in _BBOX_SCALAR:
                vkind, val = "scalar", _bbox_scalar(entity, sub)
            else:
                raise SpatialRefError(f"selector .bbox.{sub} inválido")
        elif name in _BBOX_SCALAR:  # atalho @body('X').max_z
            vkind, val = "scalar", _bbox_scalar(entity, name)
        else:
            raise SpatialRefError(
                f"selector .{name} inválido para corpo (center/corner/bbox.<min|max>_<eixo>)"
            )
    else:
        raise SpatialRefError(f"tipo de referência @{kind} desconhecido")

    # Componente final (.x/.y/.z) → escalar.
    for seg in rest:
        segname = _seg_name(seg)
        if segname in _COMPONENT_INDEX and vkind in ("vector", "axis"):
            val = val[_COMPONENT_INDEX[segname]]
            vkind = "scalar"
        else:
            raise SpatialRefError(f"selector .{segname} inválido após {vkind}")
    return vkind, val


def _entity_for(kind: str, id_: Any, state: ModelState | None) -> Any:
    if kind in ("token", "face"):
        return find_face(state, id_)
    if kind == "edge":
        return find_edge(state, id_)
    if kind == "body":
        return find_body(state, id_)
    raise SpatialRefError(f"tipo de referência @{kind} desconhecido")


def _object_to_segs(ref: dict[str, Any]) -> tuple[str, Any, list[Any]]:
    """Normaliza a forma-objeto em ``(kind, id, segments)`` para ``_eval_chain``."""

    if "face" in ref or "token" in ref:
        kind, id_ = "face", (ref.get("face") or ref.get("token"))
        if ref.get("axis") == "normal":
            segs: list[Any] = ["normal"]
        else:
            segs = _parse_dotted(ref.get("point", "center"))
    elif "edge" in ref:
        kind, id_ = "edge", ref["edge"]
        if ref.get("axis") == "direction":
            segs = ["direction"]
        else:
            point = ref.get("point", "midpoint")
            if point == "along":
                segs = [("along", float(ref.get("fraction", 0.5)))]
            else:
                segs = _parse_dotted(point)
    elif "body" in ref:
        kind, id_ = "body", ref["body"]
        sel = ref.get("point") or ref.get("select") or "center"
        segs = _parse_dotted(sel)
    else:
        raise SpatialRefError(f"referência-objeto sem face/edge/body: {ref!r}")

    component = ref.get("component")
    if component:
        segs = segs + _parse_dotted(component)
    return kind, id_, segs


def _resolve_any(ref: Any, state: ModelState | None) -> tuple[str, Any]:
    """Resolve objeto OU @-string única → ``(vkind, valor)``. Listas/tuplas
    numéricas viram vetor cru (passthrough)."""

    if isinstance(ref, dict):
        kind, id_, segs = _object_to_segs(ref)
    elif isinstance(ref, str):
        kind, id_, segs = parse_at_expr(ref)
    elif isinstance(ref, (list, tuple)):
        return "vector", _require_vec(ref, "vetor")
    else:
        raise SpatialRefError(f"referência espacial inválida: {ref!r}")
    entity = _entity_for(kind, id_, state)
    return _eval_chain(kind, entity, segs)


# --------------------------------------------------------------------------- #
# Aritmética restrita (AST, sem eval)                                         #
# --------------------------------------------------------------------------- #
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_arith(expr: str) -> float:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise SpatialRefError(f"expressão aritmética inválida: {expr!r}") from exc
    return _eval_ast(tree.body)


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            raise SpatialRefError("booleano não é número")
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_ast(node.operand))
    raise SpatialRefError("expressão aritmética não suportada (só números e + - * / % ( ))")


# --------------------------------------------------------------------------- #
# API pública: resolve_point / resolve_axis / resolve_scalar                  #
# --------------------------------------------------------------------------- #
def resolve_point(ref: Any, state: ModelState | None) -> Vec3:
    """Resolve uma referência (objeto, @-string única, ou ``[x,y,z]`` cru) em um
    ponto ``(x, y, z)`` em mm. Erro tipado se resolver eixo/escalar."""

    vkind, val = _resolve_any(ref, state)
    if vkind != "vector":
        raise SpatialRefError(f"referência {ref!r} resolveu {vkind}, esperava ponto")
    return val


def resolve_axis(ref: Any, state: ModelState | None) -> Vec3:
    """Resolve um eixo em vetor unitário. Aceita cardinal (``"+z"``), ``[x,y,z]``
    cru, @-string (``@edge('E').direction``) ou objeto (face→normal,
    aresta→direction por padrão)."""

    if isinstance(ref, str):
        key = ref.strip().lower()
        if key in _CARDINAL:
            return _CARDINAL[key]
    elif isinstance(ref, (list, tuple)):
        return _normalize(ref)
    elif isinstance(ref, dict):
        ax = ref.get("axis")
        if isinstance(ax, str) and ax.strip().lower() in _CARDINAL:
            return _CARDINAL[ax.strip().lower()]
        if isinstance(ax, (list, tuple)):
            return _normalize(ax)
        if "axis" not in ref:
            ref = dict(ref)
            if "edge" in ref:
                ref["axis"] = "direction"
            elif "face" in ref or "token" in ref:
                ref["axis"] = "normal"
    vkind, val = _resolve_any(ref, state)
    if vkind == "scalar":
        raise SpatialRefError(f"referência {ref!r} resolveu escalar, esperava eixo")
    return _normalize(val)


def resolve_scalar(value: Any, state: ModelState | None) -> float:
    """Resolve um escalar em mm. Aceita número cru, objeto-escalar
    (``{body, point:"bbox.max_z"}``), ou @-string com aritmética restrita
    (``"@body('Placa').bbox.max_z - 20"``)."""

    if isinstance(value, bool):
        raise SpatialRefError("booleano não é escalar")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        vkind, val = _resolve_any(value, state)
        if vkind != "scalar":
            raise SpatialRefError(
                f"objeto {value!r} resolveu {vkind}; escalar exige componente "
                "(.x/.y/.z) ou bbox.<min|max>_<eixo>"
            )
        return float(val)
    if isinstance(value, str):
        return _resolve_scalar_expr(value, state)
    raise SpatialRefError(f"escalar inválido: {value!r}")


def _resolve_scalar_expr(expr: str, state: ModelState | None) -> float:
    """Substitui cada @-ref (que DEVE resolver escalar) por seu número e avalia a
    aritmética restante por AST restrito."""

    matches = list(_AT_RE.finditer(expr))
    if not matches:
        return _safe_arith(expr)
    out: list[str] = []
    last = 0
    for m in matches:
        out.append(expr[last : m.start()])
        kind, id_, chain = m.group("kind"), m.group("id"), _parse_chain(m.group("chain"))
        entity = _entity_for(kind, id_, state)
        vkind, val = _eval_chain(kind, entity, chain)
        if vkind != "scalar":
            raise SpatialRefError(
                f"referência {m.group(0)!r} resolveu {vkind}; em expressão escalar "
                "exige componente (.x/.y/.z) ou bbox.<min|max>_<eixo>"
            )
        out.append(f"({val!r})")
        last = m.end()
    out.append(expr[last:])
    return _safe_arith("".join(out))
