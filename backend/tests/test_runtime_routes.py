import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_provider_settings_routes_are_exposed() -> None:
    client = TestClient(app)
    response = client.get("/api/settings/providers")

    assert response.status_code == 200
    providers = {item["provider"] for item in response.json()}
    assert providers == {"openai", "anthropic", "google"}


def test_cost_usage_route_is_exposed() -> None:
    client = TestClient(app)
    response = client.get("/api/cost/usage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monthly_budget_brl"] >= 0
    assert payload["remaining_budget_brl"] >= 0
    assert "request_count" in payload


def test_openapi_contains_runtime_routes() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/settings/providers" in paths
    assert "/api/cost/usage" in paths
    assert "/api/documents/text" in paths
    assert "/api/documents/search" in paths
    assert "/api/projects" in paths
    assert "/api/projects/folders" in paths
    assert "/api/imports/chatgpt" in paths
    assert "/api/imports/chatgpt/from-file/{file_id}" in paths
    assert "/api/files/page" in paths
    assert "/api/documents/page" in paths
    assert "/api/documents/batch" in paths
    assert "/api/knowledge-bases" in paths
    assert "/api/knowledge-bases/documents" in paths
    assert "/api/knowledge-bases/{knowledge_base_id}/documents" in paths
    assert "/api/3d/capabilities" in paths
    assert "/api/3d/plans" in paths
    assert "/api/3d/plans/{plan_id}/execute" in paths
    assert "/api/files/{file_id}/content" in paths
    assert "/api/chat/sessions/{session_id}" in paths
    assert "delete" in paths["/api/chat/sessions/{session_id}"]


def test_chat_session_can_be_deleted() -> None:
    client = TestClient(app)
    created = client.post("/api/chat/sessions", json={"title": "Excluir sessão"})
    assert created.status_code == 200
    session_id = created.json()["id"]

    deleted = client.delete(f"/api/chat/sessions/{session_id}?delete_files=true")
    assert deleted.status_code == 200
    payload = deleted.json()
    assert payload["session_id"] == session_id
    assert isinstance(payload["deleted_file_ids"], list)

    missing = client.get(f"/api/chat/sessions/{session_id}")
    assert missing.status_code == 404


def test_new_chat_session_starts_as_empty_draft() -> None:
    client = TestClient(app)
    created = client.post("/api/chat/sessions", json={"title": "Novo chat"})

    assert created.status_code == 200
    payload = created.json()
    assert payload["metadata"]["is_empty_draft"] is True
    assert payload["project_id"] == "project_general"


def test_file_upload_creates_document_and_triggers_indexing() -> None:
    client = TestClient(app)
    filename = f"auto-index-{uuid4().hex}.txt"
    uploaded = client.post(
        "/api/files/upload",
        params={"source": "upload"},
        files={"file": (filename, b"linha 1\nlinha 2", "text/plain")},
    )
    assert uploaded.status_code == 201
    file_id = uploaded.json()["id"]

    document = None
    deadline = time.time() + 8
    while time.time() < deadline:
        listed = client.get("/api/documents")
        assert listed.status_code == 200
        document = next(
            (item for item in listed.json() if item.get("metadata", {}).get("file_id") == file_id),
            None,
        )
        if document and document.get("index_status") in {"completed", "failed"}:
            break
        time.sleep(0.2)

    assert document is not None
    assert document["metadata"]["file_id"] == file_id
    assert document["index_status"] in {"completed", "failed", "running"}


def test_files_page_supports_pagination_and_filters() -> None:
    client = TestClient(app)
    prefix = f"paged-{uuid4().hex}"
    file_a = f"{prefix}-a.txt"
    file_b = f"{prefix}-b.txt"
    upload_a = client.post(
        "/api/files/upload",
        params={"source": "upload"},
        files={"file": (file_a, b"a", "text/plain")},
    )
    upload_b = client.post(
        "/api/files/upload",
        params={"source": "chat_attachment"},
        files={"file": (file_b, b"b", "text/plain")},
    )
    assert upload_a.status_code == 201
    assert upload_b.status_code == 201

    paged = client.get("/api/files/page", params={"limit": 1, "offset": 0, "query": prefix})
    assert paged.status_code == 200
    payload = paged.json()
    assert payload["limit"] == 1
    assert payload["total"] >= 2
    assert isinstance(payload["items"], list)
    assert "has_more" in payload

    source_filtered = client.get(
        "/api/files/page",
        params={"limit": 10, "offset": 0, "query": prefix, "source": "chat_attachment"},
    )
    assert source_filtered.status_code == 200
    filtered_payload = source_filtered.json()
    assert all(item["source"] == "chat_attachment" for item in filtered_payload["items"])


def test_documents_page_supports_pagination() -> None:
    client = TestClient(app)
    title = f"doc-page-{uuid4().hex}"
    created = client.post(
        "/api/documents/text",
        json={
            "title": title,
            "content": "conteudo de teste paginado",
            "source_type": "txt",
            "tags": ["page-test"],
        },
    )
    assert created.status_code == 200

    paged = client.get("/api/documents/page", params={"limit": 1, "offset": 0, "query": "doc-page"})
    assert paged.status_code == 200
    payload = paged.json()
    assert payload["limit"] == 1
    assert payload["total"] >= 1
    assert isinstance(payload["items"], list)
    assert "has_more" in payload


def test_documents_batch_returns_requested_documents_in_order() -> None:
    client = TestClient(app)
    first = client.post(
        "/api/documents/text",
        json={
            "title": f"batch-first-{uuid4().hex}",
            "content": "primeiro documento",
            "source_type": "txt",
        },
    )
    second = client.post(
        "/api/documents/text",
        json={
            "title": f"batch-second-{uuid4().hex}",
            "content": "segundo documento",
            "source_type": "txt",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    response = client.post(
        "/api/documents/batch",
        json={"ids": [second_id, "missing", first_id, second_id]},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [second_id, first_id]


def test_knowledge_base_can_link_indexed_document() -> None:
    client = TestClient(app)
    title = f"kb-doc-{uuid4().hex}"
    created_document = client.post(
        "/api/documents/text",
        json={
            "title": title,
            "content": "contexto de base de conhecimento",
            "source_type": "txt",
            "tags": ["kb-test"],
        },
    )
    assert created_document.status_code == 200
    document_id = created_document.json()["id"]

    created_base = client.post(
        "/api/knowledge-bases",
        json={
            "name": f"Base {uuid4().hex}",
            "description": "Base de teste",
            "scope": "Somente documentos de teste automatizado",
            "tags": ["test"],
            "max_documents_per_query": 5,
            "max_chunks_per_document": 2,
        },
    )
    assert created_base.status_code == 200
    knowledge_base_id = created_base.json()["id"]

    linked = client.post(
        f"/api/knowledge-bases/{knowledge_base_id}/documents",
        json={"document_id": document_id, "priority": 2, "tags": ["selecionado"]},
    )
    assert linked.status_code == 200
    assert linked.json()["knowledge_base_id"] == knowledge_base_id
    assert linked.json()["document_id"] == document_id

    listed = client.get(f"/api/knowledge-bases/{knowledge_base_id}/documents")
    assert listed.status_code == 200
    assert any(item["document_id"] == document_id for item in listed.json())

    listed_all = client.get("/api/knowledge-bases/documents")
    assert listed_all.status_code == 200
    assert any(
        item["knowledge_base_id"] == knowledge_base_id and item["document_id"] == document_id
        for item in listed_all.json()
    )

    search = client.post(
        "/api/documents/search",
        json={"query": "base de conhecimento", "knowledge_base_ids": [knowledge_base_id]},
    )
    assert search.status_code == 200


def test_image_generation_without_pricing_is_blocked_by_cost_governor() -> None:
    client = TestClient(app)
    model_id = f"test/image-no-price-{uuid4().hex}"
    created_model = client.post(
        "/api/models",
        json={
            "id": model_id,
            "provider": "openai",
            "display_name": "Imagem sem preço",
            "provider_model_id": "test-image-no-price",
            "enabled": True,
            "default": False,
            "capabilities": ["image_generation"],
        },
    )
    assert created_model.status_code == 200

    response = client.post(
        "/api/chat/stream",
        json={
            "message": "gere uma imagem de teste",
            "response_mode": "image",
            "image_model_id": model_id,
        },
    )

    assert response.status_code == 402
    assert "image_generation_pricing_required" in response.text


def test_attached_document_from_another_project_is_rejected() -> None:
    client = TestClient(app)
    project_a = client.post(
        "/api/projects",
        json={"name": f"Projeto A {uuid4().hex}", "description": "origem"},
    )
    project_b = client.post(
        "/api/projects",
        json={"name": f"Projeto B {uuid4().hex}", "description": "destino"},
    )
    assert project_a.status_code == 200
    assert project_b.status_code == 200
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    agent = client.post(
        "/api/agents",
        json={
            "name": f"Agente {uuid4().hex}",
            "description": "Agente de teste",
            "system_prompt": "Responda somente para testes.",
            "allowed_project_ids": [project_b_id],
        },
    )
    assert agent.status_code == 200

    document = client.post(
        "/api/documents/text",
        json={
            "title": f"Documento projeto A {uuid4().hex}",
            "content": "segredo do projeto A",
            "source_type": "txt",
            "project_id": project_a_id,
        },
    )
    assert document.status_code == 200

    response = client.post(
        "/api/chat/stream",
        json={
            "message": "use o anexo",
            "agent_id": agent.json()["id"],
            "project_id": project_b_id,
            "attached_document_ids": [document.json()["id"]],
        },
    )

    assert response.status_code == 403
    assert "Documentos anexados fora do escopo" in response.text


def test_attached_file_from_another_project_is_rejected_without_moving_metadata() -> None:
    client = TestClient(app)
    project_a = client.post(
        "/api/projects",
        json={"name": f"Projeto A {uuid4().hex}", "description": "origem"},
    )
    project_b = client.post(
        "/api/projects",
        json={"name": f"Projeto B {uuid4().hex}", "description": "destino"},
    )
    assert project_a.status_code == 200
    assert project_b.status_code == 200
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    agent = client.post(
        "/api/agents",
        json={
            "name": f"Agente {uuid4().hex}",
            "description": "Agente de teste",
            "system_prompt": "Responda somente para testes.",
            "allowed_project_ids": [project_b_id],
        },
    )
    assert agent.status_code == 200

    filename = f"arquivo-projeto-a-{uuid4().hex}.txt"
    uploaded = client.post(
        "/api/files/upload",
        params={"source": "upload", "project_id": project_a_id},
        files={"file": (filename, b"conteudo do projeto A", "text/plain")},
    )
    assert uploaded.status_code == 201
    file_id = uploaded.json()["id"]

    response = client.post(
        "/api/chat/stream",
        json={
            "message": "use o arquivo",
            "agent_id": agent.json()["id"],
            "project_id": project_b_id,
            "attached_file_ids": [file_id],
        },
    )

    assert response.status_code == 403
    assert "Arquivos anexados fora do escopo" in response.text
    files = client.get("/api/files/page", params={"query": filename, "limit": 5})
    assert files.status_code == 200
    persisted = next(item for item in files.json()["items"] if item["id"] == file_id)
    assert persisted["metadata"]["project_id"] == project_a_id
    assert persisted["metadata"].get("session_id") is None


def test_delete_chat_keeps_file_promoted_to_knowledge_base() -> None:
    client = TestClient(app)
    session = client.post("/api/chat/sessions", json={"title": f"Sessão KB {uuid4().hex}"})
    assert session.status_code == 200
    session_id = session.json()["id"]

    filename = f"arquivo-base-{uuid4().hex}.txt"
    uploaded = client.post(
        "/api/files/upload",
        params={
            "source": "chat_attachment",
            "project_id": "project_general",
            "session_id": session_id,
        },
        files={"file": (filename, b"conteudo promovido para base", "text/plain")},
    )
    assert uploaded.status_code == 201
    file_id = uploaded.json()["id"]

    document = None
    deadline = time.time() + 8
    while time.time() < deadline:
        listed = client.get("/api/documents")
        assert listed.status_code == 200
        document = next(
            (item for item in listed.json() if item.get("metadata", {}).get("file_id") == file_id),
            None,
        )
        if document is not None:
            break
        time.sleep(0.2)
    assert document is not None

    created_base = client.post(
        "/api/knowledge-bases",
        json={
            "name": f"Base protegida {uuid4().hex}",
            "description": "Base de teste",
            "scope": "Protege arquivo promovido",
            "max_documents_per_query": 5,
            "max_chunks_per_document": 2,
        },
    )
    assert created_base.status_code == 200
    linked = client.post(
        f"/api/knowledge-bases/{created_base.json()['id']}/documents",
        json={"document_id": document["id"], "priority": 1},
    )
    assert linked.status_code == 200

    deleted = client.delete(f"/api/chat/sessions/{session_id}?delete_files=true")
    assert deleted.status_code == 200
    assert file_id not in deleted.json()["deleted_file_ids"]

    content = client.get(f"/api/files/{file_id}/content")
    assert content.status_code == 200
