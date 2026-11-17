from fastapi.testclient import TestClient
from api.app import app


def test_models_endpoint():
    response = TestClient(app).get("/api/v1/models")
    assert response.status_code == 200
    assert response.json()[0]["model_id"]


def test_optimizer_endpoint_and_unsatisfied_constraint():
    client = TestClient(app)
    response = client.post("/api/v1/optimize", json={"prompt": "Explain RAM", "maximum_energy_joules": 1})
    assert response.status_code == 200
    assert response.json()["selected"] is None


def test_input_validation():
    assert TestClient(app).post("/api/v1/optimize", json={"prompt": ""}).status_code == 422


def test_generate_handles_unavailable_backend_without_validation_error():
    response = TestClient(app).post("/api/v1/generate", json={"prompt": "Explain RAM"})
    assert response.status_code == 503
