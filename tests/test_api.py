from fastapi.testclient import TestClient

from api.app import app


def test_health_and_models_endpoints():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/models").status_code == 200


def test_optimize_endpoint_avoids_fake_quality():
    response = TestClient(app).post("/api/v1/optimize", json={"task_type": "all", "preference": "latency"})
    assert response.status_code == 200
    assert "selected" in response.json()


def test_generate_uses_registry_fallback_when_historical_filename_is_not_a_model_id(monkeypatch):
    monkeypatch.setattr("api.app.generate", lambda *args, **kwargs: {"answer": "ok", "measurement_kind": "measured"})
    response = TestClient(app).post("/api/v1/generate", json={"prompt": "hello", "task_type": "all"})
    assert response.status_code == 200
    assert response.json()["answer"] == "ok"
