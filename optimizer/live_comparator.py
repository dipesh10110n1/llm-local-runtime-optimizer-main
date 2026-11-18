"""Prompt-specific, sequential local-model comparison before final generation."""
from __future__ import annotations

import re
from typing import Any

from optimizer.request_router import classify_task, recommend_runtime
from runtime.clients import InferenceError, generate
from runtime.supervisor import RuntimeSwitchError, ensure_runtime


def _configuration(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "configuration_id": f"{model['model_id']}:t4:c2048:cpu",
        "backend": "llama.cpp", "threads": 4, "context_size": 2048,
        "gpu_layers": 0, "cache": "server-default",
    }


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


def compare_on_spot(prompt: str, models: list[dict[str, Any]], max_output_tokens: int, temperature: float) -> dict[str, Any]:
    """Generate complete candidate responses, locally judge them, and return the winner.

    This deliberately runs one server/model at a time to stay within laptop RAM limits.
    """
    feasibility = recommend_runtime(prompt, models)
    candidates = [item for item in feasibility["candidates"] if item["feasible"]]
    if not candidates:
        return {"selected": None, "task_type": feasibility["task_type"], "available_mb": feasibility["available_mb"], "candidates": feasibility["candidates"], "reason": feasibility["reason"]}

    comparisons: list[dict[str, Any]] = []
    for item in candidates:
        model = item["model"]
        configuration = _configuration(model)
        ensure_runtime(model, configuration)
        response = generate(
            model,
            prompt,
            {
                "backend": "llama.cpp",
                # These are complete candidate answers, not short routing probes.
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            },
        )
        comparisons.append({
            "candidate": item, "configuration": configuration, "draft": response["answer"],
            "latency_seconds": response["end_to_end_seconds"],
            "generated_tokens": response.get("generated_tokens"),
            "generation_tokens_per_second": response.get("generation_tokens_per_second"),
        })

    # Use the largest feasible local model solely as a local response judge, not a remote API.
    judge = max(candidates, key=lambda item: item["model"]["parameter_count_b"])
    judge_model = judge["model"]
    judge_configuration = _configuration(judge_model)
    ensure_runtime(judge_model, judge_configuration)
    option_text = "\n\n".join(
        f"CANDIDATE {index + 1} ({entry['candidate']['model']['model_id']}):\n{entry['draft'][:1800]}"
        for index, entry in enumerate(comparisons)
    )
    judge_prompt = (
        "You are a strict evaluator of local-model responses. Compare the candidate responses "
        "to the original user request. Select the response that is most correct, directly "
        "answers the request, follows its instructions, and is useful. Do not prefer a model "
        "because of its name or size. Reply with exactly one of: WINNER: 1, WINNER: 2, or "
        "WINNER: TIE. Do not add an explanation.\n\n"
        f"ORIGINAL USER REQUEST:\n{prompt[:4000]}\n\n{option_text}"
    )
    judge_response = generate(
        judge_model,
        judge_prompt,
        {"backend": "llama.cpp", "max_output_tokens": 16, "temperature": 0},
    )
    winner_index = parse_judgement(judge_response["answer"], len(comparisons))
    if winner_index is None:
        winner_index = max(
            range(len(comparisons)),
            key=lambda index: comparisons[index]["candidate"]["model"]["parameter_count_b"],
        )
        basis = (
            "Live judge returned a tie or an invalid verdict; selected the largest feasible "
            "model as a transparent quality fallback."
        )
    else:
        basis = (
            f"Live local judge ({judge_model['model_id']}) selected candidate "
            f"{winner_index + 1} for this prompt."
        )
    winner = comparisons[winner_index]
    return {
        "selected": winner["candidate"], "configuration": winner["configuration"],
        "task_type": classify_task(prompt), "available_mb": feasibility["available_mb"],
        "candidates": feasibility["candidates"], "reason": basis,
        "live_comparison": comparisons, "judge_model_id": judge_model["model_id"],
        "judge_output": judge_response["answer"], "winner_index": winner_index,
    }
