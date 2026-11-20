import json
import sqlite3

from benchmarks.spider_verifier import EXPECTED_FILES, verify_spider


def test_verifies_minimal_read_only_spider_layout(tmp_path):
    for name in EXPECTED_FILES:
        path = tmp_path / name
        if path.suffix == ".json":
            path.write_text("[]", encoding="utf-8")
        elif not path.suffix:
            path.mkdir()
        else:
            path.write_text("", encoding="utf-8")
    schema = [{"db_id": "sample", "table_names_original": [], "column_names_original": []}]
    (tmp_path / "tables.json").write_text(json.dumps(schema), encoding="utf-8")
    (tmp_path / "test_tables.json").write_text(json.dumps(schema), encoding="utf-8")
    records = [{"db_id": "sample", "question": "count rows", "query": "select 1"}]
    for name in ("train_spider.json", "train_others.json", "dev.json"):
        (tmp_path / name).write_text(json.dumps(records), encoding="utf-8")
    for parent in ("database", "test_database"):
        directory = tmp_path / parent / "sample"
        directory.mkdir()
        with sqlite3.connect(directory / "sample.sqlite") as connection:
            connection.execute("create table item (id integer)")
    (tmp_path / "test.json").write_text(json.dumps(records), encoding="utf-8")

    report = verify_spider(tmp_path)

    assert not report["issues"]
    assert report["database_checks"]["dev.json"]["opened_read_only"] == 1
