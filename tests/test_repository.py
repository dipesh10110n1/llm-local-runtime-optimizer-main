from database.repository import ExperimentRepository


def test_sqlite_is_explicitly_test_only():
    repo = ExperimentRepository("sqlite+pysqlite:///:memory:", allow_sqlite_for_tests=True)
    repo.initialize_schema()
    repo.upsert_model("model", {"name": "test"})
    assert repo.add_experiment("run-1", "model", "config", "ollama")
    assert not repo.add_experiment("run-1", "model", "config", "ollama")
