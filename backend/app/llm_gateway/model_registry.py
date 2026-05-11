from __future__ import annotations

from app.core.contracts import Agent, ModelCapability, ModelConfig, ProviderName
from app.storage.store import get_store


class ModelRegistry:
    def list_enabled(self) -> list[ModelConfig]:
        return [model for model in get_store().list_models() if model.enabled]

    def get_default(self) -> ModelConfig:
        models = self.list_enabled()
        if not models:
            raise ValueError("Nenhum modelo habilitado.")
        for model in models:
            if model.default:
                return model
        return models[0]

    def get(self, model_id: str | None) -> ModelConfig:
        if not model_id:
            return self.get_default()
        for model in self.list_enabled():
            if model.id == model_id:
                return model
        return self.get_default()

    def get_image_model(self, preferred_provider: ProviderName | None = None) -> ModelConfig:
        image_models = [
            model
            for model in self.list_enabled()
            if ModelCapability.image_generation in model.capabilities
        ]
        if preferred_provider:
            for model in image_models:
                if model.provider == preferred_provider:
                    return model
        if image_models:
            return image_models[0]
        return self.get_default()

    def get_deep_research_model(
        self, preferred_provider: ProviderName | None = ProviderName.openai
    ) -> ModelConfig:
        research_models = [
            model
            for model in self.list_enabled()
            if ModelCapability.deep_research in model.capabilities
        ]
        if preferred_provider:
            for model in research_models:
                if model.provider == preferred_provider:
                    return model
        if research_models:
            return research_models[0]
        return self.get_default()

    def get_for_agent(
        self, agent: Agent | None, fallback_model_id: str | None = None
    ) -> ModelConfig:
        base = self.get(agent.model_id if agent and agent.model_id else fallback_model_id)
        if agent is None:
            return base
        llm = agent.llm_config
        return base.model_copy(
            update={
                "id": agent.model_id or base.id,
                "provider": llm.provider,
                "display_name": llm.display_name
                or f"{agent.name} / {llm.provider_model_id or base.display_name}",
                "provider_model_id": llm.provider_model_id or base.provider_model_id,
                "input_token_cost_per_million": (
                    llm.input_token_cost_per_million
                    if llm.input_token_cost_per_million is not None
                    else base.input_token_cost_per_million
                ),
                "output_token_cost_per_million": (
                    llm.output_token_cost_per_million
                    if llm.output_token_cost_per_million is not None
                    else base.output_token_cost_per_million
                ),
                "temperature": llm.temperature,
                "top_p": llm.top_p,
                "top_k": llm.top_k,
                "max_output_tokens": llm.max_output_tokens,
                "reasoning_effort": llm.reasoning_effort,
                "reasoning_budget_tokens": llm.reasoning_budget_tokens,
                "verbosity": llm.verbosity,
                "response_format": llm.response_format,
                "tool_choice": llm.tool_choice,
                "parallel_tool_calls": llm.parallel_tool_calls,
                "presence_penalty": llm.presence_penalty,
                "frequency_penalty": llm.frequency_penalty,
                "seed": llm.seed,
                "stop_sequences": llm.stop_sequences,
            }
        )
