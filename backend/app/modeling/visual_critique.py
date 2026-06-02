"""Loop de verificação VISUAL (motor genérico, passo 3 — replan v4).

Depois de executar o plano, RENDERIZA o modelo (``capture_viewport``), manda o
render + a intenção para a LLM de VISÃO (gateway multimodal F4), recebe um
veredito estruturado (corresponde? que diverge?) e, se divergir, REPLANEJA uma
edição corretiva. É o que faz a composição genérica se auto-corrigir em
QUALQUER produto — sem código por caso.

Atrás de ``modeling_visual_verification_enabled`` (default OFF). Best-effort:
nunca derruba a execução; render só existe no Fusion real.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import logging
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
    ModelingTraceLevel,
    ModelingTraceSource,
)
from app.modeling.executor import inner_fusion_payload
from app.modeling.observability import get_tracer

logger = logging.getLogger(__name__)

# Schema do veredito estruturado da revisão visual.
VISUAL_VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "matches_intent": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "suggestion": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["matches_intent", "issues", "suggestion", "confidence"],
}

_VISION_SYSTEM = (
    "Você é um revisor de CAD criterioso. Recebe o RENDER de um modelo 3D e a "
    "INTENÇÃO do usuário. Aponte divergências geométricas CONCRETAS — posição, "
    "orientação, conexão entre corpos, proporção, features faltando ou no lugar "
    "errado. Não invente: se o modelo está fiel à intenção, diga que corresponde."
)


def _run_coro(coro: Any) -> Any:
    """Executa a corrotina de forma síncrona em qualquer contexto."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


def capture_viewport_image(executor: Any, plan: ModelingPlan, *, view: str = "iso") -> str | None:
    """Renderiza o viewport via probe ``capture_viewport`` e devolve o base64.

    Mesmo padrão do ``capture_model_state``: probe read-only fora dos steps,
    best-effort. Só para fusion; ``None`` em qualquer falha.
    """
    if getattr(plan, "software_choice", None) != ModelingSoftware.fusion:
        return None
    probe = ModelingPlanStep(
        seq=1,
        title="Render do viewport para verificação visual",
        software=ModelingSoftware.fusion,
        tool_name="fusion.capture_viewport",
        risk_level=ModelingRiskLevel.low,
        status=ModelingStepStatus.approved,
        input_json={"view": view},
    )
    try:
        outcome = executor._execute_single_step(probe, plan=plan)
    except Exception:  # noqa: BLE001 - render best-effort, nunca bloqueia
        logger.warning("capture_viewport probe falhou", exc_info=True)
        return None
    if not getattr(outcome, "ok", False):
        return None
    output = getattr(outcome, "output", None)
    inner = inner_fusion_payload(output) if isinstance(output, dict) else None
    if not isinstance(inner, dict):
        return None
    b64 = inner.get("image_base64")
    return b64 if isinstance(b64, str) and b64 else None


def critique_render(
    gateway: Any, model: Any, *, rendered_b64: str, intent: str
) -> dict[str, Any] | None:
    """Manda o render + a intenção para a LLM de visão; devolve o veredito."""
    from app.llm_gateway.multimodal import user_message_with_images

    try:
        raw = base64.b64decode(rendered_b64)
    except Exception:  # noqa: BLE001
        return None
    user_text = (
        "Intenção do usuário para este modelo:\n"
        + (intent or "(sem texto)")[:4000]
        + "\n\nO RENDER abaixo corresponde à intenção? Liste as divergências "
        "geométricas CONCRETAS (posição, orientação, conexão, proporção, "
        "features faltando/erradas). Se estiver fiel, matches_intent=true e "
        "issues=[]."
    )
    message = user_message_with_images(model.provider, user_text, [(raw, "image/png")])
    messages = [{"role": "system", "content": _VISION_SYSTEM}, message]
    try:
        verdict = _run_coro(
            gateway.generate_structured(
                model=model,
                messages=messages,
                schema_name="visual_verdict",
                schema=VISUAL_VERDICT_SCHEMA,
            )
        )
    except Exception as exc:  # noqa: BLE001 - crítica nunca derruba o plano
        logger.warning("crítica visual falhou: %s", exc)
        return None
    return verdict if isinstance(verdict, dict) else None


def _apply_visual_correction(
    executor: Any,
    planner: Any,
    plan: ModelingPlan,
    intent: str,
    issues: list[str],
) -> bool:
    """Replaneja uma edição corretiva a partir das divergências visuais."""
    state_block = None
    try:
        if getattr(plan, "model_state", None) is not None:
            from app.modeling.model_state import render_model_state_block

            state_block = render_model_state_block(plan.model_state)
    except Exception:  # noqa: BLE001
        state_block = None
    issues_text = "\n".join(f"- {issue}" for issue in issues[:8])
    payload = ModelingPlanCreate(
        prompt=(
            "Corrija o modelo ATUAL com base nestas DIVERGÊNCIAS VISUAIS "
            "apontadas por revisão de imagem (mantenha o resto intacto):\n"
            + issues_text
            + "\n\nIntenção original: "
            + (intent or "")[:1500]
        ),
        kind=ModelingPlanKind.edit,
        parent_plan_id=plan.id,
        conversation_id=plan.conversation_id,
        project_id=plan.project_id,
        software_override=ModelingSoftware.fusion,
    )
    try:
        correction_plan = planner.create_plan(payload, live_state_block=state_block)
        executor.execute_plan(correction_plan)
    except Exception:  # noqa: BLE001 - correção best-effort
        logger.warning("edição corretiva visual falhou", exc_info=True)
        return False
    return True


def run_visual_correction(executor: Any, planner: Any, plan: ModelingPlan) -> dict[str, Any] | None:
    """Loop visual: render → crítica → (replan edição) → re-render → re-crítica.

    Reusa ``planner.create_plan`` (edição) + ``executor``. Best-effort, atrás de
    flag. Devolve o veredito final (ou ``None`` se não rodou). Teto de rodadas
    de correção em ``settings.modeling_visual_max_rounds``.
    """
    if not settings.modeling_visual_verification_enabled:
        return None
    if getattr(plan, "software_choice", None) != ModelingSoftware.fusion:
        return None
    try:
        model = planner._resolve_planner_model()
    except Exception:  # noqa: BLE001
        model = None
    gateway = getattr(planner, "gateway", None)
    if model is None or gateway is None:
        return None

    intent = getattr(plan, "prompt", "") or ""
    tracer = get_tracer(getattr(executor, "store", None))
    max_rounds = max(0, int(settings.modeling_visual_max_rounds))
    verdict: dict[str, Any] | None = None

    for round_idx in range(max_rounds + 1):
        rendered = capture_viewport_image(executor, plan)
        if not rendered:
            return verdict
        verdict = critique_render(gateway, model, rendered_b64=rendered, intent=intent)
        if verdict is None:
            return None
        matches = bool(verdict.get("matches_intent"))
        issues = [str(i) for i in (verdict.get("issues") or []) if str(i).strip()]
        tracer.record(
            "visual.critique",
            source=ModelingTraceSource.backend,
            level=ModelingTraceLevel.info if matches else ModelingTraceLevel.warn,
            message=(
                "render corresponde à intenção"
                if matches
                else f"{len(issues)} divergência(s) visual(is) na rodada {round_idx}"
            ),
            payload={"matches": matches, "issues": issues[:10], "round": round_idx},
        )
        if matches or not issues:
            return verdict
        if round_idx >= max_rounds:
            return verdict  # esgotou as rodadas de correção
        if not _apply_visual_correction(executor, planner, plan, intent, issues):
            return verdict
    return verdict
