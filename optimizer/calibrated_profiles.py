"""Aggregate measured benchmark evidence into threshold-selectable profiles."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.ids import new_experiment_id
from core.settings import ROOT
from optimizer.weighted_selection import score_candidates

RAW_DIRECTORY = ROOT / "logs" / "full_matrix_benchmarks"
STANDARD_RAW_DIRECTORY = ROOT / "logs" / "standard_quality_benchmarks"
PROFILE_DIRECTORY = ROOT / "logs" / "calibrated_profiles"

# These studies change one configuration dimension under a controlled protocol.
# They are normalized into the same record shape as the full matrix, so the
# selector never ignores valid measured Q4/Q5/Q6, cache, or thread/context data.
CONTROLLED_STUDY_DIRECTORIES = {
    "quantization": ROOT / "logs" / "quantization_comparisons",
    "cache": ROOT / "logs" / "cache_prompt_experiments",
    "context_thread": ROOT / "logs" / "context_thread_calibrations",
    "prompt_compression": ROOT / "logs" / "prompt_compression_experiments",
    "local_retrieval": ROOT / "logs" / "local_retrieval_experiments",
    "three_model": ROOT / "logs" / "three_model_comparisons",
}

# Quality is an admission gate. These weights compare the remaining measured
# efficiency/cost properties and never reinterpret a proxy as real energy.
LOWEST_COST_WEIGHTS = {
    "task_quality": 0.0,
    "generation_tokens_per_second": 0.25,
    "ttft_seconds": 0.25,
    "peak_ram_mb": 0.25,
    "energy_proxy_joules": 0.10,
    "quality_per_estimated_watt": 0.15,
}


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "stddev": None, "min": None, "max": None}
    return {
        "count": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
        "stddev": statistics.stdev(values) if len(values) > 1 else None, "min": min(values), "max": max(values),
    }


def _quality_lower_bound(values: list[float]) -> float | None:
    """Conservative lower confidence estimate for repeated bounded trials."""
    if len(values) < 3:
        return None
    mean = statistics.mean(values)
    deviation = statistics.stdev(values)
    return max(0.0, min(1.0, mean - 1.96 * deviation / math.sqrt(len(values))))


def aggregate_records(records: list[dict[str, Any]], minimum_samples: int = 3) -> list[dict[str, Any]]:
    """Aggregate only successful measured Spider trials by exact configuration."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("phase") == "measured" and record.get("success"):
            groups.setdefault(record["configuration"]["configuration_id"], []).append(record)
    profiles: list[dict[str, Any]] = []
    for configuration_id, group in sorted(groups.items()):
        if len(group) < minimum_samples:
            continue
        telemetry = [item["telemetry"] for item in group]
        quality = [item["task_quality"]["score"] for item in group if item.get("task_quality", {}).get("score") is not None]
        profile = {
            "configuration_id": configuration_id, "model_id": group[0]["model_id"],
            "quantization": group[0].get("quantization"), "configuration": group[0]["configuration"],
            "task_type": "spider_text_to_sql", "dataset": "spider_dev",
            "sample_count": len(group), "quality": statistics.mean(quality) if quality else None,
            "quality_statistics": _stats(quality),
            "quality_lower_confidence_bound": _quality_lower_bound(quality),
            "measurement_confidence": "limited" if len(quality) < 5 else "repeatable",
            "latency_seconds": _stats([item.get("end_to_end_seconds") for item in telemetry if item.get("end_to_end_seconds") is not None])["mean"],
            "latency_statistics": _stats([item.get("end_to_end_seconds") for item in telemetry if item.get("end_to_end_seconds") is not None]),
            "ttft_seconds": _stats([item.get("ttft_seconds") for item in telemetry if item.get("ttft_seconds") is not None])["mean"],
            "prompt_processing_seconds": _stats([item.get("prompt_processing_seconds") for item in telemetry if item.get("prompt_processing_seconds") is not None])["mean"],
            "prompt_tokens_per_second": _stats([item.get("prompt_tokens_per_second") for item in telemetry if item.get("prompt_tokens_per_second") is not None])["mean"],
            "generation_tokens_per_second": _stats([item.get("generation_tokens_per_second") for item in telemetry if item.get("generation_tokens_per_second") is not None])["mean"],
            "ram_mb": _stats([item.get("peak_ram_mb") for item in telemetry if item.get("peak_ram_mb") is not None])["mean"],
            "peak_ram_mb": _stats([item.get("peak_ram_mb") for item in telemetry if item.get("peak_ram_mb") is not None])["mean"],
            "energy_joules": _stats([item.get("energy_joules") for item in telemetry if item.get("energy_measurement_kind") == "measured" and item.get("energy_joules") is not None])["mean"],
            "energy_proxy_joules": _stats([item.get("energy_proxy_joules") for item in telemetry if item.get("energy_proxy_joules") is not None])["mean"],
            "quality_per_estimated_watt": _stats([item.get("quality_per_estimated_watt", item.get("quality_per_watt")) for item in group if item.get("quality_per_estimated_watt", item.get("quality_per_watt")) is not None])["mean"],
            "quality_per_proxy_joule": _stats([item.get("quality_per_proxy_joule") for item in group if item.get("quality_per_proxy_joule") is not None])["mean"],
            "measurement_kind": "measured_spider_execution_aggregate",
            "energy_note": "energy_joules is measured only when a physical meter is configured; energy_proxy_joules is an estimate only",
        }
        profiles.append(profile)
    return profiles


def _normalise_controlled_record(record: dict[str, Any], source: str) -> dict[str, Any] | None:
    """Convert a controlled Spider-study row to the full-matrix record contract.

    Only successful measured rows are useful to an optimizer profile.  Failures
    remain in their original JSONL audit trail and are intentionally not treated
    as zero-quality answers.
    """
    configuration = record.get("configuration") or record.get("runtime_configuration")
    quality = record.get("task_quality") or record.get("quality")
    if not configuration or not quality or quality.get("score") is None:
        return None
    configuration = dict(configuration)
    configuration_id = configuration.get("configuration_id")
    if not configuration_id:
        return None
    # Cache experiments otherwise share one configuration id for both modes.
    if source == "cache":
        cache_mode = str(record.get("cache_mode", "unknown"))
        configuration["cache_mode"] = cache_mode
        configuration["configuration_id"] = f"{configuration_id}:cache-{cache_mode}"
    telemetry = dict(record.get("telemetry") or {})
    if not telemetry:
        energy = record.get("energy") or {}
        telemetry = {
            "end_to_end_seconds": record.get("wall_clock_seconds"),
            "ttft_seconds": record.get("ttft_seconds"),
            "generation_tokens_per_second": record.get("generation_tokens_per_second"),
            "peak_ram_mb": record.get("peak_ram_mb"),
            "energy_joules": energy.get("joules"),
            "energy_measurement_kind": "measured" if energy.get("kind") == "measured" else "estimated_proxy",
            "energy_proxy_joules": energy.get("joules") if energy.get("kind") == "estimated_proxy" else None,
        }
    score = float(quality["score"])
    proxy = telemetry.get("energy_proxy_joules")
    return {
        **record,
        "dataset": record.get("dataset", "spider_dev"),
        "task_type": "spider_text_to_sql",
        "configuration": configuration,
        "task_quality": quality,
        "telemetry": telemetry,
        # Older records may carry the legacy key. Do not derive watts from
        # joules: that is dimensionally invalid without a duration.
        "quality_per_estimated_watt": record.get("quality_per_estimated_watt") or (
            record.get("quality_per_watt") if telemetry.get("energy_proxy_watts") else None
        ),
        "benchmark_source": source,
    }


def load_full_matrix_records(include_controlled_studies: bool = True) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(RAW_DIRECTORY.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
    if not include_controlled_studies:
        return records
    for source, directory in CONTROLLED_STUDY_DIRECTORIES.items():
        for path in sorted(directory.glob("*.jsonl")):
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    normalised = _normalise_controlled_record(json.loads(line), source)
                    if normalised is not None:
                        records.append(normalised)
    return records


def load_standard_quality_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(STANDARD_RAW_DIRECTORY.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    return records


def aggregate_standard_quality_records(records: list[dict[str, Any]], minimum_samples: int = 3) -> list[dict[str, Any]]:
    """Turn repeated task-specific local trials into optimizer profiles."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        if record.get("phase") != "measured" or not record.get("success"):
            continue
        quality = record.get("quality", {}).get("score")
        if quality is None:
            continue
        key = (record["configuration"]["configuration_id"], record["dataset"], record["task_type"])
        groups.setdefault(key, []).append(record)
    profiles: list[dict[str, Any]] = []
    for (configuration_id, dataset, task_type), group in sorted(groups.items()):
        if len(group) < minimum_samples:
            continue
        telemetry = [record["telemetry"] for record in group]
        quality = [record["quality"]["score"] for record in group]
        profiles.append({
            "configuration_id": configuration_id, "model_id": group[0]["model_id"],
            "configuration": group[0]["configuration"], "task_type": task_type, "dataset": dataset,
            "sample_count": len(group), "quality": statistics.mean(quality),
            "quality_statistics": _stats(quality), "quality_lower_confidence_bound": _quality_lower_bound(quality),
            "measurement_confidence": "limited" if len(quality) < 5 else "repeatable",
            "latency_seconds": _stats([item.get("end_to_end_seconds") for item in telemetry if item.get("end_to_end_seconds") is not None])["mean"],
            "ttft_seconds": _stats([item.get("ttft_seconds") for item in telemetry if item.get("ttft_seconds") is not None])["mean"],
            "generation_tokens_per_second": _stats([item.get("generation_tokens_per_second") for item in telemetry if item.get("generation_tokens_per_second") is not None])["mean"],
            "ram_mb": _stats([item.get("peak_ram_mb") for item in telemetry if item.get("peak_ram_mb") is not None])["mean"],
            "peak_ram_mb": _stats([item.get("peak_ram_mb") for item in telemetry if item.get("peak_ram_mb") is not None])["mean"],
            "energy_joules": _stats([item.get("energy_joules") for item in telemetry if item.get("energy_measurement_kind") == "measured" and item.get("energy_joules") is not None])["mean"],
            "energy_proxy_joules": _stats([item.get("energy_proxy_joules") for item in telemetry if item.get("energy_proxy_joules") is not None])["mean"],
            "measurement_kind": "measured_task_specific_aggregate",
        })
    return profiles


def create_profiles(minimum_samples: int = 3, include_standard: bool = False, include_controlled_studies: bool = True) -> Path:
    profiles = aggregate_records(load_full_matrix_records(include_controlled_studies), minimum_samples)
    if include_standard:
        profiles.extend(aggregate_standard_quality_records(load_standard_quality_records(), minimum_samples))
    PROFILE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output = PROFILE_DIRECTORY / f"{new_experiment_id('full_matrix_profiles')}.json"
    output.write_text(json.dumps({
        "created_at": datetime.now(UTC).isoformat(), "minimum_samples": minimum_samples,
        "controlled_studies_included": include_controlled_studies,
        "profile_count": len(profiles), "profiles": profiles,
    }, indent=2), encoding="utf-8")
    return output


def latest_profiles() -> list[dict[str, Any]]:
    profiles_by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in sorted(PROFILE_DIRECTORY.glob("*.json")):
        for profile in json.loads(path.read_text(encoding="utf-8")).get("profiles", []):
            identity = (profile.get("configuration_id", ""), profile.get("dataset", ""), profile.get("task_type", ""))
            profiles_by_identity[identity] = profile
    return list(profiles_by_identity.values())


def select_lowest_cost(profiles: list[dict[str, Any]], quality_threshold: float, weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Apply the quality gate, then choose the best normalized cost profile."""
    if not 0 <= quality_threshold <= 1:
        raise ValueError("quality_threshold must be between zero and one")
    eligible = [
        profile for profile in profiles
        if profile.get("quality") is not None
        and (
            profile["quality_lower_confidence_bound"]
            if profile.get("quality_lower_confidence_bound") is not None
            else profile["quality"]
        ) >= quality_threshold
    ]
    if not eligible:
        return {"selected": None, "quality_threshold": quality_threshold, "eligible_count": 0, "reason": "No measured profile meets the requested quality threshold."}
    candidates = [
        {
            "profile": profile, "task_quality": profile["quality"],
            "quality_lower_confidence_bound": profile.get("quality_lower_confidence_bound"),
            "generation_tokens_per_second": profile.get("generation_tokens_per_second"),
            "ttft_seconds": profile.get("ttft_seconds"), "peak_ram_mb": profile.get("peak_ram_mb", profile.get("ram_mb")),
            "energy_proxy_joules": profile.get("energy_proxy_joules"),
            "quality_per_estimated_watt": profile.get("quality_per_estimated_watt", profile.get("quality_per_watt")),
            "quality_per_proxy_joule": profile.get("quality_per_proxy_joule"),
        }
        for profile in eligible
    ]
    scoring = score_candidates(candidates, {**LOWEST_COST_WEIGHTS, **(weights or {}), "task_quality": 0.0})
    scored = [candidate for candidate in candidates if candidate.get("weighted_score") is not None]
    winner = max(scored, key=lambda candidate: candidate["weighted_score"]) if scored else None
    return {
        "selected": winner["profile"] if winner else None, "quality_threshold": quality_threshold,
        "eligible_count": len(eligible), "scoring": scoring, "candidates": candidates,
        "reason": (
            "Quality threshold satisfied using the conservative lower confidence bound when available; selected by normalized measured cost/efficiency score."
            if winner else "Eligible profiles have no common measured cost metrics."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregate measured Spider benchmark profiles.")
    parser.add_argument("--minimum-samples", type=int, default=3)
    parser.add_argument("--include-standard", action="store_true", help="Include locally prepared task-specific benchmark profiles.")
    parser.add_argument("--exclude-controlled-studies", action="store_true", help="Use only full-matrix runs (normally controlled studies are included).")
    arguments = parser.parse_args()
    print(create_profiles(arguments.minimum_samples, arguments.include_standard, not arguments.exclude_controlled_studies))
