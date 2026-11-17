"""Runs the appropriate evaluator selected by a normalized dataset sample."""
from __future__ import annotations

from typing import Any
from benchmarks.quality_metrics import evaluate
from datasets.dataset_validator import validate_sample


def evaluate_response(sample: dict[str, Any], response: str) -> dict[str, Any]:
    errors = validate_sample(sample)
    if errors:
        raise ValueError("Invalid sample: " + "; ".join(errors))
    result = evaluate(sample["evaluation_type"], response, sample["reference_answer"], sample["metadata"])
    return {"sample_id": sample["sample_id"], "dataset": sample["dataset"], "task_type": sample["task_type"], **result}
