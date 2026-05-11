from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

from app.core.contracts import ModelConfig, ProviderModel, ProviderName
from app.llm_gateway.providers import (
    AnthropicProvider,
    GoogleProvider,
    LLMProvider,
    OpenAIProvider,
    ProviderStreamEvent,
)


class LLMGateway:
    def __init__(self) -> None:
        self.providers: dict[ProviderName, LLMProvider] = {
            ProviderName.openai: OpenAIProvider(),
            ProviderName.anthropic: AnthropicProvider(),
            ProviderName.google: GoogleProvider(),
        }

    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        reasoning_summary: Literal["off", "auto"] = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        provider = self.providers[model.provider]
        async for event in provider.stream_chat(model, messages, reasoning_summary):
            yield event

    async def list_models(self, provider_name: ProviderName) -> list[ProviderModel]:
        return await self.providers[provider_name].list_models()

    async def generate_image(self, model: ModelConfig, prompt: str) -> str:
        return await self.providers[model.provider].generate_image(model, prompt)

    async def generate_title(self, model: ModelConfig, messages: list[dict[str, str]]) -> str:
        return await self.providers[model.provider].generate_title(model, messages)

    async def deep_research(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        max_tool_calls: int,
    ) -> AsyncIterator[str]:
        async for token in self.providers[model.provider].deep_research(
            model,
            messages,
            max_tool_calls,
        ):
            yield token

    async def generate_structured(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.providers[model.provider].generate_structured(
            model, messages, schema_name, schema
        )
