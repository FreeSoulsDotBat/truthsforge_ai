"""Discovery agent for 3D modeling chats (P2 of chat-flow-redesign).

Before the planner turns a request into an executable plan, this agent
decides whether the request is clear enough to plan, or whether the agent
should ask the user clarifying questions first. The product decision
(2026-05-20) is to **ask only when there is real ambiguity** — a confidence
threshold gates the question loop so trivial, unambiguous requests flow
straight to the plan (which the P1 gate still holds for approval).

The agent is a thin LLM call with Structured Outputs, mirroring
``planner.create_llm_plan_async``. When no planner model is available it
degrades to :func:`heuristic_assessment`, which never blocks the user.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.contracts import (
    ModelConfig,
    ModelingDiscoveryAssessment,
    ModelingPlannerSource,
    ModelingSoftware,
)
from app.llm_gateway.gateway import LLMGateway

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# Limita o histórico enviado ao LLM para não estourar contexto/custo num
# chat longo. As perguntas de descoberta dependem só dos últimos turnos.
_MAX_HISTORY_MESSAGES = 12

DISCOVERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "ready_to_plan",
        "confidence",
        "questions",
        "refined_brief",
        "rationale",
    ],
    "properties": {
        "ready_to_plan": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "questions": {"type": "array", "items": {"type": "string"}},
        "refined_brief": {"type": "string"},
        "rationale": {"type": "string"},
    },
}

_SYSTEM_PROMPT = (
    "Você é o agente de DESCOBERTA de modelagem 3D da Truth's Forge AI, "
    "sempre em português brasileiro.\n"
    "Sua única tarefa agora é decidir se o pedido do usuário já tem contexto "
    "suficiente para virar um plano de modelagem CONCRETO e EXECUTÁVEL, ou se "
    "faltam informações que você precisa perguntar antes.\n\n"
    "Um pedido está pronto para planejar quando dá para inferir, com segurança:\n"
    "- a geometria pretendida (o que é a peça);\n"
    "- as dimensões principais aproximadas em milímetros;\n"
    "- quando relevante: material/processo (impressão 3D FDM, usinagem...), "
    "encaixes, função e restrições físicas.\n\n"
    "REGRAS:\n"
    "- Pergunte SOMENTE quando houver ambiguidade real. Se o pedido já é claro "
    "o suficiente para gerar etapas (mesmo assumindo defaults razoáveis e "
    "declarando essas suposições), marque ready_to_plan=true.\n"
    "- NÃO faça perguntas burocráticas para pedidos óbvios (ex.: 'um cubo de "
    "20mm' está pronto).\n"
    "- Quando faltar dimensão crítica ou a forma for vaga ('uma peça pequena', "
    "'um suporte'), marque ready_to_plan=false e liste perguntas objetivas.\n"
    "- Faça poucas perguntas e focadas (no máximo 3), uma dimensão de cada vez "
    "(geometria → dimensões → material).\n"
    "- confidence é sua certeza (0–1) de que o pedido está pronto para planejar.\n"
    "- Quando ready_to_plan=true, escreva em refined_brief uma descrição "
    "COMPLETA em linguagem natural (com dimensões em mm e suposições "
    "explícitas) que será a entrada do planner. Quando false, deixe "
    "refined_brief vazio e preencha questions.\n"
    "- rationale: 1 frase explicando a decisão.\n"
    "Responda APENAS no JSON do schema modeling_discovery_assessment."
)


def _build_messages(
    prompt: str,
    history: list[dict[str, str]] | None,
    software_override: ModelingSoftware | None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if history:
        for item in history[-_MAX_HISTORY_MESSAGES:]:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
    user_block = prompt.strip()
    if software_override is not None:
        user_block = (
            f"{user_block}\n\n(O usuário já escolheu o software "
            f"{software_override.value}; isso não muda a necessidade de "
            "esclarecer geometria/dimensões.)"
        )
    messages.append({"role": "user", "content": user_block})
    return messages


def _assessment_from_payload(
    parsed: dict[str, Any], *, threshold: float
) -> ModelingDiscoveryAssessment:
    ready = bool(parsed.get("ready_to_plan", True))
    try:
        confidence = float(parsed.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    confidence = max(0.0, min(1.0, confidence))
    questions = [
        q.strip()
        for q in parsed.get("questions", []) or []
        if isinstance(q, str) and q.strip()
    ]
    refined_brief = (parsed.get("refined_brief") or "").strip()
    rationale = (parsed.get("rationale") or "").strip()

    # Decisão final: só prossegue quando o LLM diz ready, a confiança bate o
    # limiar E não restaram perguntas. Qualquer pergunta listada força o
    # loop de descoberta (o LLM achou algo a esclarecer).
    effective_ready = ready and confidence >= threshold and not questions
    if not effective_ready and not questions:
        # O LLM travou sem perguntar — não deixa o usuário sem saída.
        questions = [
            "Pode detalhar a geometria e as dimensões principais em "
            "milímetros do que você quer modelar?"
        ]
    return ModelingDiscoveryAssessment(
        ready_to_plan=effective_ready,
        confidence=confidence,
        questions=[] if effective_ready else questions,
        refined_brief=refined_brief if effective_ready else "",
        rationale=rationale,
        source=ModelingPlannerSource.llm,
    )


async def assess_request_async(
    prompt: str,
    *,
    gateway: LLMGateway,
    model: ModelConfig,
    history: list[dict[str, str]] | None = None,
    software_override: ModelingSoftware | None = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> ModelingDiscoveryAssessment:
    """Call the LLM to assess whether ``prompt`` is ready to plan.

    Raises any provider exception; the caller wraps with a fallback to
    :func:`heuristic_assessment`.
    """

    messages = _build_messages(prompt, history, software_override)
    parsed = await gateway.generate_structured(
        model=model,
        messages=messages,
        schema_name="modeling_discovery_assessment",
        schema=DISCOVERY_SCHEMA,
    )
    return _assessment_from_payload(parsed, threshold=threshold)


def heuristic_assessment(
    prompt: str, history: list[dict[str, str]] | None = None
) -> ModelingDiscoveryAssessment:
    """Fallback when no planner model is available.

    Conservatively does NOT block the user: returns ready_to_plan=true so the
    flow degrades to "propose plan" (still held by the P1 approval gate). The
    refined_brief is just the raw prompt.
    """

    return ModelingDiscoveryAssessment(
        ready_to_plan=True,
        confidence=0.5,
        questions=[],
        refined_brief=prompt.strip(),
        rationale="discovery_llm_unavailable",
        source=ModelingPlannerSource.heuristic,
    )


__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DISCOVERY_SCHEMA",
    "assess_request_async",
    "heuristic_assessment",
]
