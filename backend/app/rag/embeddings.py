from __future__ import annotations

from functools import lru_cache
from hashlib import blake2b
from math import sqrt
from typing import Protocol

from app.core.config import settings

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

VECTOR_SIZE = settings.rag_embedding_dimensions
HASH_FALLBACK_BACKEND = "hash_fallback"
SENTENCE_TRANSFORMERS_BACKEND = "sentence_transformers"


class EmbeddingModel(Protocol):
    def encode(self, text: str, normalize_embeddings: bool = True) -> object: ...


@lru_cache(maxsize=1)
def _local_model() -> EmbeddingModel | None:
    if settings.rag_embedding_backend == "hash":
        return None
    if SentenceTransformer is None:
        return None
    try:
        return SentenceTransformer(settings.rag_embedding_model)
    except Exception:
        return None


def _normalize(values: list[float]) -> list[float]:
    norm = sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [round(value / norm, 6) for value in values]


def _coerce_vector(raw_vector: object, dimensions: int) -> list[float]:
    if hasattr(raw_vector, "tolist"):
        raw_vector = raw_vector.tolist()
    if not isinstance(raw_vector, list):
        return []
    values = [float(value) for value in raw_vector if isinstance(value, int | float)]
    if not values:
        return []
    if len(values) >= dimensions:
        return _normalize(values[:dimensions])
    return _normalize([*values, *([0.0] * (dimensions - len(values)))])


def embedding_backend_name() -> str:
    if _local_model() is not None:
        return SENTENCE_TRANSFORMERS_BACKEND
    return HASH_FALLBACK_BACKEND


def embedding_model_name() -> str:
    if _local_model() is not None:
        return settings.rag_embedding_model
    return "deterministic-blake2b"


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    values = [0.0] * dimensions
    tokens = [token.strip().lower() for token in text.split() if token.strip()]
    if not tokens:
        return values

    for token in tokens:
        digest = blake2b(token.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1 if digest[2] % 2 == 0 else -1
        weight = 1 + digest[3] / 255
        values[index] += sign * weight

    return _normalize(values)


def embed_text(text: str, dimensions: int = VECTOR_SIZE) -> list[float]:
    normalized = text.strip()
    if not normalized:
        return [0.0] * dimensions

    model = _local_model()
    if model is not None:
        vector = _coerce_vector(model.encode(normalized, normalize_embeddings=True), dimensions)
        if vector:
            return vector
    return _hash_embedding(normalized, dimensions)
