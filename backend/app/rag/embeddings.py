from __future__ import annotations

from hashlib import blake2b
from math import sqrt

VECTOR_SIZE = 64


def embed_text(text: str, dimensions: int = VECTOR_SIZE) -> list[float]:
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

    norm = sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [round(value / norm, 6) for value in values]
