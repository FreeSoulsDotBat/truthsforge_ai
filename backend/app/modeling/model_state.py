"""F1 — Estado rico do modelo (replan v4, capacidades).

Converte o read-back de ``fusion.query_geometry`` num ``ModelState``
estruturado (com tokens estáveis de face/edge) e o renderiza como bloco
textual injetável no contexto do planner entre etapas/edições. Substitui o
contexto puramente textual (nomes de timeline/params) por geometria real.

Camada de domínio pura — não toca o Fusion. A captura (``capture_model_state``)
roda um probe ``query_geometry`` fora dos steps via o executor, no mesmo molde
de ``chat_orchestrator._read_live_timeline`` (best-effort, nunca bloqueia).
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelState,
    ModelStateBody,
    ModelStateEdge,
    ModelStateFace,
)
from app.modeling.executor import inner_fusion_payload

logger = logging.getLogger(__name__)

# Quanto expor no bloco textual (token completo só das entidades salientes,
# para não estourar o prompt — tokens são longos).
_MAX_FACES_RENDERED = 8
_MAX_EDGES_RENDERED = 8


def model_state_from_query_output(output: dict[str, Any] | None) -> ModelState | None:
    """Parseia o envelope de saída de ``fusion.query_geometry`` num ``ModelState``.

    Tolerante a campos faltando (mock/in-process/versões antigas do adapter):
    usa ``inner_fusion_payload`` para desempacotar o envelope HTTP e ignora o
    que não reconhece. Retorna ``None`` se não houver ``bodies``.
    """

    payload = inner_fusion_payload(output) or (output if isinstance(output, dict) else None)
    if not isinstance(payload, dict):
        return None
    raw_bodies = payload.get("bodies")
    if not isinstance(raw_bodies, list):
        return None

    bodies: list[ModelStateBody] = []
    for rb in raw_bodies:
        if not isinstance(rb, dict):
            continue
        faces = [
            ModelStateFace(
                token=f.get("face_token"),
                type=f.get("type"),
                area_mm2=f.get("area_mm2"),
                radius_mm=f.get("radius_mm"),
                normal_axis=f.get("normal_axis"),
                center_mm=f.get("center_mm"),
                # F9 F0: o script emite ``is_open_boundary`` (borda de abertura), mas
                # o parser o descartava — cegava ``cover_opening`` e o estado
                # semântico (Pilar 2). None no mock/adapters antigos.
                is_open_boundary=f.get("is_open_boundary"),
            )
            for f in rb.get("faces", [])
            if isinstance(f, dict)
        ]
        edges = [
            ModelStateEdge(
                token=e.get("edge_token"),
                length_mm=e.get("length_mm"),
                is_circular=bool(e.get("is_circular")),
                radius_mm=e.get("radius_mm"),
                start_point_mm=e.get("start_point_mm"),
                end_point_mm=e.get("end_point_mm"),
                direction=e.get("direction"),
                adjacent_face_tokens=[
                    t for t in e.get("adjacent_face_tokens", []) if isinstance(t, str)
                ],
            )
            for e in rb.get("edges", [])
            if isinstance(e, dict)
        ]
        bodies.append(
            ModelStateBody(
                stable_id=rb.get("stable_id"),
                name=rb.get("name"),
                dimensions_mm=rb.get("dimensions_mm"),
                bbox_min_mm=rb.get("bbox_min_mm"),
                bbox_max_mm=rb.get("bbox_max_mm"),
                is_solid=rb.get("is_solid"),
                is_closed=rb.get("is_closed"),
                surface_area_mm2=rb.get("surface_area_mm2"),
                face_count=rb.get("face_count"),
                edge_count=rb.get("edge_count"),
                faces=faces,
                edges=edges,
            )
        )
    if not bodies:
        return None
    return ModelState(bodies=bodies)


def render_model_state_block(state: ModelState | None) -> str:
    """Renderiza o ``ModelState`` como bloco ``<model-state>`` para o prompt.

    Mostra o token COMPLETO só das entidades salientes (faces cilíndricas/
    maiores, arestas circulares) — são as que o planner usa para mirar
    mecanismos (eixo de um pino, borda de um furo). O resto vira contagem.
    """

    if state is None or not state.bodies:
        return ""
    lines = ["<model-state fonte=read-back>"]
    for b in state.bodies:
        dims = b.dimensions_mm or []
        dims_s = "x".join(f"{d:g}" for d in dims) if dims else "?"
        kind = "sólido" if b.is_solid else "superfície"
        ref = b.stable_id or b.name or "?"
        # F9 Pilar 2: rótulo de papel derivado (container/lid/...), quando houver.
        label = f"; papel={b.body_label}" if b.body_label else ""
        lines.append(
            f"- corpo '{b.name}' (ref estável={ref}; {kind}; bbox {dims_s} mm; "
            f"{b.face_count or 0} faces, {b.edge_count or 0} arestas{label})"
        )
        # F9 Pilar 2: adjacências derivadas (quem encosta/interfere em quem) — a
        # semântica de montagem que o LLM lê em vez de chutar coordenada.
        for t in b.touches:
            rel = "interfere com" if t.interference else "encosta em"
            lines.append(f"    {rel} '{t.other}' (eixo {t.axis}, folga {t.gap_mm}mm)")
        # Faces salientes: cilíndricas/cônicas (com raio) primeiro, depois as
        # maiores planares — são os alvos típicos de rosca/furo/junta.
        ranked_faces = sorted(
            b.faces,
            key=lambda f: (f.radius_mm is None, -(f.area_mm2 or 0.0)),
        )
        for f in ranked_faces[:_MAX_FACES_RENDERED]:
            if not f.token:
                continue
            extra = f" raio={f.radius_mm:g}mm" if f.radius_mm else ""
            axis = f" normal={f.normal_axis}" if f.normal_axis else ""
            ctr = f" centro={f.center_mm}" if f.center_mm else ""
            # F9 Pilar 2: papéis derivados (top_planar/open_boundary/...) p/ o LLM
            # ECOAR por apelido em vez de copiar o token opaco.
            roles = f" papéis={','.join(f.roles)}" if f.roles else ""
            lines.append(f"    face[{f.type or '?'}{extra}{axis}{ctr}]{roles} token={f.token}")
        # Arestas circulares (furos/knuckle) primeiro.
        ranked_edges = sorted(b.edges, key=lambda e: (not e.is_circular, -(e.radius_mm or 0.0)))
        shown = 0
        for e in ranked_edges:
            if not e.token or not e.is_circular or e.radius_mm is None:
                continue
            lines.append(f"    aresta[circular raio={e.radius_mm:g}mm] token={e.token}")
            shown += 1
            if shown >= _MAX_EDGES_RENDERED:
                break
    lines.append("</model-state>")
    return "\n".join(lines)


def capture_model_state(executor: Any, plan: ModelingPlan) -> ModelState | None:
    """F1 (T1.6): captura o ModelState rodando um probe ``query_geometry`` fora
    dos steps do plano (mesmo molde de ``_read_live_timeline``). Best-effort —
    nunca propaga exceção; retorna ``None`` se não for fusion, falhar, ou não
    houver geometria. O chamador grava em ``plan.model_state``.
    """

    if plan.software_choice != ModelingSoftware.fusion:
        return None
    probe = ModelingPlanStep(
        seq=1,
        title="read-back ModelState",
        software=ModelingSoftware.fusion,
        tool_name="fusion.query_geometry",
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json={"include_tokens": True},
    )
    try:
        outcome = executor._execute_single_step(probe, plan=plan)
    except Exception as exc:  # noqa: BLE001 - probe é best-effort
        logger.debug("capture_model_state: probe falhou (%s)", exc)
        return None
    # _execute_single_step devolve um _StepOutcome (.ok/.output), igual ao
    # consumo em chat_orchestrator._read_live_timeline.
    output = getattr(outcome, "output", outcome)
    if getattr(outcome, "ok", True) is False or not isinstance(output, dict):
        return None
    try:
        state = model_state_from_query_output(output)
    except Exception as exc:  # noqa: BLE001
        logger.debug("capture_model_state: parse falhou (%s)", exc)
        return None
    return _maybe_enrich_semantic(state)


def _maybe_enrich_semantic(state: ModelState | None) -> ModelState | None:
    """F9 Pilar 2: atrás de ``modeling_semantic_state_enabled``, deriva roles/
    touches/body_label (medindo) e injeta no state. Best-effort — nunca propaga
    exceção; flag OFF = state intacto (zero regressão)."""

    from app.core.config import settings

    if state is None or not settings.modeling_semantic_state_enabled:
        return state
    try:
        from app.modeling.semantic_state import derive_semantic_state

        return derive_semantic_state(state)
    except Exception as exc:  # noqa: BLE001 - enriquecimento é best-effort
        logger.debug("capture_model_state: enriquecimento semântico falhou (%s)", exc)
        return state


__all__ = [
    "model_state_from_query_output",
    "render_model_state_block",
    "capture_model_state",
]
