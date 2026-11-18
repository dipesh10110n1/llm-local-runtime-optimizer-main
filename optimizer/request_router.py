"""Evidence-labelled routing for one local request at a time."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import psutil

from core.settings import ROOT
from optimizer.profile_store import historical_profiles

SELECTION_HISTORY = ROOT / "logs" / "runtime_selection_history.jsonl"
CALIBRATION_HISTORY = ROOT / "logs" / "model_calibration.jsonl"


def classify_task(prompt: str) -> str:
    text = prompt.lower()
    if re.search(r"\b(code|python|function|bug|algorithm|script|program)\b", text):
        return "coding"
    if re.search(r"\b(calculate|solve|math|equation|reason|proof|why)\b", text):
        return "reasoning"
    if re.search(r"\b(summarize|summary|shorten)\b", text):
        return "summarization"
    return "general"


def _measured_memory(model: dict[str, Any]) -> float | None:
    historical_name = model["path"].split("/")[-1]
    values = [profile["ram_mb"] for profile in historical_profiles() if profile["model_id"] == historical_name and profile.get("ram_mb")]
    return min(values) if values else None


def _estimated_memory(model: dict[str, Any]) -> float:
    """Conservative feasibility estimate from the on-disk GGUF size plus 300 MiB runtime headroom."""
    size_mb = (ROOT / model["path"]).stat().st_size / 1024**2
    return size_mb * 1.3 + 300


def _reclaimable_orbit_runtime_mb() -> float:
    """Return RAM held by Orbit's current server, which a model switch will release."""
    state_path = ROOT / "runtime" / "active_runtime.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        pid = state.get("pid")
        if not isinstance(pid, int):
            return 0.0
        process = psutil.Process(pid)
        if "llama-server" not in process.name().lower():
            return 0.0
        return process.memory_info().rss / 1024**2
    except (FileNotFoundError, json.JSONDecodeError, psutil.Error):
        return 0.0


def _latest_calibrations() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    try:
        with CALIBRATION_HISTORY.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    latest[record["model_id"]] = record
    except FileNotFoundError:
        pass
    return latest


def recommend_runtime(prompt: str, models: list[dict[str, Any]]) -> dict[str, Any]:
    task_type = classify_task(prompt)
    physical_available_mb = psutil.virtual_memory().available / 1024**2
    # Switching models terminates Orbit's recorded llama-server first. Its RSS is
    # therefore reclaimable, not concurrent memory required by the next candidate.
    reclaimable_runtime_mb = _reclaimable_orbit_runtime_mb()
    available_mb = physical_available_mb + reclaimable_runtime_mb
    calibrations = _latest_calibrations()
    candidates: list[dict[str, Any]] = []
    for model in models:
        if not model.get("available_locally") or "llama.cpp" not in model.get("backends", []):
            continue
        measured_memory = _measured_memory(model)
        required_mb = measured_memory or _estimated_memory(model)
        candidates.append({
            "model": model,
            "required_mb": required_mb,
            "memory_source": "measured historical peak RSS" if measured_memory else "estimated from GGUF file size",
            "calibration": calibrations.get(model["model_id"]),
            # Keep 1.5 GiB free for Windows, Streamlit, and context/KV growth.
            "feasible": required_mb + 1536 <= available_mb,
        })
    feasible = [item for item in candidates if item["feasible"]]
    if not feasible:
        fallback = min(candidates, key=lambda item: item["required_mb"], default=None)
        return {"selected": None, "task_type": task_type, "available_mb": available_mb, "physical_available_mb": physical_available_mb, "reclaimable_runtime_mb": reclaimable_runtime_mb, "candidates": candidates, "reason": "No registered model fits while retaining the 1.5 GiB RAM safety reserve.", "fallback": fallback}
    calibrated = [item for item in feasible if item["calibration"]]
    if calibrated:
        best_quality = max(item["calibration"]["quality_score"] for item in calibrated)
        close_quality = [
            item for item in calibrated
            if best_quality - item["calibration"]["quality_score"] <= 0.08
        ]
        if task_type in {"coding", "reasoning"} and close_quality:
            selected = max(close_quality, key=lambda item: item["model"]["parameter_count_b"])
            reason = "For coding/reasoning, selected the largest model within 8 quality points of the measured calibration leader."
        else:
            selected = max(calibrated, key=lambda item: (item["calibration"]["quality_score"], -item["calibration"]["mean_latency_seconds"]))
            reason = "For general/summarization work, selected the calibration leader by measured quality, then mean latency."
    else:
        selected = max(feasible, key=lambda item: item["model"]["parameter_count_b"])
        reason = "Largest feasible Qwen model selected for response quality; quality is a parameter-count proxy until task calibration is recorded."
    model = selected["model"]
    config = {
        "configuration_id": f"{model['model_id']}:t4:c2048:cpu",
        "backend": "llama.cpp",
        "threads": 4,
        "context_size": 2048,
        "gpu_layers": 0,
        "cache": "server-default",
    }
    return {
        "selected": selected,
        "configuration": config,
        "task_type": task_type,
        "available_mb": available_mb,
        "physical_available_mb": physical_available_mb,
        "reclaimable_runtime_mb": reclaimable_runtime_mb,
        "candidates": candidates,
        "reason": reason,
    }


def record_selection(decision: dict[str, Any], telemetry: dict[str, Any]) -> None:
    selected = decision.get("selected")
    if not selected:
        return
    row = {
        "model_id": selected["model"]["model_id"],
        "configuration_id": decision["configuration"]["configuration_id"],
        "task_type": decision["task_type"],
        "configuration": decision["configuration"],
        "telemetry": telemetry,
    }
    with SELECTION_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def selection_caption(decision: dict[str, Any]) -> str:
    selected = decision.get("selected")
    if not selected:
        return f"No safe model selected - available RAM {decision['available_mb']:.0f} MiB"
    model = selected["model"]
    config = decision["configuration"]
    if decision.get("live_comparison"):
        live = "; ".join(
            f"{entry['candidate']['model']['model_id']} draft: {entry['latency_seconds']:.2f}s"
            for entry in decision["live_comparison"]
        )
        return (
            f"Selected **{model['model_id']}** - llama.cpp - {config['threads']} CPU threads - "
            f"context {config['context_size']} - CPU-only. On-the-spot comparison: {live}. "
            f"{decision['reason']}"
        )
    comparison = []
    for candidate in decision.get("candidates", []):
        calibration = candidate.get("calibration")
        if calibration:
            comparison.append(
                f"{candidate['model']['model_id']}: quality {calibration['quality_score']:.3f}, "
                f"latency {calibration['mean_latency_seconds']:.2f}s"
            )
    return (
        f"Selected **{model['model_id']}** - llama.cpp - {config['threads']} CPU threads - "
        f"context {config['context_size']} - CPU-only - {selected['memory_source']}. "
        f"Selection basis: {decision.get('reason', 'estimated quality; no calibration record is available.')} "
        f"Compared: {'; '.join(comparison) if comparison else 'no calibrated candidates yet.'}"
    )
