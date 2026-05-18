"""Tests pinning the discovery system prompt contract (Onda 2.5)."""

from __future__ import annotations

from app.modeling.prompts import discovery_system_prompt


def test_prompt_loads_and_is_non_empty() -> None:
    body = discovery_system_prompt()
    assert isinstance(body, str)
    assert len(body) > 1000  # plenty of content


def test_prompt_lists_the_five_chat_first_tools() -> None:
    body = discovery_system_prompt()
    for tool_name in (
        "3d.ask_clarification",
        "3d.propose_plan",
        "3d.propose_edit_plan",
        "3d.request_high_risk_approval",
        "3d.analyze_attachment",
    ):
        assert tool_name in body, f"Missing tool reference: {tool_name}"


def test_prompt_documents_state_machine_stages() -> None:
    body = discovery_system_prompt()
    for stage in ("discovery", "planning", "executing", "editing"):
        assert stage in body, f"Missing stage in prompt: {stage}"


def test_prompt_forbids_free_code_and_textual_approval() -> None:
    body = discovery_system_prompt()
    assert "Sem código livre" in body
    assert "Aprovação só via card" in body


def test_prompt_is_pt_br_facing() -> None:
    body = discovery_system_prompt()
    assert "português brasileiro" in body.lower()
