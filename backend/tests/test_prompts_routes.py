from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_list_prompts_returns_list() -> None:
    client = TestClient(app)
    response = client.get("/api/prompts")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_prompt_persists_and_is_listed() -> None:
    client = TestClient(app)
    title = f"Prompt de teste {uuid4().hex}"

    created = client.post(
        "/api/prompts",
        json={"title": title, "template": "Ola {nome}", "tags": ["teste"]},
    )

    assert created.status_code == 200
    body = created.json()
    assert body["id"]
    assert body["title"] == title
    assert body["template"] == "Ola {nome}"
    assert body["tags"] == ["teste"]
    assert body["version"] == 1
    assert body["favorite"] is False

    listing = client.get("/api/prompts")
    assert listing.status_code == 200
    assert any(item["id"] == body["id"] for item in listing.json())
