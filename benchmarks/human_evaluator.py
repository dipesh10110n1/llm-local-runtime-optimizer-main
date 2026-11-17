"""Separate schema for manual assessment; it does not assert factual validity."""
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class HumanEvaluation:
    correctness: int
    completeness: int
    relevance: int
    clarity: int
    instruction_following: int
    evaluator_id: str
    notes: str = ""

    def validate(self) -> None:
        if any(not 0 <= value <= 2 for value in (self.correctness, self.completeness, self.relevance, self.clarity, self.instruction_following)):
            raise ValueError("Human dimensions must be whole scores from 0 to 2.")

    @property
    def total(self) -> int:
        self.validate()
        return sum((self.correctness, self.completeness, self.relevance, self.clarity, self.instruction_following))

    def as_dict(self) -> dict:
        result = asdict(self)
        result["total_score"] = self.total
        result["quality_percentage"] = self.total * 10
        result["warning"] = "Human ratings are stored separately from automated correctness metrics."
        return result
