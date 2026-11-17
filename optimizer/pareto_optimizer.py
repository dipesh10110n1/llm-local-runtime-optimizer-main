"""Non-dominated measured candidates for quality (max) and cost metrics (min)."""
from __future__ import annotations
from runtime_optimizer.types import CandidateProfile


def dominates(left: CandidateProfile, right: CandidateProfile) -> bool:
    # Exclude dimensions missing on either profile instead of inventing measurements.
    pairs = [(left.quality, right.quality, True), (left.latency_seconds, right.latency_seconds, False), (left.ram_mb, right.ram_mb, False), (left.energy_joules, right.energy_joules, False)]
    compared = [(a, b, maximize) for a, b, maximize in pairs if a is not None and b is not None]
    if not compared: return False
    no_worse = all(a >= b if maximize else a <= b for a, b, maximize in compared)
    better = any(a > b if maximize else a < b for a, b, maximize in compared)
    return no_worse and better


def frontier(candidates: list[CandidateProfile]) -> list[CandidateProfile]:
    return [candidate for candidate in candidates if not any(other is not candidate and dominates(other, candidate) for other in candidates)]
