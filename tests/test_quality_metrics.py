from benchmarks.quality_metrics.metrics import evaluate


def test_numeric_extracts_final_answer():
    result = evaluate({"evaluation_type": "numeric_exact", "reference_answer": "Work gives 42."}, "Therefore the answer is 42")
    assert result["score"] == 1


def test_rouge_is_not_fabricated():
    result = evaluate({"evaluation_type": "rouge", "reference_answer": "cats sit on mats"}, "cats sit")
    assert 0 < result["score"] < 1
