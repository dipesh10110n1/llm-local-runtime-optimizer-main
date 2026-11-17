"""Candidate retrieval abstraction. Storage adapters return only supported hardware profiles."""
from runtime_optimizer.types import CandidateProfile


def for_task(candidates: list[CandidateProfile], task_type: str) -> list[CandidateProfile]:
    exact = [candidate for candidate in candidates if candidate.task_type == task_type]
    return exact or [candidate for candidate in candidates if candidate.task_type == "general"]
