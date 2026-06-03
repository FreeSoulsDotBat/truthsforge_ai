"""Montagem de mensagens multimodais (texto + imagem) por provedor (F4).

O contrato do gateway aceita ``content`` como ``str`` **ou** uma lista de
blocos. Cada provedor tem um formato próprio de bloco de imagem:

* **Anthropic** — ``{"type": "image", "source": {"type": "base64", ...}}``
* **OpenAI** (Responses API) — ``{"type": "input_image", "image_url": "data:..."}``
* **Google** — ``{"inline_data": {"mime_type": ..., "data": ...}}``

Estas funções produzem o shape correto e preservam o caminho text-only
(``str`` continua válido — sem imagens, devolvemos o texto cru e nada muda
para o fluxo de chat existente).

Os providers do gateway repassam ``message["content"]`` verbatim para a API,
então basta o caller montar o bloco certo para o provedor do modelo escolhido.
"""

from __future__ import annotations

import base64
from typing import Any

from app.core.contracts import ProviderName

_MEDIA_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def media_type_for(filename: str | None, fallback: str = "image/png") -> str:
    """Deduz o media type de uma imagem pelo nome do arquivo."""
    name = (filename or "").lower()
    for suffix, media in _MEDIA_BY_SUFFIX.items():
        if name.endswith(suffix):
            return media
    return fallback


def supports_image_blocks(provider: ProviderName) -> bool:
    """True quando sabemos montar blocos de imagem para o provedor.

    Google fica de fora por enquanto (o provider serializa ``parts`` de forma
    diferente); cai no caminho text-only sem quebrar.
    """
    return provider in {ProviderName.anthropic, ProviderName.openai}


def text_block(provider: ProviderName, text: str) -> dict[str, Any]:
    if provider == ProviderName.openai:
        return {"type": "input_text", "text": text}
    # anthropic (e default)
    return {"type": "text", "text": text}


def image_block(provider: ProviderName, image_bytes: bytes, *, media_type: str) -> dict[str, Any]:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    if provider == ProviderName.openai:
        return {
            "type": "input_image",
            "image_url": f"data:{media_type};base64,{b64}",
        }
    # anthropic (e default)
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64},
    }


def user_message_with_images(
    provider: ProviderName,
    text: str,
    images: list[tuple[bytes, str]],
) -> dict[str, Any]:
    """Mensagem ``role=user`` com texto + imagens.

    ``images`` é uma lista de ``(bytes, media_type)``. Sem imagens (ou provedor
    sem suporte a blocos), devolve ``content`` como ``str`` — caminho text-only
    intacto.
    """
    if not images or not supports_image_blocks(provider):
        return {"role": "user", "content": text}
    blocks: list[dict[str, Any]] = [text_block(provider, text)]
    for image_bytes, media_type in images:
        blocks.append(image_block(provider, image_bytes, media_type=media_type))
    return {"role": "user", "content": blocks}
