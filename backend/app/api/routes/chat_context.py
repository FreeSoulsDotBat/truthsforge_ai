"""RAG context retrieval and knowledge-base resolution for the chat routes.

Extracted from the ``chat.py`` monolith (architecture-map finding "monólitos
de borda"). Groups the distinct RAG concern: resolving which knowledge bases
a runtime may use, mapping ``@folder`` mentions, selecting context documents
and searching the vector store for project/knowledge-base snippets injected
into the prompt.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.contracts import (
    MAX_CONTEXT_KNOWLEDGE_BASE_IDS,
    Agent,
    Document,
    KnowledgeBase,
    KnowledgeBaseDocument,
)
from app.rag.embeddings import embed_text
from app.rag.vector_store import QdrantVectorStore

DOCUMENT_COLLECTION = "truths_forge_documents"
MAX_CONTEXT_DOCUMENTS = 20
FOLDER_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_./-]+)")


def _folder_lookup_key(project_name: str, folder_path: str) -> str:
    normalized_project = project_name.strip().replace(" ", "_")
    normalized_path = folder_path.strip().replace(" ", "_")
    return f"{normalized_project}/{normalized_path}".strip("/").lower()


def _mentioned_folder_ids(
    message: str,
    *,
    projects_by_id: dict[str, Any],
    project_folders: list[Any],
) -> set[str]:
    mentions = {
        match.group(1).strip().replace("\\", "/").replace(" ", "_").lower()
        for match in FOLDER_MENTION_PATTERN.finditer(message)
        if match.group(1).strip()
    }
    if not mentions:
        return set()

    folder_id_by_key: dict[str, str] = {}
    for folder in project_folders:
        project = projects_by_id.get(folder.project_id)
        if project is None:
            continue
        key = _folder_lookup_key(project.name, folder.path)
        folder_id_by_key[key] = folder.id
    return {folder_id for key, folder_id in folder_id_by_key.items() if key in mentions}


def _indexed_documents_for_projects(
    documents: list[Document], project_ids: set[str]
) -> list[Document]:
    return [
        document
        for document in documents
        if document.indexed
        and str(document.index_status) == "completed"
        and document.project_id in project_ids
    ]


def _select_context_documents(
    *,
    documents: list[Document],
    selected_document_ids: list[str],
) -> list[Document]:
    if not selected_document_ids:
        return []
    allowed = set(selected_document_ids[:MAX_CONTEXT_DOCUMENTS])
    selected = [document for document in documents if document.id in allowed]
    selected.sort(key=lambda document: selected_document_ids.index(document.id))
    return selected[:MAX_CONTEXT_DOCUMENTS]


def _normalize_knowledge_base_ids(
    knowledge_base_ids: list[str],
    *,
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    known_ids = {knowledge_base.id for knowledge_base in knowledge_bases if knowledge_base.enabled}
    normalized: list[str] = []
    for raw_id in knowledge_base_ids:
        if raw_id not in known_ids or raw_id in normalized:
            continue
        normalized.append(raw_id)
    return normalized[:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]


def _allowed_knowledge_base_ids_for_runtime(
    *,
    project_id: str,
    projects_by_id: dict[str, Any],
    primary_agent: Agent | None,
    target_agent: Agent | None,
    support_agents: list[Agent],
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    ordered: list[str] = []
    project = projects_by_id.get(project_id)
    if project is not None:
        ordered.extend(getattr(project.context, "knowledge_base_ids", []) or [])
    for agent in [primary_agent, target_agent, *support_agents]:
        if agent is None:
            continue
        ordered.extend(agent.knowledge_base_ids or [])
    return _normalize_knowledge_base_ids(ordered, knowledge_bases=knowledge_bases)


def _knowledge_base_ids_for_runtime(
    *,
    project_id: str,
    projects_by_id: dict[str, Any],
    primary_agent: Agent | None,
    target_agent: Agent | None,
    support_agents: list[Agent],
    payload_ids: list[str],
    session_ids: list[str],
    knowledge_bases: list[KnowledgeBase],
) -> list[str]:
    allowed_ids = _allowed_knowledge_base_ids_for_runtime(
        project_id=project_id,
        projects_by_id=projects_by_id,
        primary_agent=primary_agent,
        target_agent=target_agent,
        support_agents=support_agents,
        knowledge_bases=knowledge_bases,
    )
    allowed_set = set(allowed_ids)
    if payload_ids:
        return [
            knowledge_base_id
            for knowledge_base_id in _normalize_knowledge_base_ids(
                payload_ids, knowledge_bases=knowledge_bases
            )
            if knowledge_base_id in allowed_set
        ][:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]
    if session_ids:
        return [
            knowledge_base_id
            for knowledge_base_id in _normalize_knowledge_base_ids(
                session_ids, knowledge_bases=knowledge_bases
            )
            if knowledge_base_id in allowed_set
        ][:MAX_CONTEXT_KNOWLEDGE_BASE_IDS]

    return allowed_ids


def _knowledge_base_document_index(
    items: list[KnowledgeBaseDocument], knowledge_base_ids: set[str]
) -> dict[str, list[KnowledgeBaseDocument]]:
    indexed: dict[str, list[KnowledgeBaseDocument]] = {}
    for item in items:
        if not item.enabled or item.knowledge_base_id not in knowledge_base_ids:
            continue
        indexed.setdefault(item.document_id, []).append(item)
    return indexed


async def _search_project_context(
    *,
    message: str,
    project_ids: set[str],
    selected_document_ids: set[str],
    max_documents: int,
    folder_ids: set[str],
) -> list[dict[str, str]]:
    if not message.strip():
        return []
    vector_store = QdrantVectorStore()
    try:
        results = await vector_store.search(
            DOCUMENT_COLLECTION,
            embed_text(message),
            max(8, min(80, max_documents * 4)),
        )
    except Exception:
        return []

    snippets: list[dict[str, str]] = []
    for item in results:
        raw_payload = item.get("payload") or {}
        raw_project_id = str(raw_payload.get("project_id") or "")
        if project_ids and raw_project_id not in project_ids:
            continue
        raw_folder_id = raw_payload.get("folder_id")
        if folder_ids and str(raw_folder_id or "") not in folder_ids:
            continue
        raw_document_id = str(raw_payload.get("document_id") or "")
        if selected_document_ids and raw_document_id not in selected_document_ids:
            continue
        content = str(raw_payload.get("content") or "").strip()
        if not content:
            continue
        snippets.append(
            {
                "title": str(raw_payload.get("title") or "Documento"),
                "content": content,
                "project_id": str(raw_payload.get("project_id") or ""),
                "folder_id": str(raw_folder_id or ""),
                "score": f"{float(item.get('score', 0)):.3f}",
            }
        )
        if len(snippets) >= max_documents:
            break
    return snippets


async def _search_knowledge_base_context(
    *,
    message: str,
    knowledge_bases: list[KnowledgeBase],
    knowledge_base_items: list[KnowledgeBaseDocument],
    documents: list[Document],
    folder_ids: set[str],
) -> list[dict[str, str]]:
    if not message.strip() or not knowledge_bases:
        return []

    active_bases = [knowledge_base for knowledge_base in knowledge_bases if knowledge_base.enabled]
    active_base_ids = {knowledge_base.id for knowledge_base in active_bases}
    items_by_document_id = _knowledge_base_document_index(knowledge_base_items, active_base_ids)
    if not items_by_document_id:
        return []

    document_by_id = {
        document.id: document
        for document in documents
        if document.indexed and str(document.index_status) == "completed"
    }
    active_bases_by_id = {knowledge_base.id: knowledge_base for knowledge_base in active_bases}
    base_document_hits: dict[str, set[str]] = {
        knowledge_base.id: set() for knowledge_base in active_bases
    }
    document_chunk_hits: dict[tuple[str, str], int] = {}
    max_documents_total = min(
        MAX_CONTEXT_DOCUMENTS,
        sum(knowledge_base.max_documents_per_query for knowledge_base in active_bases),
    )
    vector_limit = max(8, min(120, max_documents_total * 5))

    vector_store = QdrantVectorStore()
    try:
        results = await vector_store.search(DOCUMENT_COLLECTION, embed_text(message), vector_limit)
    except Exception:
        return []

    ranked: list[tuple[float, dict[str, str]]] = []
    for item in results:
        raw_payload = item.get("payload") or {}
        raw_document_id = str(raw_payload.get("document_id") or "")
        document = document_by_id.get(raw_document_id)
        if document is None:
            continue
        if folder_ids and str(raw_payload.get("folder_id") or "") not in folder_ids:
            continue
        memberships = items_by_document_id.get(raw_document_id, [])
        if not memberships:
            continue

        selected_membership: KnowledgeBaseDocument | None = None
        selected_base: KnowledgeBase | None = None
        for membership in sorted(memberships, key=lambda value: value.priority, reverse=True):
            candidate_base = active_bases_by_id.get(membership.knowledge_base_id)
            if candidate_base is None:
                continue
            base_documents = base_document_hits[candidate_base.id]
            document_already_counted = document.id in base_documents
            if (
                not document_already_counted
                and len(base_documents) >= candidate_base.max_documents_per_query
            ):
                continue
            chunk_key = (candidate_base.id, document.id)
            if document_chunk_hits.get(chunk_key, 0) >= candidate_base.max_chunks_per_document:
                continue
            selected_membership = membership
            selected_base = candidate_base
            break
        if selected_membership is None or selected_base is None:
            continue

        content = str(raw_payload.get("content") or "").strip()
        if not content:
            continue
        base_document_hits[selected_base.id].add(document.id)
        chunk_key = (selected_base.id, document.id)
        document_chunk_hits[chunk_key] = document_chunk_hits.get(chunk_key, 0) + 1
        vector_score = float(item.get("score", 0))
        priority_boost = selected_membership.priority * 0.015
        pinned_boost = 0.03 if document.pinned else 0
        score = vector_score + priority_boost + pinned_boost
        ranked.append(
            (
                score,
                {
                    "title": str(raw_payload.get("title") or document.title or "Documento"),
                    "content": content,
                    "knowledge_base_id": selected_base.id,
                    "knowledge_base_name": selected_base.name,
                    "document_id": document.id,
                    "folder_id": str(raw_payload.get("folder_id") or ""),
                    "score": f"{score:.3f}",
                    "vector_score": f"{vector_score:.3f}",
                },
            )
        )
        if len(ranked) >= MAX_CONTEXT_DOCUMENTS:
            break

    ranked.sort(key=lambda value: value[0], reverse=True)
    return [item for _score, item in ranked[:MAX_CONTEXT_DOCUMENTS]]


__all__ = [
    "DOCUMENT_COLLECTION",
    "FOLDER_MENTION_PATTERN",
    "MAX_CONTEXT_DOCUMENTS",
    "_allowed_knowledge_base_ids_for_runtime",
    "_folder_lookup_key",
    "_indexed_documents_for_projects",
    "_knowledge_base_document_index",
    "_knowledge_base_ids_for_runtime",
    "_mentioned_folder_ids",
    "_normalize_knowledge_base_ids",
    "_search_knowledge_base_context",
    "_search_project_context",
    "_select_context_documents",
]
