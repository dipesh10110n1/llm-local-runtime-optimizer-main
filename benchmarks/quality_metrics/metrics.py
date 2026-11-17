"""Small dependency-light evaluation implementations.

MBPP execution is deliberately restricted to a temporary working directory,
with a timeout and stripped environment. This is risk reduction, not a
security boundary; use a container/VM for untrusted benchmark outputs.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def normalize_exact(text: str) -> str:
    return " ".join(text.strip().casefold().split())


def exact_match(prediction: str, reference: str) -> dict[str, Any]:
    return {"metric": "exact_match", "score": float(normalize_exact(prediction) == normalize_exact(reference))}


def extract_number(text: str) -> str | None:
    matches = re.findall(r"(?:####\s*)?(-?\d+(?:\.\d+)?)", text.replace(",", ""))
    return matches[-1] if matches else None


def gsm8k_numeric_match(prediction: str, reference: str) -> dict[str, Any]:
    predicted, expected = extract_number(prediction), extract_number(reference)
    return {"metric": "gsm8k_numeric_exact_match", "score": float(predicted is not None and predicted == expected), "predicted": predicted, "expected": expected}


def code_tests(prediction: str, tests: list[str], timeout_seconds: float = 3.0) -> dict[str, Any]:
    code = re.sub(r"^```(?:python)?\s*|```$", "", prediction.strip(), flags=re.MULTILINE)
    with tempfile.TemporaryDirectory(prefix="llm-opt-mbpp-") as directory:
        script = Path(directory) / "candidate.py"
        script.write_text(code + "\n\n" + "\n".join(tests), encoding="utf-8")
        try:
            completed = subprocess.run([sys.executable, "-I", str(script)], cwd=directory, capture_output=True, text=True, timeout=timeout_seconds, env={"PYTHONIOENCODING": "utf-8"})
            return {"metric": "mbpp_tests", "score": float(completed.returncode == 0), "stderr": completed.stderr[-1000:]}
        except subprocess.TimeoutExpired:
            return {"metric": "mbpp_tests", "score": 0.0, "error": "timeout"}


def rouge_l(prediction: str, reference: str) -> dict[str, Any]:
    try:
        from rouge_score import rouge_scorer  # type: ignore[import-not-found]
        score = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True).score(reference, prediction)["rougeL"].fmeasure
        return {"metric": "rougeL_f1", "score": score}
    except ImportError:
        # A transparent fallback used only when optional ROUGE dependency is absent.
        p, r = set(normalize_exact(prediction).split()), set(normalize_exact(reference).split())
        overlap = len(p & r)
        return {"metric": "token_overlap_fallback", "score": (2 * overlap / (len(p) + len(r))) if p or r else 0.0, "warning": "Install rouge-score for ROUGE-L."}


def ifeval_proxy(prediction: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {"metric": "ifeval_requires_official_evaluator", "score": None, "instruction_ids": metadata.get("instruction_id_list", []), "warning": "Run the official IFEval evaluator for a valid score."}


def evaluate(evaluation_type: str, prediction: str, reference: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    if evaluation_type == "exact_match":
        return exact_match(prediction, reference)
    if evaluation_type == "numeric_exact_match":
        return gsm8k_numeric_match(prediction, reference)
    if evaluation_type == "code_tests":
        return code_tests(prediction, metadata.get("test_list", []))
    if evaluation_type == "rouge":
        return rouge_l(prediction, reference)
    if evaluation_type == "ifeval":
        return ifeval_proxy(prediction, metadata)
    raise ValueError(f"Unsupported evaluation type: {evaluation_type}")
