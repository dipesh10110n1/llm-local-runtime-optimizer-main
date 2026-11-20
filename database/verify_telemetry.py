"""Read-only verification of the optional local MySQL telemetry connection."""
from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.settings import settings
from database.schema import make_engine


REQUIRED_TABLES = {
    "models", "hardware_profiles", "runtime_configurations", "benchmark_experiments",
    "benchmark_results", "quality_results", "performance_metrics", "resource_metrics",
    "energy_metrics", "optimization_recommendations",
}


def verify(url: str | None = None) -> dict[str, Any]:
    """Check connectivity and schema presence without writing benchmark data."""
    database_url = url or settings.database_url
    if not database_url or not database_url.startswith("mysql+"):
        return {"configured": False, "connected": False, "reason": "DATABASE_URL is not configured for local MySQL."}
    try:
        engine = make_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            names = set(connection.execute(text("SHOW TABLES")).scalars())
        return {
            "configured": True, "connected": True,
            "required_tables_present": sorted(REQUIRED_TABLES & names),
            "missing_tables": sorted(REQUIRED_TABLES - names),
            "ready": REQUIRED_TABLES.issubset(names),
        }
    except SQLAlchemyError as error:
        return {"configured": True, "connected": False, "ready": False, "reason": error.__class__.__name__}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify local MySQL telemetry without creating or changing data.")
    parser.parse_args()
    print(json.dumps(verify(), indent=2))
