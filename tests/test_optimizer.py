from optimizer.optimizer import RuntimeOptimizer
from runtime_optimizer.types import CandidateProfile, OptimizationRequest, RuntimeConfiguration


def profile(identifier, quality, latency, ram, energy=None):
    return CandidateProfile(RuntimeConfiguration(identifier, identifier, "ollama"), "general", quality, latency, ram, energy, 5)


def test_quality_first_respects_constraints():
    optimizer = RuntimeOptimizer([profile("fast", .7, 1, 100), profile("good", .9, 2, 200)])
    result = optimizer.recommend(OptimizationRequest("test", minimum_quality=.8, maximum_latency_seconds=3, preference="quality"))
    assert result.selected.configuration.configuration_id == "good"


def test_unknown_energy_fails_explicit_cap():
    result = RuntimeOptimizer([profile("one", .9, 1, 100)]).recommend(OptimizationRequest("x", maximum_energy_joules=2))
    assert result.selected is None
    assert result.violations["one"] == ["maximum_energy_joules"]


def test_no_feasible_result_returns_alternatives():
    result = RuntimeOptimizer([profile("slow", .9, 10, 100)]).recommend(OptimizationRequest("x", maximum_latency_seconds=1))
    assert result.selected is None and result.alternatives
