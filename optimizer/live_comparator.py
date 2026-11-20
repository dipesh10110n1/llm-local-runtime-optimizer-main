"""Prompt-specific, sequential local-model comparison before final generation."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from optimizer.configuration_catalog import baseline_configuration, cache_server_arguments
from optimizer.live_matrix import full_live_candidates
from optimizer.request_router import classify_task, recommend_runtime
from optimizer.task_quality import evaluate_spider_sql
from optimizer.weighted_selection import score_candidates
from runtime.clients import InferenceError, generate
from runtime.prompt_pipeline import prepare_prompt
from runtime.supervisor import RuntimeSwitchError, ensure_runtime


def _configuration(model: dict[str, Any]) -> dict[str, Any]:
    return baseline_configuration(model)


def parse_judgement(text: str, candidate_count: int) -> int | None:
    """Return a valid, explicitly labelled judge choice, if one was supplied."""
    lowered = text.lower()
    if re.search(r"\b(?:winner\s*:\s*)?tie\b", lowered):
        return None
    match = re.search(r"\bwinner\s*:\s*(\d+)\b", lowered)
    if not match:
        match = re.fullmatch(r"\s*(?:candidate\s*)?(\d+)\s*[.!]?\s*", lowered)
    if not match:
        return None
    index = int(match.group(1)) - 1
    return index if 0 <= index < candidate_count else None


def compare_on_spot(
    prompt: str,
    models: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float,
    compare_all_models: bool = False,
    full_configuration_matrix: bool = False,
    reference_sql: str | None = None,
    spider_database_path: str | None = None,
    quality_threshold: float | None = None,
    weights: dict[str, float] | None = None,
    max_live_candidates: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate, measure, score, and select local candidate responses.

    This deliberately runs one server/model at a time to stay within laptop RAM limits.
    The RAM safety reserve is read from ORBIT_SAFETY_RESERVE_MB env var (default 512 MiB).
    """
    if quality_threshold is not None and not 0 <= quality_threshold <= 1:
        raise ValueError("quality_threshold must be between zero and one")
    if max_live_candidates is not None and max_live_candidates < 1:
        raise ValueError("max_live_candidates must be at least one when provided")
    if weights and any(value < 0 for value in weights.values()):
        raise ValueError("selection weights cannot be negative")
    # Read the safety reserve at call time so the dashboard slider (which writes
    # ORBIT_SAFETY_RESERVE_MB to os.environ) takes effect without a restart.
    reserve_mb = float(os.environ.get("ORBIT_SAFETY_RESERVE_MB", "512.0"))
    feasibility = recommend_runtime(prompt, models, safety_reserve_mb=reserve_mb)
    # A threshold is a hard claim about task quality.  Do not silently reuse a
    # historical Spider score for an unrelated live chat prompt: that would
    # make a quality-gated selection look measured when it is not.
    if quality_threshold is not None and not reference_sql:
        return {
            "selected": None,
            "task_type": feasibility["task_type"],
            "available_mb": feasibility["available_mb"],
            "candidates": feasibility["candidates"],
            "quality_threshold": quality_threshold,
            "reason": (
                "A live quality threshold requires task-valid reference evidence. "
                "For the currently integrated Spider evaluator, provide reference_sql "
                "and optionally the matching local Spider database path for execution matching."
            ),
        }
    matrix_skips: list[dict[str, Any]] = []
    if full_configuration_matrix:
        runs, matrix_skips = full_live_candidates(models, safety_reserve_mb=reserve_mb)
        candidates = []
        resident_fallback = False
    elif compare_all_models:
        # Compare every installed local candidate one at a time. Only one
        # llama.cpp server is live, so model RAM is released before the next
        # candidate is loaded. Never bypass the admission gate merely because
        # the caller requested a broad comparison.
        candidates = [item for item in feasibility["candidates"] if item["feasible"]]
        if not candidates and feasibility.get("resident_fallback"):
            candidates = [feasibility["selected"]]
        runs = [{"model": item["model"], "configuration": _configuration(item["model"]), "candidate": item} for item in candidates]
        resident_fallback = feasibility.get("resident_fallback", False)
    else:
        candidates = [item for item in feasibility["candidates"] if item["feasible"]]
        resident_fallback = feasibility.get("resident_fallback", False)
        if not candidates and resident_fallback:
            # The model is already loaded and reusing it needs no additional RAM.
            candidates = [feasibility["selected"]]
        runs = [{"model": item["model"], "configuration": _configuration(item["model"]), "candidate": item} for item in candidates]
    if not runs:
        return {"selected": None, "task_type": feasibility["task_type"], "available_mb": feasibility["available_mb"], "candidates": feasibility["candidates"], "reason": feasibility["reason"]}

    total_candidate_count = len(runs)
    deferred_runs: list[dict[str, Any]] = []
    if max_live_candidates is not None and len(runs) > max_live_candidates:
        deferred_runs, runs = runs[max_live_candidates:], runs[:max_live_candidates]
    if dry_run:
        return {
            "selected": None, "task_type": feasibility["task_type"], "available_mb": feasibility["available_mb"],
            "candidate_count": total_candidate_count, "scheduled_candidate_count": len(runs),
            "deferred_candidate_count": len(deferred_runs), "matrix_safety_skips": matrix_skips,
            "quality_threshold": quality_threshold,
            "reason": "Dry run only: no model was loaded or response generated.",
        }

    comparisons: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for run in runs:
        model = run["model"]
        configuration = run["configuration"]
        # Do not use ``dict.get(key, run[...])`` here: Python evaluates the
        # fallback eagerly, which previously raised KeyError for matrix runs
        # that already supplied their candidate metadata.
        item = run.get("candidate")
        if item is None:
            item = {
                "model": model,
                "required_mb": run.get("required_mb"),
                "memory_source": "configuration safety estimate",
            }
        try:
            ensure_runtime(model, configuration, cache_server_arguments(configuration))
            prepared_prompt, preparation = prepare_prompt(prompt, configuration)
            response = generate(
                model,
                prepared_prompt,
                {
                    "backend": "llama.cpp",
                    # These are complete candidate answers, not short routing probes.
                    "max_output_tokens": max_output_tokens,
                    "temperature": temperature,
                },
            )
        except (InferenceError, RuntimeSwitchError) as error:
            failures.append({"candidate": item, "configuration": configuration, "error": str(error)})
            continue
        quality = evaluate_spider_sql(
            response["answer"], reference_sql,
            database_path=None if spider_database_path is None else Path(spider_database_path),
        )
        watts = response.get("energy_proxy_watts")
        joules = response.get("energy_proxy_joules")
        task_quality = quality.get("score")
        comparisons.append({
            "candidate": item, "configuration": configuration, "draft": response["answer"],
            "latency_seconds": response["end_to_end_seconds"],
            "ttft_seconds": response.get("ttft_seconds"),
            "generated_tokens": response.get("generated_tokens"),
            "generation_tokens_per_second": response.get("generation_tokens_per_second"),
            "peak_ram_mb": response.get("peak_ram_mb"),
            "energy_proxy_watts": watts,
            "energy_proxy_joules": joules,
            "energy_proxy_method": response.get("energy_proxy_method"),
            "energy_measurement_kind": response.get("energy_measurement_kind"),
            "task_quality": task_quality,
            "task_quality_detail": quality,
            "quality_per_proxy_joule": task_quality / joules if task_quality is not None and joules and joules > 0 else None,
            "quality_per_estimated_watt": task_quality / watts if task_quality is not None and watts else None,
            # Compatibility alias. Consumers must read the explicit estimate
            # label above and must not present this as physical-meter evidence.
            "quality_per_watt": task_quality / watts if task_quality is not None and watts else None,
            "energy_unit_note": "quality_per_proxy_joule uses estimated proxy joules; quality_per_estimated_watt uses instantaneous watts proxy",
            "prompt_preparation": preparation,
        })

    if not comparisons:
        return {
            "selected": None, "task_type": feasibility["task_type"],
            "available_mb": feasibility["available_mb"], "candidates": feasibility["candidates"],
            "comparison_failures": failures,
            "reason": "No selected local model completed the response comparison.",
        }

    eligible_indices = [
        index for index, entry in enumerate(comparisons)
        if quality_threshold is None or (entry["task_quality"] is not None and entry["task_quality"] >= quality_threshold)
    ]
    quality_rejections = [
        {
            "model_id": entry["candidate"]["model"]["model_id"],
            "configuration_id": entry["configuration"]["configuration_id"],
            "reason": (
                "Task-valid quality is unavailable"
                if entry["task_quality"] is None
                else f"Task quality {entry['task_quality']:.3f} is below threshold {quality_threshold:.3f}"
            ),
        }
        for entry in comparisons
        if quality_threshold is not None
        and (entry["task_quality"] is None or entry["task_quality"] < quality_threshold)
    ]
    scoring_weights = dict(weights or {})
    if quality_threshold is not None:
        # Quality is a hard admission requirement. Once eligible, choose the
        # lowest-cost configuration instead of rewarding surplus quality twice.
        scoring_weights["task_quality"] = 0.0
    scoring = score_candidates(comparisons, scoring_weights)
    scored_indices = [index for index in eligible_indices if comparisons[index]["weighted_score"] is not None]
    if scored_indices:
        winner_index = max(scored_indices, key=lambda index: comparisons[index]["weighted_score"])
        basis = (
            f"Met quality threshold {quality_threshold:.3f}; selected by normalized weighted cost/efficiency score."
            if quality_threshold is not None else "Selected by normalized weighted score across the measured available metrics."
        )
    elif quality_threshold is not None:
        return {
            "selected": None, "task_type": feasibility["task_type"], "available_mb": feasibility["available_mb"],
            "candidates": feasibility["candidates"], "live_comparison": comparisons, "scoring": scoring,
            "comparison_failures": failures, "matrix_safety_skips": matrix_skips,
            "quality_threshold": quality_threshold,
            "quality_rejections": quality_rejections,
            "reason": "No completed configuration supplied measured or calibrated quality at the requested threshold.",
        }
    else:
        winner_index = min(range(len(comparisons)), key=lambda index: comparisons[index]["latency_seconds"])
        basis = "No weighted metrics were available; selected the lowest-latency completed response."
    winner = comparisons[winner_index]
    runtime_state = ensure_runtime(winner["candidate"]["model"], winner["configuration"], cache_server_arguments(winner["configuration"]))
    return {
        "selected": winner["candidate"], "configuration": winner["configuration"],
        "task_type": classify_task(prompt), "available_mb": feasibility["available_mb"],
        "candidates": feasibility["candidates"], "reason": basis,
        "live_comparison": comparisons, "scoring": scoring,
        "comparison_failures": failures, "matrix_safety_skips": matrix_skips,
        "deferred_candidate_count": len(deferred_runs), "candidate_count": total_candidate_count,
        "quality_threshold": quality_threshold,
        "quality_rejections": quality_rejections,
        "winner_index": winner_index, "resident_fallback": resident_fallback,
        "runtime_switched": runtime_state["switched"],
    }
