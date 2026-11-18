from optimizer.request_router import classify_task, selection_caption


def test_classifies_common_task_types():
    assert classify_task("Write a Python function") == "coding"
    assert classify_task("Solve this math equation") == "reasoning"
    assert classify_task("Summarize this paragraph") == "summarization"


def test_selection_caption_discloses_estimated_quality():
    decision = {
        "selected": {"model": {"model_id": "qwen-test"}, "memory_source": "estimated from GGUF file size"},
        "configuration": {"threads": 4, "context_size": 2048},
    }
    assert "estimate" in selection_caption(decision).lower()
