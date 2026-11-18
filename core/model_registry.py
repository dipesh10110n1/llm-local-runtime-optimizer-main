from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.settings import ROOT

REGISTRY_PATH = ROOT / "config" / "models.json"


def load_models() -> list[dict[str, Any]]:
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        models = json.load(handle)
    for model in models:
        path = model.get("path")
        model["available_locally"] = bool(path and (ROOT / path).exists())
    return models


def get_model(model_id: str) -> dict[str, Any] | None:
    return next((item for item in load_models() if item["model_id"] == model_id), None)
