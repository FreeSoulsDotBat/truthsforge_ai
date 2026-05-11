from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.core.config import settings
from app.rag.embeddings import VECTOR_SIZE


class VectorStore(ABC):
    @abstractmethod
    async def upsert_chunks(self, collection: str, chunks: list[dict[str, Any]]) -> None:
        """Persist embedded chunks in the vector index."""

    @abstractmethod
    async def search(
        self, collection: str, vector: list[float], limit: int = 8
    ) -> list[dict[str, Any]]:
        """Search indexed chunks by vector similarity."""

    @abstractmethod
    async def delete_document_chunks(self, collection: str, document_id: str) -> None:
        """Delete all chunks for a document."""


@dataclass
class QdrantVectorStore(VectorStore):
    url: str = settings.qdrant_url
    vector_size: int = VECTOR_SIZE

    async def _ensure_collection(self, client: httpx.AsyncClient, collection: str) -> None:
        response = await client.get(f"/collections/{collection}")
        if response.status_code == 200:
            return
        if response.status_code != 404:
            response.raise_for_status()
        create = await client.put(
            f"/collections/{collection}",
            json={"vectors": {"size": self.vector_size, "distance": "Cosine"}},
        )
        create.raise_for_status()

    async def upsert_chunks(self, collection: str, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        async with httpx.AsyncClient(base_url=self.url, timeout=10) as client:
            await self._ensure_collection(client, collection)
            points = [
                {
                    "id": str(uuid5(NAMESPACE_URL, chunk["id"])),
                    "vector": chunk["vector"],
                    "payload": chunk["payload"],
                }
                for chunk in chunks
            ]
            response = await client.put(
                f"/collections/{collection}/points",
                params={"wait": "true"},
                json={"points": points},
            )
            response.raise_for_status()

    async def search(
        self, collection: str, vector: list[float], limit: int = 8
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.url, timeout=10) as client:
            await self._ensure_collection(client, collection)
            response = await client.post(
                f"/collections/{collection}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True},
            )
            response.raise_for_status()
            return response.json().get("result", [])

    async def delete_document_chunks(self, collection: str, document_id: str) -> None:
        async with httpx.AsyncClient(base_url=self.url, timeout=10) as client:
            await self._ensure_collection(client, collection)
            response = await client.post(
                f"/collections/{collection}/points/delete",
                params={"wait": "true"},
                json={
                    "filter": {
                        "must": [
                            {
                                "key": "document_id",
                                "match": {"value": document_id},
                            }
                        ]
                    }
                },
            )
            response.raise_for_status()
