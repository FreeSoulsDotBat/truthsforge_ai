from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_list_agents_returns_list() -> None:
    client = TestClient(app)
    response = client.get("/api/agents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_agent_modifies_fields() -> None:
    client = TestClient(app)

    created = client.post(
        "/api/agents",
        json={
            "name": f"Agente {uuid4().hex}",
            "system_prompt": "Responda apenas para testes.",
        },
    )
    assert created.status_code == 200
    agent_id = created.json()["id"]

    new_name = f"Agente renomeado {uuid4().hex}"
    updated = client.put(
        f"/api/agents/{agent_id}",
        json={
            "name": new_name,
            "description": "Atualizado no teste",
            "system_prompt": "Novo prompt de sistema.",
        },
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["id"] == agent_id
    assert body["name"] == new_name
    assert body["description"] == "Atualizado no teste"
    assert body["system_prompt"] == "Novo prompt de sistema."

    listing = client.get("/api/agents")
    assert listing.status_code == 200
    assert any(item["id"] == agent_id for item in listing.json())
