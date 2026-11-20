from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.model_registry import get_model, load_models
from core.settings import ROOT
from optimizer.optimizer import OptimizationRequest, Optimizer
from optimizer.live_comparator import compare_on_spot
from optimizer.request_router import record_selection
from optimizer.profile_store import historical_profiles
from optimizer.calibrated_profiles import latest_profiles
from optimizer.evidence_report import profile_pareto_view, readiness_report, selection_history
from optimizer.live_matrix import full_live_candidates
from runtime.clients import InferenceError, backend_health, generate
from database.telemetry import verify_jsonl_store
from database.verify_telemetry import verify as verify_mysql

app = FastAPI(title="Local LLM Runtime Optimizer", version="1.0.0")


class OptimizeBody(BaseModel):
    task_type: str = "all"
    minimum_quality: float | None = Field(None, ge=0, le=1)
    maximum_latency_seconds: float | None = Field(None, gt=0)
    maximum_ram_mb: float | None = Field(None, gt=0)
    maximum_energy_joules: float | None = Field(None, gt=0)
    preference: str = Field("balanced", pattern="^(quality|latency|memory|energy|balanced)$")


class GenerateBody(OptimizeBody):
    prompt: str = Field(min_length=1, max_length=20000)
    model_id: str | None = None
    max_output_tokens: int = Field(256, ge=1, le=2048)
    live_compare: bool = False
    full_configuration_matrix: bool = False
    reference_sql: str | None = None
    spider_database_path: str | None = Field(None, max_length=1000)
    selection_weights: dict[str, float] | None = None
    max_live_candidates: int | None = Field(None, ge=1)
    dry_run: bool = False


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "backends": {"llama.cpp": backend_health("llama.cpp"), "ollama": backend_health("ollama")}}


@app.get("/api/v1/models")
def models() -> list[dict[str, Any]]:
    return load_models()


@app.get("/api/v1/readiness")
def readiness() -> dict[str, Any]:
    """Expose local evidence readiness without starting a model or benchmark."""
    models = load_models()
    local_models = [model for model in models if model.get("available_locally") and "llama.cpp" in model.get("backends", [])]
    safe, skipped = full_live_candidates(local_models)
    profiles = latest_profiles()
    return {
        "local_only": True,
        "llama_cpp_available": backend_health("llama.cpp"),
        "available_models": [model["model_id"] for model in local_models],
        "safe_full_matrix_candidates": len(safe),
        "ram_safety_skips": len(skipped),
        "calibrated_profile_count": len(profiles),
        "quality_threshold_ready": bool(profiles),
        "energy_measurement_note": "Physical energy is unavailable unless a cumulative-joule meter export is configured.",
        "evidence": readiness_report(),
    }


@app.get("/api/v1/store-status")
def store_status() -> dict[str, Any]:
    """Report status of the operational primary JSONL store and optional MySQL mirror."""
    return {
        "primary_store": verify_jsonl_store(),
        "optional_mysql_mirror": verify_mysql(),
    }


@app.post("/api/v1/optimize")
def optimize(body: OptimizeBody) -> dict[str, Any]:
    return Optimizer().recommend(historical_profiles(), OptimizationRequest(**body.model_dump()))


def _validated_spider_database_path(value: str | None) -> str | None:
    """Keep API execution matching inside the local Spider dataset boundary."""
    if not value:
        return None
    candidate = Path(value).resolve()
    permitted_root = (ROOT / "spider_data" / "spider_data" / "database").resolve()
    try:
        candidate.relative_to(permitted_root)
    except ValueError as error:
        raise HTTPException(422, "spider_database_path must be inside the local Spider database directory.") from error
    if candidate.suffix.lower() != ".sqlite" or not candidate.is_file():
        raise HTTPException(422, "spider_database_path must identify an existing local Spider SQLite file.")
    return str(candidate)


@app.post("/api/v1/generate")
def generate_request(body: GenerateBody) -> dict[str, Any]:
    if body.live_compare:
        decision = compare_on_spot(
            body.prompt, load_models(), body.max_output_tokens, 0,
            compare_all_models=True, full_configuration_matrix=body.full_configuration_matrix,
            reference_sql=body.reference_sql, spider_database_path=_validated_spider_database_path(body.spider_database_path),
            quality_threshold=body.minimum_quality,
            weights=body.selection_weights, max_live_candidates=body.max_live_candidates, dry_run=body.dry_run,
        )
        if body.dry_run:
            return {"answer": None, "selected_model": None, "configuration": None, "telemetry": None, "recommendation": decision, "recommendation_is_historical": False}
        if not decision.get("selected"):
            raise HTTPException(422, decision["reason"])
        winner = decision["live_comparison"][decision["winner_index"]]
        persistence = record_selection(decision, winner | {"answer": winner["draft"]})
        return {"answer": winner["draft"], "selected_model": decision["selected"]["model"]["model_id"], "configuration": decision["configuration"], "telemetry": winner, "recommendation": decision, "telemetry_persistence": persistence, "recommendation_is_historical": False}
    recommendation = Optimizer().recommend(historical_profiles(), OptimizationRequest(**body.model_dump(exclude={
        "prompt", "model_id", "max_output_tokens", "live_compare", "full_configuration_matrix", "reference_sql", "spider_database_path", "selection_weights", "max_live_candidates", "dry_run",
    })))
    selected_id = body.model_id or (recommendation["selected"] or {}).get("model_id")
    # Historical filenames are not registry IDs; choose a locally registered fallback deliberately.
    model = get_model(selected_id) or next((item for item in load_models() if item["available_locally"]), None)
    if not model:
        raise HTTPException(503, "No requested local model is registered and available.")
    configuration = {"backend": model["backends"][0], "max_output_tokens": body.max_output_tokens}
    try:
        inference = generate(model, body.prompt, configuration)
    except InferenceError as error:
        raise HTTPException(503, str(error)) from error
    return {"answer": inference["answer"], "selected_model": model["model_id"], "configuration": configuration, "telemetry": inference, "recommendation": recommendation, "recommendation_is_historical": bool(recommendation["selected"])}


@app.get("/api/v1/experiments")
def experiments() -> list[dict[str, Any]]:
    return historical_profiles()


@app.get("/api/v1/history")
def history() -> list[dict[str, Any]]:
    """Recent private selection metadata; response text is never returned."""
    return selection_history()


@app.get("/api/v1/pareto")
def pareto() -> list[dict[str, Any]]:
    """Measured, non-dominated Spider profiles only."""
    return profile_pareto_view()


@app.get("/api/v1/recommendations")
def recommendations() -> dict[str, Any]:
    return Optimizer().recommend(historical_profiles(), OptimizationRequest(task_type="all"))
