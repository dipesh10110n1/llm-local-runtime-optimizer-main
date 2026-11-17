"""End-to-end deterministic optimizer with an explicit no-feasible-result path."""
from __future__ import annotations
from runtime_optimizer.types import CandidateProfile, OptimizationRequest, Recommendation
from .candidate_generator import for_task
from .constraint_manager import feasible
from .pareto_optimizer import frontier
from .recommendation_engine import explain
from .scoring_engine import rank


class RuntimeOptimizer:
    def __init__(self, candidates: list[CandidateProfile]): self.candidates = candidates

    def recommend(self, request: OptimizationRequest) -> Recommendation:
        relevant = for_task(self.candidates, request.task_type)
        valid, rejected = feasible(relevant, request)
        if valid:
            ranked = rank(valid, request.preference)
            return Recommendation(selected=ranked[0], feasible=ranked, pareto_frontier=frontier(valid), violations=rejected, explanation=explain(ranked[0], len(valid), rejected))
        closest = rank(relevant, request.preference)[:3]
        return Recommendation(selected=None, alternatives=closest, violations=rejected, explanation=explain(None, 0, rejected))
