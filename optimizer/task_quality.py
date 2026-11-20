"""Reference-based task-quality checks used by local model comparison."""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def _sql_from_response(text: str) -> str:
    """Extract a SQL statement from a model response without sending it elsewhere."""
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    statement = re.search(r"\b(?:select|with|insert|update|delete)\b.*", candidate, flags=re.IGNORECASE | re.DOTALL)
    return statement.group(0) if statement else candidate


def _normalise_sql(text: str) -> str:
    text = _sql_from_response(text).strip().rstrip(";")
    return re.sub(r"\s+", " ", text).lower()


def _safe_select(sql: str) -> bool:
    return bool(re.match(r"^\s*(?:select|with|explain)\b", sql, flags=re.IGNORECASE))


def _requires_ordered_rows(sql: str) -> bool:
    """Whether the result sequence is part of the reference query's contract.

    This intentionally uses the reference SQL as the conservative signal.  An
    unordered reference is compared as a multiset, while an ordered reference
    must be reproduced as the same sequence by a query that declares ordering.
    """
    return bool(re.search(r"\border\s+by\b", sql, flags=re.IGNORECASE))


def _execute_read_only(database_path: Path, sql: str) -> list[tuple[Any, ...]]:
    if not _safe_select(sql):
        raise ValueError("Only read-only SELECT, WITH, or EXPLAIN SQL is evaluated.")
    with sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True) as connection:
        connection.set_progress_handler(lambda: 1, 1_000_000)
        return connection.execute(sql).fetchall()


def evaluate_spider_sql(answer: str, reference_sql: str | None, database_path: Path | None = None) -> dict[str, Any]:
    """Score one Spider response against a user-supplied gold SQL query.

    This is exact normalized SQL matching. Equivalent SQL written differently is
    deliberately reported as a non-match; execution equivalence needs the
    corresponding local Spider SQLite database and evaluator.
    """
    if not reference_sql or not reference_sql.strip():
        return {
            "score": None,
            "metric": "spider_sql_exact_match",
            "status": "reference_sql_required",
        }
    expected = _normalise_sql(reference_sql)
    predicted = _normalise_sql(answer)
    if predicted == expected:
        return {
            "score": 1.0,
            "metric": "spider_sql_exact_match",
            "status": "measured_exact_match",
            "predicted_sql": predicted,
            "reference_sql": expected,
        }
    if database_path and database_path.exists():
        try:
            predicted_rows = _execute_read_only(database_path, predicted)
            expected_rows = _execute_read_only(database_path, expected)
            ordering_required = _requires_ordered_rows(expected)
            predicted_declares_ordering = _requires_ordered_rows(predicted)
            if ordering_required:
                matched = predicted_declares_ordering and predicted_rows == expected_rows
                comparison_kind = "ordered_row_sequence"
                status = "measured_execution_match" if matched else "ordered_execution_mismatch"
            else:
                matched = Counter(predicted_rows) == Counter(expected_rows)
                comparison_kind = "unordered_row_multiset"
                status = "measured_execution_match" if matched else "execution_mismatch"
            return {
                "score": float(matched),
                "metric": "spider_sql_execution_match",
                "status": status,
                "row_comparison": comparison_kind,
                "reference_requires_ordering": ordering_required,
                "predicted_declares_ordering": predicted_declares_ordering,
                "predicted_sql": predicted,
                "reference_sql": expected,
            }
        except (sqlite3.Error, ValueError) as error:
            return {
                "score": 0.0,
                "metric": "spider_sql_execution_match",
                "status": "invalid_or_nonmatching_sql",
                "error": str(error),
                "predicted_sql": predicted,
                "reference_sql": expected,
            }
    return {
        "score": 0.0,
        "metric": "spider_sql_exact_match",
        "status": "nonmatching_exact_sql",
        "predicted_sql": predicted,
        "reference_sql": expected,
    }
