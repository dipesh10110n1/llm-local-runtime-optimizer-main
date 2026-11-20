"""Read-only structural verification for a local Spider dataset copy."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.settings import ROOT

EXPECTED_FILES = (
    "train_spider.json", "train_others.json", "dev.json", "dev_gold.sql", "tables.json",
    "test.json", "test_gold.sql", "train_gold.sql", "test_tables.json", "database", "test_database",
)
JSON_DATASETS = ("train_spider.json", "train_others.json", "dev.json", "test.json")


def _open_database(path: Path) -> str | None:
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
            connection.execute("pragma schema_version").fetchone()
        return None
    except sqlite3.Error as error:
        return str(error)


def verify_spider(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = {name: (root / name).exists() for name in EXPECTED_FILES}
    report: dict[str, Any] = {
        "dataset_root": str(root), "verified_at": datetime.now(UTC).isoformat(),
        "expected_files": files, "json_files": {}, "schema": {}, "database_checks": {}, "issues": [],
    }
    examples: dict[str, list[dict[str, Any]]] = {}
    for name in JSON_DATASETS:
        path = root / name
        if not path.exists():
            report["issues"].append(f"Missing dataset file: {name}")
            continue
        try:
            contents = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(contents, list):
                raise ValueError("expected a JSON array")
            examples[name] = contents
            report["json_files"][name] = {"valid": True, "record_count": len(contents)}
        except (json.JSONDecodeError, OSError, ValueError) as error:
            report["json_files"][name] = {"valid": False, "error": str(error)}
            report["issues"].append(f"Malformed dataset file {name}: {error}")

    for name in ("tables.json", "test_tables.json"):
        path = root / name
        if not path.exists():
            report["issues"].append(f"Missing schema file: {name}")
            continue
        try:
            tables = json.loads(path.read_text(encoding="utf-8"))
            valid = isinstance(tables, list) and all(isinstance(row, dict) and "db_id" in row for row in tables)
            report["schema"][name] = {"valid": valid, "database_count": len(tables) if isinstance(tables, list) else 0}
            if not valid:
                report["issues"].append(f"Schema file has unexpected shape: {name}")
        except (json.JSONDecodeError, OSError) as error:
            report["schema"][name] = {"valid": False, "error": str(error)}
            report["issues"].append(f"Malformed schema file {name}: {error}")

    for split, records in examples.items():
        database_parent = "test_database" if split == "test.json" else "database"
        referenced_ids = {row.get("db_id") for row in records if isinstance(row.get("db_id"), str)}
        missing = []
        opened = 0
        failures: dict[str, str] = {}
        for database_id in referenced_ids:
            database = root / database_parent / database_id / f"{database_id}.sqlite"
            if not database.exists():
                missing.append(database_id)
                continue
            error = _open_database(database)
            if error:
                failures[database_id] = error
            else:
                opened += 1
        report["database_checks"][split] = {
            "referenced_database_count": len(referenced_ids), "opened_read_only": opened,
            "missing_database_ids": sorted(missing), "open_failures": failures,
        }
        if missing:
            report["issues"].append(f"{split}: missing SQLite databases for {', '.join(sorted(missing)[:10])}")
        if failures:
            report["issues"].append(f"{split}: {len(failures)} SQLite databases could not be opened")
    return report


def write_report(report: dict[str, Any], output_dir: Path | None = None) -> Path:
    directory = output_dir or ROOT / "logs" / "verification_reports"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"spider_verification_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    report = verify_spider(ROOT / "spider_data" / "spider_data")
    saved = write_report(report)
    print(json.dumps({"report": str(saved), "issues": report["issues"]}, indent=2))
