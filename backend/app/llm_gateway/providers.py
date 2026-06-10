from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.core.contracts import ModelConfig, ProviderModel, ProviderName
from app.llm_gateway.pricing import with_pricing
from app.security.secrets import SecretStore, get_secret_store


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot run because credentials/model ids are missing."""


class ProviderExecutionError(RuntimeError):
    """Raised when a configured provider rejects or cannot complete a request."""


@dataclass(frozen=True)
class ProviderStreamEvent:
    kind: Literal["token", "reasoning_summary"]
    content: str


def token_event(content: str) -> ProviderStreamEvent:
    return ProviderStreamEvent(kind="token", content=content)


def reasoning_summary_event(content: str) -> ProviderStreamEvent:
    return ProviderStreamEvent(kind="reasoning_summary", content=content)


class LLMProvider(ABC):
    provider: ProviderName

    @abstractmethod
    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        reasoning_summary: Literal["off", "auto"] = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        """Stream model output token by token."""

    async def list_models(self) -> list[ProviderModel]:
        raise ProviderConfigurationError(
            f"Listagem de modelos não implementada para {self.provider.value}."
        )

    async def generate_image(self, model: ModelConfig, prompt: str) -> str:
        raise ProviderConfigurationError(
            f"Geração de imagem não implementada para {self.provider.value}."
        )

    # ``generate_title`` was removed in Onda 2.10 (ADR-014). The base
    # method and the per-provider overrides have been deleted; chat
    # titles must come from the user (Pydantic validator at
    # ``ChatSessionCreate`` + 422 in ``POST /api/chat/stream``).

    async def deep_research(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        max_tool_calls: int,
    ) -> AsyncIterator[str]:
        raise ProviderConfigurationError(
            f"Deep Research não implementado para {self.provider.value}."
        )

    async def generate_structured(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Single-shot call returning a JSON object that satisfies the schema.

        Default implementation rejects the call. Providers must opt-in by
        overriding this method.
        """
        raise ProviderConfigurationError(
            f"Saída estruturada não implementada para {self.provider.value}."
        )


# NOTE: there is a single dev/offline fallback in the codebase —
# ``app.judite.orchestrator.judite_dev_response`` — used by the chat stream
# when a real provider is misconfigured and ``settings.allow_dev_llm`` is on.
# A second, orphaned ``DevLLMProvider`` used to live here but was never
# registered in :class:`app.llm_gateway.gateway.LLMGateway` (which only wires
# openai/anthropic/google), so it was dead code duplicating the same intent.
# It was removed (architecture-map finding "fallback duplo de dev"); keep the
# dev fallback consolidated in ``judite_dev_response``.


class BaseRemoteProvider(LLMProvider):
    def __init__(self, secrets: SecretStore | None = None) -> None:
        self.secrets = secrets or get_secret_store()

    def api_key(self) -> str:
        key = self.secrets.get_api_key(self.provider)
        if not key:
            raise ProviderConfigurationError(f"API key não configurada para {self.provider.value}.")
        return key

    def provider_model_id(self, model: ModelConfig) -> str:
        if model.provider_model_id:
            return model.provider_model_id
        if "/" not in model.id and not model.id.endswith("default-chat"):
            return model.id
        raise ProviderConfigurationError(
            f"Modelo real do provedor não configurado para {model.display_name}."
        )

    def _common_payload(self, model: ModelConfig) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if model.temperature is not None:
            payload["temperature"] = model.temperature
        if model.top_p is not None:
            payload["top_p"] = model.top_p
        if model.stop_sequences:
            payload["stop"] = model.stop_sequences
        return payload


class OpenAIProvider(BaseRemoteProvider):
    provider = ProviderName.openai

    def _deep_research_prompt(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        instructions = "\n\n".join(
            message["content"] for message in messages if message["role"] == "system"
        ).strip()
        transcript = []
        for message in messages:
            if message["role"] not in {"user", "assistant"}:
                continue
            role = "Usuário" if message["role"] == "user" else "Assistente"
            transcript.append(f"{role}: {message['content']}")
        input_text = "\n\n".join(transcript).strip()
        if not input_text and messages:
            input_text = messages[-1]["content"]
        research_instructions = (
            "Conduza uma pesquisa aprofundada em português do Brasil. "
            "Priorize fontes recentes e confiáveis, separe fatos de inferências, "
            "inclua links/citações clicáveis quando disponíveis e sinalize lacunas."
        )
        if instructions:
            instructions = f"{instructions}\n\n{research_instructions}"
        else:
            instructions = research_instructions
        return instructions, input_text

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        if payload.get("output_text"):
            return str(payload["output_text"]).strip()

        parts = []
        sources: list[tuple[str, str]] = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") not in {"output_text", "text"}:
                    continue
                text = content.get("text") or ""
                if isinstance(text, dict):
                    text = text.get("value", "")
                if text:
                    parts.append(str(text))
                for annotation in content.get("annotations", []):
                    url = annotation.get("url")
                    if not url:
                        continue
                    title = annotation.get("title") or url
                    source = (str(title), str(url))
                    if source not in sources:
                        sources.append(source)

        text = "\n\n".join(parts).strip()
        if sources:
            source_lines = "\n".join(f"- [{title}]({url})" for title, url in sources[:20])
            text = f"{text}\n\nFontes:\n{source_lines}".strip()
        return text

    def _provider_error(self, exc: httpx.HTTPStatusError) -> ProviderExecutionError:
        try:
            detail = exc.response.json().get("error", {})
        except ValueError:
            detail = {}
        message = detail.get("message") or exc.response.reason_phrase or "erro sem mensagem"
        return ProviderExecutionError(f"OpenAI retornou erro {exc.response.status_code}: {message}")

    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        reasoning_summary: Literal["off", "auto"] = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        payload = {
            "model": provider_model_id,
            "input": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
                if message["role"] in {"system", "user", "assistant"}
            ],
            "stream": True,
        }
        payload.update(self._common_payload(model))
        if model.max_output_tokens:
            payload["max_output_tokens"] = model.max_output_tokens
        reasoning: dict[str, Any] = {}
        if model.reasoning_effort and model.reasoning_effort != "none":
            reasoning["effort"] = (
                "high" if model.reasoning_effort == "xhigh" else model.reasoning_effort
            )
        if reasoning_summary == "auto":
            reasoning["summary"] = "auto"
        if reasoning:
            payload["reasoning"] = reasoning
        if model.verbosity:
            payload.setdefault("text", {})["verbosity"] = model.verbosity
        if model.response_format == "json":
            payload.setdefault("text", {})["format"] = {"type": "json_object"}
        if model.tool_choice != "auto":
            payload["tool_choice"] = model.tool_choice
        payload["parallel_tool_calls"] = model.parallel_tool_calls
        if model.presence_penalty is not None:
            payload["presence_penalty"] = model.presence_penalty
        if model.frequency_penalty is not None:
            payload["frequency_penalty"] = model.frequency_penalty
        if model.seed is not None:
            payload["seed"] = model.seed
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", "https://api.openai.com/v1/responses", headers=headers, json=payload
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        response.raise_for_status()
                    summary_delta_seen = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line.removeprefix("data: ").strip()
                        if raw == "[DONE]" or not raw or raw.startswith(":"):
                            if raw == "[DONE]":
                                break
                            continue
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            # SSE keep-alive/comment ou frame parcial: ignore a linha
                            continue
                        event_type = data.get("type")
                        if event_type == "response.output_text.delta":
                            yield token_event(data.get("delta", ""))
                        elif event_type in {
                            "response.reasoning_summary_text.delta",
                            "response.reasoning_summary.delta",
                        }:
                            summary_delta_seen = True
                            summary_delta = data.get("delta") or data.get("text") or ""
                            if isinstance(summary_delta, dict):
                                summary_delta = (
                                    summary_delta.get("text") or summary_delta.get("content") or ""
                                )
                            if summary_delta:
                                yield reasoning_summary_event(str(summary_delta))
                        elif event_type in {
                            "response.reasoning_summary_text.done",
                            "response.reasoning_summary.done",
                        }:
                            summary_text = data.get("text") or data.get("summary") or ""
                            if summary_text and not summary_delta_seen:
                                yield reasoning_summary_event(str(summary_text))
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Falha de rede ao chamar OpenAI: {exc}") from exc

    async def generate_image(self, model: ModelConfig, prompt: str) -> str:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        payload = {
            "model": provider_model_id,
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations", headers=headers, json=payload
            )
            response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            raise ProviderConfigurationError("O provedor não retornou imagem.")
        first = data[0]
        if first.get("b64_json"):
            return f"![Imagem gerada](data:image/png;base64,{first['b64_json']})"
        if first.get("url"):
            return f"![Imagem gerada]({first['url']})"
        raise ProviderConfigurationError("Resposta de imagem sem URL ou base64.")

    # ``generate_title`` removed in Onda 2.10 (ADR-014). Auto-titulação
    # via OpenAI Responses API descontinuada — chats nascem com título
    # obrigatório fornecido pelo usuário.

    async def deep_research(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        max_tool_calls: int,
    ) -> AsyncIterator[str]:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        instructions, input_text = self._deep_research_prompt(messages)
        payload: dict[str, Any] = {
            "model": provider_model_id,
            "input": input_text,
            "instructions": instructions,
            "background": True,
            "tools": [{"type": "web_search_preview"}],
            "include": ["web_search_call.action.sources"],
            "max_tool_calls": max_tool_calls,
        }
        if model.max_output_tokens:
            payload["max_output_tokens"] = model.max_output_tokens
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                response_id = data.get("id")
                if data.get("status") == "completed":
                    yield self._extract_response_text(data)
                    return
                if not response_id:
                    raise ProviderConfigurationError("Deep Research não retornou id de resposta.")

                yield (
                    "Pesquisa aprofundada iniciada. "
                    "Vou consultar fontes externas e sintetizar a resposta "
                    f"(limite: {max_tool_calls} chamadas de ferramenta).\n\n"
                )
                # Teto configurável de polls (default 360 × 5s ≈ 30 min). O operador
                # pode encurtar via TRUTHS_FORGE_DEEP_RESEARCH_MAX_POLLS para não segurar
                # a request indefinidamente em aba abandonada.
                try:
                    max_polls = int(os.getenv("TRUTHS_FORGE_DEEP_RESEARCH_MAX_POLLS", "360"))
                except ValueError:
                    max_polls = 360
                if max_polls < 1:
                    max_polls = 1
                for attempt in range(max_polls):
                    await asyncio.sleep(5)
                    poll_response = await client.get(
                        f"https://api.openai.com/v1/responses/{response_id}",
                        headers=headers,
                    )
                    poll_response.raise_for_status()
                    poll_data = poll_response.json()
                    status = poll_data.get("status")
                    if status == "completed":
                        text = self._extract_response_text(poll_data)
                        if not text:
                            raise ProviderConfigurationError(
                                "Deep Research concluiu sem texto de saída."
                            )
                        yield text
                        return
                    if status in {"failed", "cancelled", "incomplete"}:
                        details = poll_data.get("error") or poll_data.get("incomplete_details")
                        raise ProviderConfigurationError(
                            f"Deep Research terminou com status {status}: {details}"
                        )
                    if attempt and attempt % 6 == 0:
                        yield "Ainda pesquisando e cruzando fontes...\n\n"
                raise ProviderConfigurationError(
                    "Tempo limite aguardando a conclusão do Deep Research."
                )
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Falha de rede ao chamar OpenAI: {exc}") from exc

    async def generate_structured(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        payload: dict[str, Any] = {
            "model": provider_model_id,
            "input": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
                if message["role"] in {"system", "user", "assistant"}
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        if model.max_output_tokens:
            payload["max_output_tokens"] = model.max_output_tokens
        if model.temperature is not None:
            payload["temperature"] = model.temperature
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            # F6: 180s — planos complexos com orçamento de saída maior demoram
            # mais (gpt-5-mini gasta tempo em reasoning antes de emitir o JSON).
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(
                f"Falha de rede ao gerar saída estruturada com OpenAI: {exc}"
            ) from exc

        text = self._extract_response_text(data)
        if not text:
            raise ProviderExecutionError("Resposta estruturada da OpenAI veio vazia.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderExecutionError(
                f"Resposta estruturada da OpenAI não é JSON válido: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderExecutionError("Saída estruturada precisa ser um objeto JSON na raiz.")
        return parsed

    async def list_models(self) -> list[ProviderModel]:
        headers = {"Authorization": f"Bearer {self.api_key()}"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.openai.com/v1/models", headers=headers)
            response.raise_for_status()
        models = []
        for item in response.json().get("data", []):
            created = item.get("created")
            created_at = (
                datetime.fromtimestamp(created, tz=UTC).isoformat()
                if isinstance(created, int)
                else None
            )
            models.append(
                with_pricing(
                    ProviderModel(
                        id=item["id"],
                        provider=self.provider,
                        display_name=item["id"],
                        owned_by=item.get("owned_by"),
                        created_at=created_at,
                    )
                )
            )
        return sorted(models, key=lambda item: item.id)


class AnthropicProvider(BaseRemoteProvider):
    provider = ProviderName.anthropic

    def _provider_error(self, exc: httpx.HTTPStatusError) -> ProviderExecutionError:
        try:
            detail = exc.response.json().get("error", {})
        except ValueError:
            detail = {}
        message = detail.get("message") or exc.response.reason_phrase or "erro sem mensagem"
        return ProviderExecutionError(
            f"Anthropic retornou erro {exc.response.status_code}: {message}"
        )

    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        reasoning_summary: Literal["off", "auto"] = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        system = "\n".join(
            message["content"] for message in messages if message["role"] == "system"
        )
        chat_messages = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message["role"] in {"user", "assistant"}
        ]
        payload = {
            "model": provider_model_id,
            "max_tokens": model.max_output_tokens or 2048,
            "messages": chat_messages,
            "stream": True,
        }
        common = self._common_payload(model)
        if "temperature" in common:
            payload["temperature"] = common["temperature"]
        if "top_p" in common:
            payload["top_p"] = common["top_p"]
        if model.top_k is not None:
            payload["top_k"] = model.top_k
        if model.stop_sequences:
            payload["stop_sequences"] = model.stop_sequences
        if model.reasoning_budget_tokens:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": model.reasoning_budget_tokens,
            }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line.removeprefix("data: ").strip()
                        if not raw or raw.startswith(":"):
                            continue
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            # SSE keep-alive/comment ou frame parcial: ignore a linha
                            continue
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield token_event(delta.get("text", ""))
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Falha de rede ao chamar Anthropic: {exc}") from exc

    async def list_models(self) -> list[ProviderModel]:
        headers = {
            "x-api-key": self.api_key(),
            "anthropic-version": "2023-06-01",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.anthropic.com/v1/models", headers=headers)
            response.raise_for_status()
        return [
            with_pricing(
                ProviderModel(
                    id=item["id"],
                    provider=self.provider,
                    display_name=item.get("display_name") or item["id"],
                    created_at=item.get("created_at"),
                )
            )
            for item in response.json().get("data", [])
        ]


class GoogleProvider(BaseRemoteProvider):
    provider = ProviderName.google

    def _provider_error(self, exc: httpx.HTTPStatusError) -> ProviderExecutionError:
        try:
            detail = exc.response.json().get("error", {})
        except ValueError:
            detail = {}
        message = detail.get("message") or exc.response.reason_phrase or "erro sem mensagem"
        return ProviderExecutionError(f"Google retornou erro {exc.response.status_code}: {message}")

    async def stream_chat(
        self,
        model: ModelConfig,
        messages: list[dict[str, str]],
        reasoning_summary: Literal["off", "auto"] = "off",
    ) -> AsyncIterator[ProviderStreamEvent]:
        api_key = self.api_key()
        provider_model_id = self.provider_model_id(model)
        contents = []
        for message in messages:
            if message["role"] not in {"user", "assistant"}:
                continue
            contents.append(
                {
                    "role": "model" if message["role"] == "assistant" else "user",
                    "parts": [{"text": message["content"]}],
                }
            )
        # A chave vai no header (x-goog-api-key), nunca na URL: assim ela não
        # vaza em mensagens de erro do httpx (que ecoam a URL completa).
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{provider_model_id}:streamGenerateContent?alt=sse"
        )
        generation_config: dict[str, Any] = {}
        if model.temperature is not None:
            generation_config["temperature"] = model.temperature
        if model.top_p is not None:
            generation_config["topP"] = model.top_p
        if model.top_k is not None:
            generation_config["topK"] = model.top_k
        if model.max_output_tokens:
            generation_config["maxOutputTokens"] = model.max_output_tokens
        if model.stop_sequences:
            generation_config["stopSequences"] = model.stop_sequences
        if model.response_format == "json":
            generation_config["responseMimeType"] = "application/json"
        if model.reasoning_budget_tokens is not None:
            generation_config["thinkingConfig"] = {"thinkingBudget": model.reasoning_budget_tokens}
        payload: dict[str, Any] = {"contents": contents}
        if generation_config:
            payload["generationConfig"] = generation_config
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line.removeprefix("data: ").strip()
                        if not raw or raw.startswith(":"):
                            continue
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            # SSE keep-alive/comment ou frame parcial: ignore a linha
                            continue
                        for candidate in data.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                if text := part.get("text"):
                                    yield token_event(text)
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Falha de rede ao chamar Google: {exc}") from exc

    async def list_models(self) -> list[ProviderModel]:
        api_key = self.api_key()
        # Chave no header (não na URL) para não vazar em mensagens de erro.
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {"x-goog-api-key": api_key}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        provider_models = []
        for item in response.json().get("models", []):
            name = item.get("name", "")
            model_id = name.removeprefix("models/")
            provider_models.append(
                with_pricing(
                    ProviderModel(
                        id=model_id,
                        provider=self.provider,
                        display_name=item.get("displayName") or model_id,
                        input_token_limit=item.get("inputTokenLimit"),
                        output_token_limit=item.get("outputTokenLimit"),
                        default_temperature=item.get("temperature"),
                        max_temperature=item.get("maxTemperature"),
                        default_top_p=item.get("topP"),
                        default_top_k=item.get("topK"),
                        supported_actions=item.get("supportedGenerationMethods", []),
                    )
                )
            )
        return provider_models
