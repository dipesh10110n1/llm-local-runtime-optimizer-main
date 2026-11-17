from benchmarks.evaluation_runner import evaluate_response
from benchmarks.quality_metrics.metrics import code_tests, gsm8k_numeric_match


def test_gsm8k_final_number_match():
    assert gsm8k_numeric_match("work... #### 42", "answer is 42")["score"] == 1.0


def test_code_test_executes_with_assertion():
    result = code_tests("def add(a, b):\n    return a + b", ["assert add(2, 3) == 5"])
    assert result["score"] == 1.0


def test_runner_selects_metric():
    sample = {"sample_id": "g:1", "dataset": "gsm8k", "task_type": "reasoning", "prompt": "Solve the problem", "reference_answer": "#### 5", "evaluation_type": "numeric_exact_match", "metadata": {}}
    assert evaluate_response(sample, "5")["score"] == 1.0
