"""Local FastAPI gateway for optimization and optional inference."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config.model_registry import load_model_registry, model_by_id
from config.settings import settings
from inference.backends import LlamaCppServerBackend, OllamaBackend
from optimizer.optimizer import RuntimeOptimizer
from optimizer.profile_loader import legacy_profiles
from runtime_optimizer.types import OptimizationRequest

app = FastAPI(title="Local LLM Runtime Optimizer", version="1.0.0")


class OptimizePayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    task_type: str = "general"
    minimum_quality: float | None = Field(default=None, ge=0, le=1)
    maximum_latency_seconds: float | None = Field(default=None, gt=0)
    maximum_ram_mb: float | None = Field(default=None, gt=0)
    maximum_energy_joules: float | None = Field(default=None, gt=0)
    preference: str = Field(default="balanced", pattern="^(quality|latency|memory|energy|balanced)$")


class GeneratePayload(OptimizePayload):
    fallback_on_unavailable: bool = True


def get_recommendation(payload: OptimizePayload):
    request = OptimizationRequest(**payload.model_dump(exclude={"fallback_on_unavailable"}))
    return RuntimeOptimizer(legacy_profiles()).recommend(request)


@app.get("/health")
def health() -> dict:
    llama = LlamaCppServerBackend(settings.llama_server_url).health()
    ollama = OllamaBackend(settings.ollama_url).health()
    return {"status": "ok", "inference_backends": {"llama.cpp": llama, "ollama": ollama}, "profiles_loaded": len(legacy_profiles())}


@app.get("/api/v1/models")
def models() -> list[dict]:
    return load_model_registry()


@app.post("/api/v1/optimize")
def optimize(payload: OptimizePayload) -> dict:
    return get_recommendation(payload).as_dict()


@app.post("/api/v1/generate")
def generate(payload: GeneratePayload) -> dict:
    recommendation = get_recommendation(payload)
    if recommendation.selected is None:
        raise HTTPException(status_code=422, detail=recommendation.as_dict())
    config = recommendation.selected.configuration
    model = model_by_id(config.model_id)
    if not model:
        raise HTTPException(status_code=503, detail="Selected model is not registered.")
    backend = LlamaCppServerBackend(settings.llama_server_url) if config.backend == "llama.cpp" else OllamaBackend(settings.ollama_url)
    if not backend.health():
        raise HTTPException(status_code=503, detail={"message": f"{config.backend} is unavailable; no untested fallback was selected.", "recommendation": recommendation.as_dict()})
    try:
        inference_model = model.get("file_path") or model["model_id"].replace("ollama-", "").replace("-", ":", 1)
        result = backend.generate(inference_model, payload.prompt, config.max_output_tokens, config.temperature, settings.request_timeout_seconds)
    except Exception as error:
        raise HTTPException(status_code=504, detail=f"Local inference failed: {error}") from error
    return {"answer": result.text, "selected_configuration": config.as_dict(), "recommendation_evidence": recommendation.selected.source, "measured_response_metadata": {"latency_seconds": result.latency_seconds, "prompt_tokens": result.prompt_tokens, "generated_tokens": result.generated_tokens, "backend": result.backend}}


@app.get("/api/v1/experiments")
def experiments() -> dict:
    return {"source": "legacy CSV (read-only)", "profiles": [{"configuration": profile.configuration.as_dict(), "quality": profile.quality, "latency_seconds": profile.latency_seconds, "ram_mb": profile.ram_mb, "sample_count": profile.sample_count, "notes": profile.notes} for profile in legacy_profiles()]}


@app.get("/api/v1/recommendations")
def recommendations() -> dict:
    return {"message": "POST /api/v1/optimize with prompt and constraints to create a recommendation."}
