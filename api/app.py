from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.model_registry import get_model, load_models
from optimizer.optimizer import OptimizationRequest, Optimizer
from optimizer.profile_store import historical_profiles
from runtime.clients import InferenceError, backend_health, generate

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


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "backends": {"llama.cpp": backend_health("llama.cpp"), "ollama": backend_health("ollama")}}


@app.get("/api/v1/models")
def models() -> list[dict[str, Any]]:
    return load_models()


@app.post("/api/v1/optimize")
def optimize(body: OptimizeBody) -> dict[str, Any]:
    return Optimizer().recommend(historical_profiles(), OptimizationRequest(**body.model_dump()))


@app.post("/api/v1/generate")
def generate_request(body: GenerateBody) -> dict[str, Any]:
    recommendation = Optimizer().recommend(historical_profiles(), OptimizationRequest(**body.model_dump(exclude={"prompt", "model_id", "max_output_tokens"})))
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


@app.get("/api/v1/recommendations")
def recommendations() -> dict[str, Any]:
    return Optimizer().recommend(historical_profiles(), OptimizationRequest(task_type="all"))
