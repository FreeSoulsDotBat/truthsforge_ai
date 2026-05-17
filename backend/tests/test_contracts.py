import pytest
from pydantic import ValidationError

from app.core.contracts import (
    ChatStreamRequest,
    CostPolicy,
    ModelCapability,
    ModelConfig,
    ProviderModel,
    ProviderName,
)
from app.cost_governor.service import estimate_cost, has_configured_pricing
from app.llm_gateway.pricing import with_pricing
from app.storage.dev_store import default_seed_data


def test_cost_governor_estimates_brl() -> None:
    model = ModelConfig(
        id="openai/test",
        provider=ProviderName.openai,
        display_name="Test",
        input_token_cost_per_million=1,
        output_token_cost_per_million=2,
    )
    estimate = estimate_cost(model, CostPolicy(monthly_budget_brl=200), 1000, 1000)
    assert estimate.estimated_cost_brl == 0.015
    assert estimate.blocked is False


def test_cost_governor_blocks_projected_monthly_budget() -> None:
    model = ModelConfig(
        id="openai/test",
        provider=ProviderName.openai,
        display_name="Test",
        input_token_cost_per_million=1,
        output_token_cost_per_million=1,
    )

    estimate = estimate_cost(
        model,
        CostPolicy(monthly_budget_brl=1),
        tokens_in=100_000,
        tokens_out=100_000,
        current_spend_brl=0.25,
    )

    assert estimate.estimated_cost_brl == 1
    assert estimate.blocked is True
    assert estimate.reason == "estimated_monthly_budget_exceeded"


def test_seed_contains_deep_research_model() -> None:
    models = [ModelConfig(**item) for item in default_seed_data()["models"]]
    deep_research = next(model for model in models if model.id == "openai/deep-research")

    assert deep_research.provider == ProviderName.openai
    assert deep_research.provider_model_id == "o4-mini-deep-research"
    assert ModelCapability.deep_research in deep_research.capabilities


def test_deep_research_and_image_mode_are_exclusive() -> None:
    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="pesquise e gere imagem", deep_research=True, response_mode="image"
        )


def test_reasoning_summary_is_only_for_regular_text_chat() -> None:
    with pytest.raises(ValidationError):
        ChatStreamRequest(message="gere imagem", response_mode="image", reasoning_summary="auto")

    with pytest.raises(ValidationError):
        ChatStreamRequest(message="pesquise", deep_research=True, reasoning_summary="auto")


def test_modeling_3d_context_is_exclusive_with_other_structured_modes() -> None:
    payload = ChatStreamRequest(
        message="crie um suporte 3d",
        modeling_3d={"enabled": True, "software_override": "auto"},
    )
    assert payload.modeling_3d.enabled is True
    assert payload.modeling_3d.software_override is None

    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="crie uma peça e uma imagem",
            response_mode="image",
            modeling_3d={"enabled": True},
        )

    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="pesquise uma peça",
            deep_research=True,
            modeling_3d={"enabled": True},
        )

    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="raciocine e modele",
            reasoning_summary="auto",
            modeling_3d={"enabled": True},
        )

    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="modele com agentes",
            multi_agent_mode=True,
            modeling_3d={"enabled": True},
        )


def test_chat_attachments_have_hard_limits() -> None:
    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="teste",
            attached_file_ids=[f"file_{index}" for index in range(11)],
        )

    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="teste",
            attached_document_ids=[f"doc_{index}" for index in range(21)],
        )


def test_chat_attachment_lists_are_deduplicated() -> None:
    payload = ChatStreamRequest(
        message="teste",
        attached_file_ids=["file_1", "file_1", "file_2"],
        attached_document_ids=["doc_1", "doc_1", "doc_2"],
        context_document_ids=["ctx_1", "ctx_1", "ctx_2"],
    )
    assert payload.attached_file_ids == ["file_1", "file_2"]
    assert payload.attached_document_ids == ["doc_1", "doc_2"]
    assert payload.context_document_ids == ["ctx_1", "ctx_2"]


def test_configured_pricing_requires_both_positive_costs() -> None:
    model = ModelConfig(id="openai/research", provider=ProviderName.openai, display_name="Research")
    assert has_configured_pricing(model) is False

    priced_model = model.model_copy(
        update={
            "input_token_cost_per_million": 10,
            "output_token_cost_per_million": 20,
        }
    )
    assert has_configured_pricing(priced_model) is True


def test_provider_models_are_enriched_with_local_pricing() -> None:
    openai_model = with_pricing(
        ProviderModel(id="gpt-5.5", provider=ProviderName.openai, display_name="gpt-5.5")
    )
    anthropic_model = with_pricing(
        ProviderModel(
            id="claude-sonnet-4-5-20250929",
            provider=ProviderName.anthropic,
            display_name="Claude Sonnet 4.5",
        )
    )
    google_model = with_pricing(
        ProviderModel(
            id="gemini-2.5-flash",
            provider=ProviderName.google,
            display_name="Gemini 2.5 Flash",
        )
    )

    assert openai_model.input_token_cost_per_million == 5
    assert openai_model.output_token_cost_per_million == 30
    assert anthropic_model.input_token_cost_per_million == 3
    assert anthropic_model.output_token_cost_per_million == 15
    assert google_model.input_token_cost_per_million == 0.3
    assert google_model.output_token_cost_per_million == 2.5
