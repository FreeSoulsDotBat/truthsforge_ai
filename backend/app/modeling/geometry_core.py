"""Núcleo geométrico puro compartilhado (ADR-023).

Camada de domínio **pura** (sem ``adsk``): medidas de bounding-box sobre o
``ModelState`` que mais de um módulo do contexto 3D consome. Existe para ser a
FONTE ÚNICA dessas medidas — antes desta extração ``geometry_verifier`` e
``model_critique`` mantinham CÓPIAS divergentes de :func:`bbox_overlap_volume`
(corte estrito ``<= 0`` vs ``<= 1e-3``), produzindo dois vereditos sobre
"interferência/contato" no mesmo modelo. O limiar continua sendo política de
cada chamador — agora EXPLÍCITO via o parâmetro ``eps``, não escondido numa
segunda implementação que pode derivar quando uma das cópias for editada.

NÃO confundir :func:`find_body_by_ref` (busca por ``stable_id``/``name`` no
``ModelState``, devolve ``None``) com as funções homônimas de ``entity_ref`` /
``relation_derive`` (que LEVANTAM erro tipado) nem com a de
``fusion_mcp_scripts`` (que opera sobre o ``design`` DENTRO do Fusion): são
contratos distintos, deliberadamente NÃO unificados aqui.
"""

from __future__ import annotations

from app.core.contracts import ModelState, ModelStateBody

__all__ = [
    "bbox_overlap_volume",
    "find_body_by_ref",
    "gap_along",
    "mate_axis",
]


def find_body_by_ref(state: ModelState | None, ref: str) -> ModelStateBody | None:
    """Corpo cujo ``stable_id`` OU ``name`` casa com ``ref`` (ou ``None``)."""
    for b in state.bodies if state else []:
        if b.stable_id == ref or b.name == ref:
            return b
    return None


def _center(b: ModelStateBody) -> list[float] | None:
    if not (b.bbox_min_mm and b.bbox_max_mm):
        return None
    return [(b.bbox_min_mm[i] + b.bbox_max_mm[i]) / 2.0 for i in range(3)]


def mate_axis(m: ModelStateBody, r: ModelStateBody) -> int:
    """Eixo do mate = aquele de maior separação entre os centros (o empilhamento).

    Limitação conhecida (laudo F8, baixa/latente): a inferência por centro erra se
    o desalinhamento lateral exceder a altura do empilhamento. A medição robusta
    viria da NORMAL da face-alvo declarada na recipe (top_planar/open_boundary) —
    follow-up quando o verificador for plugado no loop (hoje só reporta, não-ligado)."""

    cm, cr = _center(m), _center(r)
    if cm is None or cr is None:
        return 2  # default z
    return max(range(3), key=lambda i: abs(cm[i] - cr[i]))


def gap_along(m: ModelStateBody, r: ModelStateBody, axis: int) -> float:
    """Folga (positiva) ou penetração (negativa) entre m e r ao longo de ``axis``."""

    cm, cr = _center(m), _center(r)
    if cm is None or cr is None:
        return 0.0
    if cm[axis] >= cr[axis]:  # m acima de r
        return m.bbox_min_mm[axis] - r.bbox_max_mm[axis]
    return r.bbox_min_mm[axis] - m.bbox_max_mm[axis]


def bbox_overlap_volume(a: ModelStateBody, b: ModelStateBody, *, eps: float = 0.0) -> float:
    """Volume (mm³) da interseção das bounding-boxes de ``a`` e ``b``.

    ``eps`` é o piso por-eixo abaixo do qual a sobreposição é tratada como
    contato/ruído numérico e não conta (retorna 0.0). ``eps=0.0`` (default) =
    corte estrito do verificador geométrico; ``eps=1e-3`` = tolerância da
    auto-crítica (``model_critique._OVERLAP_EPS``), que não quer acusar
    interferência por causa de 1 µm de penetração numérica. O comportamento de
    cada chamador é preservado bit-a-bit — a diferença vira parâmetro explícito,
    não uma segunda cópia da função."""

    if not (a.bbox_min_mm and a.bbox_max_mm and b.bbox_min_mm and b.bbox_max_mm):
        return 0.0
    vol = 1.0
    for i in range(3):
        lo = max(a.bbox_min_mm[i], b.bbox_min_mm[i])
        hi = min(a.bbox_max_mm[i], b.bbox_max_mm[i])
        overlap = hi - lo
        if overlap <= eps:
            return 0.0
        vol *= overlap
    return vol
