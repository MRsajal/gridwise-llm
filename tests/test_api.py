from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_contract():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_malformed_request_is_controlled():
    response = client.post("/optimize-energy", json={"scenario_id": "broken"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
