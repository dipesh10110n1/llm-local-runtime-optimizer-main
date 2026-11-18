from __future__ import annotations

import time
from typing import Any

import requests

from core.settings import settings


class InferenceError(RuntimeError):
    pass


def backend_health(backend: str) -> bool:
    url = settings.llama_server_url + "/health" if backend == "llama.cpp" else settings.ollama_url + "/api/tags"
    try:
        return requests.get(url, timeout=2).ok
    except requests.RequestException:
        return False


def generate(model: dict[str, Any], prompt: str, configuration: dict[str, Any]) -> dict[str, Any]:
    backend = configuration.get("backend") or model["backends"][0]
    start = time.perf_counter()
    try:
        if backend == "llama.cpp":
            payload = {"messages": [{"role": "user", "content": prompt}], "temperature": configuration.get("temperature", 0), "max_tokens": configuration.get("max_output_tokens", 256), "stream": False}
            response = requests.post(settings.llama_server_url + "/v1/chat/completions", json=payload, timeout=settings.request_timeout_seconds)
            response.raise_for_status(); data = response.json()
            answer = data["choices"][0]["message"]["content"].strip(); usage = data.get("usage", {})
        elif backend == "ollama":
            payload = {"model": model.get("backend_model_name", model["model_id"]), "prompt": prompt, "stream": False, "options": {"temperature": configuration.get("temperature", 0), "num_predict": configuration.get("max_output_tokens", 256)}}
            response = requests.post(settings.ollama_url + "/api/generate", json=payload, timeout=settings.request_timeout_seconds)
            response.raise_for_status(); data = response.json()
            answer = data.get("response", "").strip(); usage = {"completion_tokens": data.get("eval_count"), "prompt_tokens": data.get("prompt_eval_count")}
        else:
            raise InferenceError(f"Unsupported backend: {backend}")
    except requests.RequestException as error:
        raise InferenceError(f"{backend} inference unavailable: {error}") from error
    elapsed = time.perf_counter() - start
    tokens = usage.get("completion_tokens")
    return {"answer": answer, "backend": backend, "end_to_end_seconds": elapsed, "generated_tokens": tokens, "generation_tokens_per_second": tokens / elapsed if tokens and elapsed else None, "measurement_kind": "measured"}
