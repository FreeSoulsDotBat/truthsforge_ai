from fastapi import APIRouter, HTTPException

from app.core.contracts import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentUpdate,
    KnowledgeBaseUpdate,
)
from app.storage.store import get_store

router = APIRouter()


@router.get("", response_model=list[KnowledgeBase])
def list_knowledge_bases() -> list[KnowledgeBase]:
    store = get_store()
    if not hasattr(store, "list_knowledge_bases"):
        return []
    return store.list_knowledge_bases()


@router.post("", response_model=KnowledgeBase)
def create_knowledge_base(payload: KnowledgeBaseCreate) -> KnowledgeBase:
    store = get_store()
    if not hasattr(store, "create_knowledge_base"):
        raise HTTPException(status_code=501, detail="Bases de conhecimento não suportadas.")
    return store.create_knowledge_base(payload)


@router.put("/{knowledge_base_id}", response_model=KnowledgeBase)
def update_knowledge_base(knowledge_base_id: str, payload: KnowledgeBaseUpdate) -> KnowledgeBase:
    store = get_store()
    if not hasattr(store, "update_knowledge_base"):
        raise HTTPException(status_code=501, detail="Bases de conhecimento não suportadas.")
    return store.update_knowledge_base(knowledge_base_id, payload)


@router.delete("/{knowledge_base_id}", response_model=KnowledgeBase)
def delete_knowledge_base(knowledge_base_id: str) -> KnowledgeBase:
    store = get_store()
    if not hasattr(store, "delete_knowledge_base"):
        raise HTTPException(status_code=501, detail="Bases de conhecimento não suportadas.")
    deleted = store.delete_knowledge_base(knowledge_base_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Base de conhecimento não encontrada.")
    return deleted


@router.get("/documents", response_model=list[KnowledgeBaseDocument])
def list_all_knowledge_base_documents() -> list[KnowledgeBaseDocument]:
    store = get_store()
    if not hasattr(store, "list_knowledge_base_documents"):
        return []
    return store.list_knowledge_base_documents()


@router.get("/{knowledge_base_id}/documents", response_model=list[KnowledgeBaseDocument])
def list_knowledge_base_documents(knowledge_base_id: str) -> list[KnowledgeBaseDocument]:
    store = get_store()
    if not hasattr(store, "list_knowledge_base_documents"):
        return []
    return store.list_knowledge_base_documents(knowledge_base_id)


@router.post("/{knowledge_base_id}/documents", response_model=KnowledgeBaseDocument)
def add_knowledge_base_document(
    knowledge_base_id: str, payload: KnowledgeBaseDocumentCreate
) -> KnowledgeBaseDocument:
    store = get_store()
    if not hasattr(store, "add_knowledge_base_document"):
        raise HTTPException(status_code=501, detail="Itens de base não suportados.")
    try:
        return store.add_knowledge_base_document(knowledge_base_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Base ou documento não encontrado.") from exc


@router.put("/documents/{item_id}", response_model=KnowledgeBaseDocument)
def update_knowledge_base_document(
    item_id: str, payload: KnowledgeBaseDocumentUpdate
) -> KnowledgeBaseDocument:
    store = get_store()
    if not hasattr(store, "update_knowledge_base_document"):
        raise HTTPException(status_code=501, detail="Itens de base não suportados.")
    try:
        return store.update_knowledge_base_document(item_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Item de base não encontrado.") from exc


@router.delete("/{knowledge_base_id}/documents/{document_id}", response_model=KnowledgeBaseDocument)
def remove_knowledge_base_document(
    knowledge_base_id: str, document_id: str
) -> KnowledgeBaseDocument:
    store = get_store()
    if not hasattr(store, "remove_knowledge_base_document"):
        raise HTTPException(status_code=501, detail="Itens de base não suportados.")
    deleted = store.remove_knowledge_base_document(knowledge_base_id, document_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Item de base não encontrado.")
    return deleted
