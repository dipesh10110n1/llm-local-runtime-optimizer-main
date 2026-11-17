"""Feasibility filters. Unknown energy cannot satisfy an explicit energy cap."""
from __future__ import annotations

from runtime_optimizer.types import CandidateProfile, OptimizationRequest


def violations(candidate: CandidateProfile, request: OptimizationRequest) -> list[str]:
    errors: list[str] = []
    if request.minimum_quality is not None and (candidate.quality is None or candidate.quality < request.minimum_quality): errors.append("minimum_quality")
    if request.maximum_latency_seconds is not None and (candidate.latency_seconds is None or candidate.latency_seconds > request.maximum_latency_seconds): errors.append("maximum_latency_seconds")
    if request.maximum_ram_mb is not None and (candidate.ram_mb is None or candidate.ram_mb > request.maximum_ram_mb): errors.append("maximum_ram_mb")
    if request.maximum_energy_joules is not None and (candidate.energy_joules is None or candidate.energy_joules > request.maximum_energy_joules): errors.append("maximum_energy_joules")
    return errors


def feasible(candidates: list[CandidateProfile], request: OptimizationRequest) -> tuple[list[CandidateProfile], dict[str, list[str]]]:
    accepted, rejected = [], {}
    for candidate in candidates:
        failed = violations(candidate, request)
        if failed: rejected[candidate.configuration.configuration_id] = failed
        else: accepted.append(candidate)
    return accepted, rejected
