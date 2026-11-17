"""Human-readable, honest recommendation explanations."""
from runtime_optimizer.types import CandidateProfile, Recommendation


def explain(selected: CandidateProfile | None, feasible_count: int, violations: dict[str, list[str]]) -> str:
    if selected is None:
        names = sorted({item for values in violations.values() for item in values})
        return "No measured configuration satisfies all requested constraints. Violated constraints: " + (", ".join(names) or "no candidate profiles are available") + "."
    status = "measured on this system" if selected.source == "measured" else "estimated; validate with a benchmark before relying on it"
    return f"Selected {selected.configuration.configuration_id} from {feasible_count} feasible profile(s); its evidence is {status} and has {selected.sample_count} sample(s)."
