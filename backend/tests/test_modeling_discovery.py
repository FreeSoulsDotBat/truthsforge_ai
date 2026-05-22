"""Unit tests for the discovery agent (P2 do chat-flow-redesign).

Cobrem a lógica de decisão (limiar de confiança + perguntas) sem chamar o
LLM, e o fallback heurístico que nunca bloqueia o usuário.
"""

from __future__ import annotations

from app.modeling.discovery import (
    _assessment_from_payload,
    heuristic_assessment,
)


def test_ready_when_confident_and_no_questions() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.92,
        "questions": [],
        "refined_brief": "Placa 80x60x5mm com furo central de 10mm.",
        "rationale": "Dimensões claras.",
    }
    out = _assessment_from_payload(parsed, threshold=0.7)
    assert out.ready_to_plan is True
    assert out.questions == []
    assert out.refined_brief.startswith("Placa 80x60")


def test_low_confidence_blocks_even_if_model_says_ready() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.4,
        "questions": [],
        "refined_brief": "algo vago",
        "rationale": "Pouca certeza.",
    }
    out = _assessment_from_payload(parsed, threshold=0.7)
    assert out.ready_to_plan is False
    # Sem perguntas do LLM, injetamos uma genérica para não travar o usuário.
    assert len(out.questions) >= 1
    assert out.refined_brief == ""


def test_questions_force_discovery_even_if_ready_true() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.95,
        "questions": ["Qual a altura em mm?"],
        "refined_brief": "",
        "rationale": "Falta altura.",
    }
    out = _assessment_from_payload(parsed, threshold=0.7)
    assert out.ready_to_plan is False
    assert out.questions == ["Qual a altura em mm?"]


def test_not_ready_keeps_listed_questions() -> None:
    parsed = {
        "ready_to_plan": False,
        "confidence": 0.3,
        "questions": ["Qual a geometria?", "Quais dimensões?"],
        "refined_brief": "",
        "rationale": "Pedido vago.",
    }
    out = _assessment_from_payload(parsed, threshold=0.7)
    assert out.ready_to_plan is False
    assert out.questions == ["Qual a geometria?", "Quais dimensões?"]


def test_heuristic_assessment_never_blocks() -> None:
    out = heuristic_assessment("uma peça qualquer")
    assert out.ready_to_plan is True
    assert out.questions == []
    assert out.refined_brief == "uma peça qualquer"
    assert out.source.value == "heuristic"
    assert out.intent == "new_model"


def test_intent_edit_when_model_exists() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.9,
        "questions": [],
        "refined_brief": "Aumentar a espessura para 8mm.",
        "intent": "edit",
        "rationale": "alteração do modelo atual",
    }
    out = _assessment_from_payload(parsed, threshold=0.7, has_existing_model=True)
    assert out.ready_to_plan is True
    assert out.intent == "edit"


def test_intent_ambiguous_preserved_when_model_exists() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.9,
        "questions": [],
        "refined_brief": "Fazer um suporte.",
        "intent": "ambiguous",
        "rationale": "pode ser edição ou novo",
    }
    out = _assessment_from_payload(parsed, threshold=0.7, has_existing_model=True)
    assert out.intent == "ambiguous"


def test_intent_forced_new_model_without_existing_model() -> None:
    parsed = {
        "ready_to_plan": True,
        "confidence": 0.9,
        "questions": [],
        "refined_brief": "Cubo 20mm.",
        "intent": "edit",  # LLM errou; sem modelo, deve virar new_model
        "rationale": "",
    }
    out = _assessment_from_payload(parsed, threshold=0.7, has_existing_model=False)
    assert out.intent == "new_model"


def test_heuristic_intent_edit_when_model_exists() -> None:
    out = heuristic_assessment("adicione um furo", has_existing_model=True)
    assert out.intent == "edit"
