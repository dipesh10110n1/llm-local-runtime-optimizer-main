from api import app as api_module
from api.app import GenerateBody, OptimizeBody, generate_request, health, models, optimize, readiness, store_status


def test_health_and_models_endpoints():
    health_res = health()
    assert health_res["status"] == "ok"
    assert "backends" in health_res
    models_res = models()
    assert isinstance(models_res, list)


def test_optimize_endpoint_avoids_fake_quality():
    body = OptimizeBody(task_type="all", preference="latency")
    res = optimize(body)
    assert "selected" in res


def test_readiness_endpoint_reports_measurement_limits(monkeypatch):
    monkeypatch.setattr("api.app.full_live_candidates", lambda _: ([], [{"reason": "RAM safety skip"}]))
    res = readiness()
    assert res["local_only"] is True
    assert "Physical energy" in res["energy_measurement_note"]


def test_live_api_selection_is_persisted_with_private_telemetry(monkeypatch):
    decision = {
        "selected": {"model": {"model_id": "qwen"}}, "configuration": {"configuration_id": "qwen:t4"},
        "task_type": "general", "winner_index": 0, "live_comparison": [{"draft": "answer"}],
    }
    monkeypatch.setattr(api_module, "compare_on_spot", lambda *args, **kwargs: decision)
    monkeypatch.setattr(api_module, "record_selection", lambda selected, telemetry: {"status": "persisted", "answer": telemetry["answer"]})

    body = GenerateBody(prompt="hello", live_compare=True)
    res = generate_request(body)

    assert res["answer"] == "answer"
    assert res["telemetry_persistence"]["status"] == "persisted"


def test_generate_uses_registry_fallback_when_historical_filename_is_not_a_model_id(monkeypatch):
    monkeypatch.setattr("api.app.generate", lambda *args, **kwargs: {"answer": "ok", "measurement_kind": "measured"})
    body = GenerateBody(prompt="hello", task_type="all")
    res = generate_request(body)
    assert res["answer"] == "ok"


def test_store_status_endpoint():
    res = store_status()
    assert "primary_store" in res
    assert res["primary_store"]["primary_store"] == "jsonl"
    assert "optional_mysql_mirror" in res
