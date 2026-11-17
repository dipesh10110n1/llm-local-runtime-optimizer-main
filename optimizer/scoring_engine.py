"""Preference-specific transparent rankings; estimates rank below measured profiles."""
from __future__ import annotations
from runtime_optimizer.types import CandidateProfile, Preference


def _cost(value: float | None) -> float: return value if value is not None else float("inf")
def _quality(value: float | None) -> float: return value if value is not None else -float("inf")


def rank(candidates: list[CandidateProfile], preference: Preference) -> list[CandidateProfile]:
    measured_penalty = lambda c: 0 if c.source == "measured" else 1
    if preference == "quality": return sorted(candidates, key=lambda c: (measured_penalty(c), -_quality(c.quality), _cost(c.latency_seconds)))
    if preference == "latency": return sorted(candidates, key=lambda c: (measured_penalty(c), _cost(c.latency_seconds), -_quality(c.quality)))
    if preference == "memory": return sorted(candidates, key=lambda c: (measured_penalty(c), _cost(c.ram_mb), -_quality(c.quality)))
    if preference == "energy": return sorted(candidates, key=lambda c: (measured_penalty(c), _cost(c.energy_joules), -_quality(c.quality)))
    return sorted(candidates, key=lambda c: (measured_penalty(c), -_quality(c.quality), _cost(c.latency_seconds), _cost(c.ram_mb), _cost(c.energy_joules)))
