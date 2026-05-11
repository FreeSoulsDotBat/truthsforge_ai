from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_server_status() -> None:
    client = TestClient(app)
    response = client.get("/api/server/status")
    assert response.status_code == 200
    assert response.json()["persona"] == "JUDITE"
