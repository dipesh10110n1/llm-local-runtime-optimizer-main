"""RAM-safe expansion of the full local runtime configuration matrix."""
from __future__ import annotations

import json
import random
from typing import Any

import psutil

from core.settings import ROOT, settings
from optimizer.configuration_catalog import benchmark_configurations

SAFETY_RESERVE_MB = float(getattr(settings, "safety_reserve_mb", 512.0))


def _reclaimable_managed_runtime_mb() -> float:
    """The recorded Orbit server is stopped before sequential model switching."""
    state_path = ROOT / "runtime" / "active_runtime.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        process = psutil.Process(int(state["pid"]))
        if "llama-server" in process.name().lower():
            return process.memory_info().rss / 1024**2
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError, psutil.Error):
        pass
    return 0.0


def safe_available_memory_mb() -> float:
    """Available RAM plus only Orbit's safely reclaimable managed server RSS."""
    return psutil.virtual_memory().available / 1024**2 + _reclaimable_managed_runtime_mb()


def required_memory_mb(model: dict[str, Any], configuration: dict[str, Any]) -> float:
    """Conservative pre-launch admission estimate; benchmark RSS later replaces it."""
    model_size_mb = (ROOT / model["path"]).stat().st_size / 1024**2
    return model_size_mb * 1.3 + 300 + float(configuration["context_size"]) * 0.15


def full_live_candidates(
    models: list[dict[str, Any]],
    available_mb: float | None = None,
    safety_reserve_mb: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Expand all local configurations, retaining only candidates safe in isolation."""
    reserve = safety_reserve_mb if safety_reserve_mb is not None else float(getattr(settings, "safety_reserve_mb", SAFETY_RESERVE_MB))
    available = (
        available_mb if available_mb is not None
        else safe_available_memory_mb()
    )
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for model in models:
        if not model.get("available_locally") or "llama.cpp" not in model.get("backends", []):
            continue
        for configuration in benchmark_configurations(model):
            required = required_memory_mb(model, configuration)
            entry = {"model": model, "configuration": configuration, "required_mb": required}
            if required + reserve <= available:
                candidates.append(entry)
            else:
                skipped.append(entry | {"reason": f"RAM safety skip: estimated {required:.0f} MiB plus {reserve:.0f} MiB reserve; available {available:.0f} MiB"})
    return candidates, skipped


def stratified_sample(candidates: list[dict[str, Any]], n: int, seed: int = 42) -> list[dict[str, Any]]:
    """Return n candidates picked evenly across (model_id, cache, compression, retrieval_enabled) groups.

    If n >= len(candidates), falls back to a reproducibly shuffled copy of all candidates.
    Uses random.Random(seed) so results are deterministic across calls with the same seed.
    """
    rng = random.Random(seed)
    if n >= len(candidates):
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        return shuffled

    # Group by the four stratification dimensions.
    groups: dict[tuple[str, str, str, bool], list[dict[str, Any]]] = {}
    for entry in candidates:
        cfg = entry["configuration"]
        key = (
            entry["model"]["model_id"],
            cfg.get("cache", ""),
            cfg.get("prompt_compression", cfg.get("compression", "")),
            bool(cfg.get("retrieval", {}).get("enabled", False)),
        )
        groups.setdefault(key, []).append(entry)

    # Shuffle each group independently for variety within strata.
    group_lists = []
    for key in sorted(groups):  # sorted for determinism before rng comes in
        bucket = list(groups[key])
        rng.shuffle(bucket)
        group_lists.append(bucket)

    # Round-robin across groups until n candidates are collected.
    result: list[dict[str, Any]] = []
    indices = [0] * len(group_lists)
    group_count = len(group_lists)
    group_idx = 0
    while len(result) < n:
        # Advance to the next group that still has candidates.
        exhausted = 0
        while indices[group_idx] >= len(group_lists[group_idx]):
            group_idx = (group_idx + 1) % group_count
            exhausted += 1
            if exhausted > group_count:
                break  # All groups exhausted
        if indices[group_idx] >= len(group_lists[group_idx]):
            break  # No more candidates anywhere
        result.append(group_lists[group_idx][indices[group_idx]])
        indices[group_idx] += 1
        group_idx = (group_idx + 1) % group_count
    return result
